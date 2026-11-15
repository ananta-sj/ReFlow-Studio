"""GUI reconnect, orderly close and temporary-cleanup boundaries."""
from collections import deque
from pathlib import Path
import tempfile
import threading
import unittest
import sys
import subprocess
import time
import psutil
from unittest.mock import Mock, patch

from bridge import push
from dev.test_render_queue import api
from core.code_updates import backend_version, interface_version
from core.exit_cleanup import clear_temporary_files
from core.render_context import RenderContext, bind_job, run_process


class LifecycleTests(unittest.TestCase):
    def test_interface_edits_trigger_a_finite_build_using_existing_tools(self):
        from core.interface_watcher import InterfaceWatcher

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'frontend/src/view.ts'
            source.parent.mkdir(parents=True)
            source.write_text('old interface')
            vite = root/'frontend/node_modules/vite/bin/vite.js'
            vite.parent.mkdir(parents=True)
            vite.write_text('fixture')
            built = threading.Event()
            ready = threading.Event()
            process = Mock()
            process.poll.return_value = 0
            def build(*args, **kwargs):
                built.set()
                return process
            original_stamp = InterfaceWatcher.stamp
            def stamp(watcher):
                value = original_stamp(watcher)
                ready.set()
                return value
            with (
                patch('core.interface_watcher.shutil.which', return_value='node'),
                patch.object(InterfaceWatcher, 'stamp', stamp),
                patch('core.interface_watcher.subprocess.Popen', side_effect=build) as start,
            ):
                watcher = InterfaceWatcher(root)
                try:
                    self.assertTrue(ready.wait(5))
                    source.write_text('updated interface')
                    self.assertTrue(built.wait(5))
                    self.assertNotIn('--watch', start.call_args.args[0])
                finally:
                    watcher.close()
                self.assertFalse(watcher.thread.is_alive())

    def test_isolated_worker_exits_when_its_parent_crashes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            ready = Path(folder)/'ready'
            child = ("import sys,time,pathlib;"
                     f"sys.path.insert(0,{str(root)!r});"
                     "from core.worker_lifetime import watch_parent;"
                     f"pathlib.Path({str(ready)!r}).write_text('ready');"
                     "watch_parent();time.sleep(60)")
            parent = (
                "import os,sys,subprocess,psutil;"
                "env=dict(os.environ,REFLOW_PARENT_PID=str(os.getpid()),"
                "REFLOW_PARENT_CREATED=str(psutil.Process().create_time()));"
                f"p=subprocess.Popen([sys.executable,'-B','-c',{child!r}],env=env,"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,"
                "creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));"
                "print(p.pid,flush=True);os._exit(0)")
            result = subprocess.run([sys.executable, '-B', '-c', parent], capture_output=True,
                                    text=True, timeout=20, check=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            pid = int(result.stdout.strip())
            try:
                deadline = time.monotonic()+10
                while psutil.pid_exists(pid) and time.monotonic() < deadline:
                    time.sleep(.1)
                self.assertTrue(ready.exists())
                self.assertFalse(psutil.pid_exists(pid))
            finally:
                if psutil.pid_exists(pid):
                    psutil.Process(pid).kill()

    def test_separator_report_comes_from_its_actual_worker_log(self):
        from types import SimpleNamespace
        from core.job_telemetry import SeparationProgress

        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            (workspace/'demucs-test').mkdir()
            (workspace/'demucs-test/worker.log').write_text(' 17%|####| frames processed\r')
            reported = []
            event = threading.Event()
            def report(percent):
                reported.append(percent)
                event.set()
            monitor = SeparationProgress(SimpleNamespace(workspace=workspace), report)
            try:
                self.assertTrue(event.wait(5))
                self.assertEqual(reported, [17])
            finally:
                monitor.close()

    def test_active_worker_can_run_past_idle_window_but_stalled_worker_is_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(folder)
            activity = job.workspace/'activity.log'
            script = "import pathlib,sys,time;p=pathlib.Path(sys.argv[1]);[(p.write_text(str(i)),time.sleep(.2)) for i in range(6)]"
            try:
                with bind_job(job):
                    run_process([sys.executable, '-B', '-c', script, str(activity)],
                                timeout=10, check=True, activity_path=activity, idle_timeout=1)
                    with self.assertRaisesRegex(TimeoutError, 'without reported activity'):
                        run_process([sys.executable, '-B', '-c', 'import time;time.sleep(20)'],
                                    timeout=20, activity_path=activity, idle_timeout=.3)
                self.assertFalse(job.processes)
            finally:
                job.cleanup()

    def test_logs_survive_a_page_reload_and_gui_dispatch_failure(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(push, '_logs', deque(maxlen=1000)),
            patch.object(push, '_loaded', False),
            patch.object(push, '_log_path', return_value=Path(folder)/'log.jsonl'),
            patch.object(push.webview, 'windows', [Mock()]) as windows,
        ):
            windows[0].evaluate_js.side_effect = RuntimeError('page reloading')
            push.emit('log', {'level': 'info', 'message': 'Separation complete'})
            first = push.recent_logs()
            self.assertEqual(first[-1]['message'], 'Separation complete')
            with patch.object(push, '_logs', deque(maxlen=1000)), patch.object(push, '_loaded', False):
                self.assertEqual(push.recent_logs()[-1]['id'], first[-1]['id'])

    def test_exit_cleanup_clears_temp_and_keeps_recovery_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            temporary = root/'temp'
            (temporary/'jobs/job-example').mkdir(parents=True)
            (temporary/'jobs/job-example/working.wav').write_bytes(b'temp')
            (temporary/'legacy.log').write_text('temp')
            recovery = root/'outputs/stage_checkpoints/audio'
            recovery.mkdir(parents=True)
            (recovery/'saved.wav').write_bytes(b'saved')
            clear_temporary_files(root, temporary)
            self.assertEqual(list(temporary.iterdir()), [])
            self.assertEqual((recovery/'saved.wav').read_bytes(), b'saved')
            with self.assertRaises(ValueError):
                clear_temporary_files(root, root)

    def test_code_updates_distinguish_interface_and_backend_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'frontend/dist').mkdir(parents=True)
            (root/'main.py').write_text('old code')
            (root/'frontend/dist/index.html').write_text('old interface')
            backend, frontend = backend_version(root), interface_version(root)
            (root/'frontend/dist/index.html').write_text('new interface')
            self.assertEqual(backend_version(root), backend)
            self.assertNotEqual(interface_version(root), frontend)
            (root/'main.py').write_text('updated backend code')
            self.assertNotEqual(backend_version(root), backend)

    def test_close_waits_for_render_and_runs_optional_cleanup_before_destroy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'temp').mkdir()
            (root/'temp/working.log').write_text('temporary')
            bridge = api.PythonBridge.__new__(api.PythonBridge)
            bridge._render_lock = threading.RLock()
            bridge._render_thread = Mock()
            bridge._active_job = Mock()
            bridge.queue_manager = Mock()
            bridge.settings = {'clear_temp_on_exit': True}
            bridge._tray_stop_fn = None
            finished = threading.Event()
            window = Mock()
            window.destroy.side_effect = finished.set
            with (
                patch.object(api.config, 'BASE_DIR', str(root)),
                patch.object(api.config, 'TEMP_PATH', str(root/'temp')),
                patch.object(api.webview, 'windows', [window]),
                patch.object(bridge, '_emit_render'),
            ):
                bridge.close_window()
                self.assertTrue(finished.wait(5))
            bridge._active_job.request_stop.assert_called_once()
            bridge._render_thread.join.assert_called_once()
            self.assertTrue(bridge._shutdown_ready)
            self.assertEqual(list((root/'temp').iterdir()), [])
