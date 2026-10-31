"""Deterministic cancellation races and disposable real process checks."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core.render_context import RenderContext, RenderCancelled, bind_job, current_job, run_process, wait_or_cancel
from dev import test_render_queue as queue_fixture
from dev.test_speech_integrity import pipeline


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = RenderContext(self.root)

    def test_binding_is_thread_local_and_restored(self):
        with bind_job(self.job):
            self.assertIs(current_job(), self.job)
            with ThreadPoolExecutor(1) as pool:
                self.assertIsNone(pool.submit(current_job).result())
        self.assertIsNone(current_job())

    def test_scoped_cleanup_preserves_siblings_models_outputs(self):
        sibling = RenderContext(self.root)
        (sibling.workspace / 'keep').write_text('other job')
        outside = self.root / 'output.wav'
        outside.write_text('user output')
        (self.job.workspace / 'owned').write_text('temporary')
        self.job.cleanup()
        self.assertFalse(self.job.workspace.exists())
        self.assertTrue((sibling.workspace / 'keep').exists())
        self.assertEqual(outside.read_text(), 'user output')

    def test_live_process_prevents_cleanup(self):
        self.job.processes.add(object())
        with self.assertRaisesRegex(RuntimeError, 'owned processes'):
            self.job.cleanup()
        self.assertTrue(self.job.workspace.exists())

    def test_path_tampering_refuses_root_and_sibling(self):
        for path in (self.root, self.root.parent, self.root / 'outputs'):
            self.job.workspace = path
            with self.assertRaisesRegex(RuntimeError, 'Unsafe cleanup'):
                self.job.cleanup()

    def test_reparse_point_is_refused_without_following(self):
        owned = self.job.workspace / 'file'
        owned.write_text('x')
        real_stat = Path.lstat
        def altered(path):
            if path == owned:
                from types import SimpleNamespace
                return SimpleNamespace(st_file_attributes=0x400, st_mode=real_stat(path).st_mode)
            return real_stat(path)
        with patch.object(Path, 'lstat', altered):
            with self.assertRaisesRegex(RuntimeError, 'reparse point'):
                self.job.cleanup()
        self.assertTrue(owned.exists())

    def test_cancelled_publication_preserves_valid_destination(self):
        destination, pending = self.root / 'result', self.root / 'pending'
        destination.write_text('old valid result')
        pending.write_text('new result')
        self.job.request_stop()
        with self.assertRaises(RenderCancelled):
            self.job.publish(pending, destination)
        self.assertEqual(destination.read_text(), 'old valid result')

    def test_publish_before_stop_preserves_published_result(self):
        destination, pending = self.root / 'result', self.root / 'pending'
        pending.write_text('valid new result')
        self.job.publish(pending, destination)
        self.job.request_stop()
        self.job.cleanup()
        self.assertEqual(destination.read_text(), 'valid new result')

    def test_cancelled_staging_cleans_pending_file(self):
        destination = self.root / 'result.wav'
        destination.write_bytes(b'old')
        with bind_job(self.job), self.assertRaises(RenderCancelled):
            with pipeline._staged_output(destination) as pending:
                Path(pending).write_bytes(b'new')
                self.job.request_stop()
        self.assertEqual(destination.read_bytes(), b'old')
        self.assertFalse(list(self.root.glob('.reflow-*')))

    def test_cancel_before_launch_does_not_start_process(self):
        self.job.request_stop()
        with bind_job(self.job), patch('core.render_context.subprocess.Popen') as spawn:
            with self.assertRaises(RenderCancelled):
                run_process(['unused'])
            spawn.assert_not_called()

    def test_real_owned_process_cancel_keeps_unrelated_process_alive(self):
        unrelated = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
        started = threading.Event()
        real_spawn = subprocess.Popen
        def spawn(*args, **kwargs):
            process = real_spawn(*args, **kwargs)
            started.set()
            return process
        def run():
            with bind_job(self.job):
                return run_process([sys.executable, '-B', '-c', 'import time; time.sleep(60)'], timeout=10)
        try:
            with patch('core.render_context.subprocess.Popen', side_effect=spawn), ThreadPoolExecutor(1) as pool:
                future = pool.submit(run)
                self.assertTrue(started.wait(5))
                self.job.request_stop()
                with self.assertRaises(RenderCancelled):
                    future.result(timeout=10)
            self.assertIsNone(unrelated.poll())
            self.assertFalse(self.job.processes)
            self.job.cleanup()
        finally:
            if unrelated.poll() is None:
                unrelated.kill()
            unrelated.wait(timeout=5)

    def test_real_process_success_and_nonzero_failure(self):
        with bind_job(self.job):
            result = run_process([sys.executable, '-B', '-c', 'print("done")'],
                                 check=True, stdout=subprocess.PIPE, text=True, timeout=10)
            self.assertEqual(result.stdout.strip(), 'done')
            with self.assertRaises(subprocess.CalledProcessError):
                run_process([sys.executable, '-B', '-c', 'raise SystemExit(7)'], check=True, timeout=10)
        self.assertFalse(self.job.processes)

    def test_real_process_timeout_is_reaped(self):
        with bind_job(self.job), self.assertRaises(subprocess.TimeoutExpired):
            run_process([sys.executable, '-B', '-c', 'import time; time.sleep(60)'], timeout=.1)
        self.assertFalse(self.job.processes)

    def test_owned_descendant_is_terminated(self):
        import json
        import time
        import psutil
        pid_file = self.job.workspace / 'child.pid'
        script = ('import subprocess,sys,time; from pathlib import Path; '
                  'child=subprocess.Popen([sys.executable,"-B","-c","import time; time.sleep(60)"]); '
                  f'Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(60)')
        def run():
            with bind_job(self.job):
                run_process([sys.executable, '-B', '-c', script], timeout=15)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(run)
            deadline = time.monotonic() + 5
            while not pid_file.exists() and time.monotonic() < deadline:
                threading.Event().wait(.02)
            try:
                self.assertTrue(pid_file.exists())
                child = psutil.Process(int(pid_file.read_text()))
            finally:
                self.job.request_stop()
            with self.assertRaises(RenderCancelled):
                future.result(timeout=10)
        self.assertFalse(child.is_running())
        self.assertFalse(self.job.processes)

    def test_polling_wait_is_interruptible(self):
        self.job.request_stop()
        with bind_job(self.job), self.assertRaises(RenderCancelled):
            wait_or_cancel(60)

    def test_pipeline_workspace_uses_job_without_global_sweep(self):
        with bind_job(self.job), patch.object(pipeline, 'ModelRegistry'):
            subject = pipeline.ReflowPipeline()
        self.assertEqual(Path(subject.temp_dir), self.job.workspace)

    def test_cancelled_worker_does_not_enter_waiting_inference(self):
        lock = threading.Lock()
        acquired = threading.Event()
        fn = Mock()
        lock.acquire()
        def work():
            with bind_job(self.job):
                acquired.set()
                return pipeline.ReflowPipeline._maybe_locked(lock, fn)
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(work)
            self.assertTrue(acquired.wait(5))
            self.job.request_stop()
            lock.release()
            with self.assertRaises(RenderCancelled):
                future.result(timeout=5)
        fn.assert_not_called()


class LifecycleTests(unittest.TestCase):
    setUp = queue_fixture.RenderQueueTests.setUp
    add = queue_fixture.RenderQueueTests.add
    statuses = queue_fixture.RenderQueueTests.statuses
    terminal_events = queue_fixture.RenderQueueTests.terminal_events

    def test_blocked_call_keeps_workspace_until_worker_exits(self):
        entered, release = threading.Event(), threading.Event()
        workspace = []
        def generator(*args):
            workspace.append(current_job().workspace)
            (workspace[0] / 'in-use').write_text('active')
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test barrier timeout')
            yield 100, 'Done', str(self.output)
        self.pipeline.run.side_effect = generator
        first = self.add()
        self.add('next.mp4')
        self.bridge.start_render(first['input_path'], {}, queue_item_id=first['id'])
        worker = self.bridge._render_thread
        try:
            self.assertTrue(entered.wait(5))
            response = self.bridge.stop_render()
            self.assertTrue(response['stopping'])
            self.assertTrue((workspace[0] / 'in-use').exists())
            self.assertFalse(self.bridge.start_render('other', {})['ok'])
            names = [call.args[0] for call in self.events.call_args_list]
            self.assertIn('render_stopping', names)
            self.assertNotIn('render_stopped', names)
            self.state.clear.assert_not_called()
        finally:
            release.set()
            worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertFalse(workspace[0].exists())
        self.assertEqual(self.statuses(), ['cancelled', 'queued'])
        self.assertEqual(self.terminal_events(), [])
        self.assertEqual(sum(call.args[0] == 'render_stopped' for call in self.events.call_args_list), 1)

    def test_idle_stop_does_not_clean_or_emit_stopped(self):
        with patch.object(queue_fixture.janitor_module, 'Janitor') as janitor:
            response = self.bridge.stop_render()
        self.assertFalse(response['stopping'])
        janitor.assert_not_called()
        self.events.assert_not_called()

    def test_stuck_owned_process_blocks_restart(self):
        self.bridge._active_job = Mock(processes={object()})
        self.assertFalse(self.bridge.start_render('other', {})['ok'])

    def test_active_job_blocks_reset_and_model_removal(self):
        self.bridge._active_job = Mock()
        with patch.object(queue_fixture.janitor_module, 'Janitor') as janitor:
            self.assertFalse(self.bridge.factory_reset()['ok'])
            self.assertFalse(self.bridge.remove_model('anything')['ok'])
        janitor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
