"""Exercise the real bridge lifecycle with simulated pipelines and no AI jobs."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
from bridge import api
from core import janitor as janitor_module
from core.queue_manager import QueueManager


class RenderQueueTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(api.config, "TEMP_PATH", self.temp))
        self.output = Path(self.temp) / "output.mp4"
        self.output.write_bytes(b"simulated output")
        # Avoid GUI, model registry, and hardware initialization. These are the
        # real bridge methods; only their external effects are substituted.
        self.bridge = api.PythonBridge.__new__(api.PythonBridge)
        self.bridge._render_thread = None
        self.bridge._render_lock = threading.Lock()
        self.bridge._render_killed = False
        self.bridge.queue_manager = QueueManager()
        self.bridge.settings = {"auto_cleanup_temp": False}
        self.stack.enter_context(patch.object(self.bridge, "_template_kwargs", return_value={}))
        self.events = self.stack.enter_context(patch.object(api.push, "emit"))
        self.state = self.stack.enter_context(patch.object(api, "render_state"))
        self.pipeline = Mock()
        self.stack.enter_context(patch.dict(sys.modules, {
            "pipeline": SimpleNamespace(ReflowPipeline=lambda: self.pipeline)
        }))
        self.pipeline.run.side_effect = lambda *args: iter_render(self.output)

    def add(self, name="input.mp4"):
        return self.bridge.add_queue_item(name, {}, "video_dub")

    def run_item(self, item):
        self.bridge._run_render(item["input_path"], item["params"], item["template_id"], item["id"])

    def statuses(self):
        return [item["status"] for item in self.bridge.get_queue_items()]

    def terminal_events(self):
        return [call.args for call in self.events.call_args_list
                if call.args[0] in ("render_finished", "render_error")]

    def test_success_records_output_and_finishes_once(self):
        self.run_item(self.add())
        item, = self.bridge.get_queue_items()
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["progress"], 100)
        self.assertEqual(item["output_path"], str(self.output))
        self.assertIsNone(item["error"])
        self.assertEqual(self.terminal_events(), [("render_finished", {"outputPath": str(self.output)})])

    def test_each_queued_job_emits_started_to_reset_source_feedback(self):
        first = self.add('one.mp4')
        self.add('two.mp4')
        self.run_item(first)
        started = [call.args[1]['inputPath'] for call in self.events.call_args_list if call.args[0] == 'render_started']
        self.assertEqual(started, ['one.mp4', 'two.mp4'])

    def test_source_feedback_is_forwarded_and_suppressed_after_stop(self):
        self.bridge._run_render_inner('input.mp4', {})
        self.events.reset_mock()
        self.pipeline.source_language_callback({'source_name': 'Hindi'})
        self.events.assert_any_call('source_language', {'source_name': 'Hindi'})
        self.assertEqual(self.bridge.get_session_state()['render']['sourceFeedback'], {'source_name': 'Hindi'})
        self.bridge._render_killed = True
        self.events.reset_mock()
        self.pipeline.source_language_callback({'source_name': 'French'})
        self.events.assert_not_called()

    def test_failure_is_failed_and_next_job_completes(self):
        first = self.add("bad.mp4")
        self.add("good.mp4")
        def run(template, path, kwargs):
            if path == "bad.mp4":
                raise RuntimeError("decoder failed")
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.run_item(first)
        self.assertEqual(self.statuses(), ["failed", "completed"])
        self.assertEqual(self.bridge.get_queue_items()[0]["error"], "decoder failed")
        self.assertEqual([event[0] for event in self.terminal_events()], ["render_error", "render_finished"])

    def test_no_output_is_failed(self):
        self.pipeline.run.side_effect = lambda *args: iter_render(None)
        self.run_item(self.add())
        self.assertEqual(self.statuses(), ["failed"])
        self.assertIn("without output", self.bridge.get_queue_items()[0]["error"])
        self.assertEqual(len(self.terminal_events()), 1)

    def test_missing_output_is_failed(self):
        self.output.unlink()
        self.run_item(self.add())
        self.assertEqual(self.statuses(), ["failed"])
        self.assertIn("missing or empty", self.bridge.get_queue_items()[0]["error"])

    def test_empty_output_is_failed(self):
        self.output.write_bytes(b"")
        self.run_item(self.add())
        self.assertEqual(self.statuses(), ["failed"])

    def test_batch_runs_in_order_on_one_actual_worker(self):
        first = self.add("first.mp4")
        self.add("second.mp4")
        workers, paths = [], []
        def run(template, path, kwargs):
            workers.append(threading.current_thread())
            paths.append(path)
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        result = self.bridge.start_render(first["input_path"], {}, queue_item_id=first["id"])
        self.assertTrue(result["ok"])
        self.bridge._render_thread.join(3)
        self.assertFalse(self.bridge._render_thread.is_alive())
        self.assertEqual(self.statuses(), ["completed", "completed"])
        self.assertEqual(paths, ["first.mp4", "second.mp4"])
        self.assertEqual(workers, [self.bridge._render_thread] * 2)
        self.assertEqual(self.state.mark_started.call_count, 2)
        self.assertEqual(self.state.clear.call_count, 2)

    def test_pause_allows_current_job_but_leaves_next_queued(self):
        first = self.add()
        self.add("next.mp4")
        self.bridge.set_queue_paused(True)
        self.run_item(first)
        self.assertEqual(self.statuses(), ["completed", "queued"])

    def test_stop_cancels_current_and_does_not_advance_or_finish(self):
        first = self.add()
        self.add("next.mp4")
        closed = []
        stop_errors = []
        def cancelled(*args):
            try:
                yield 10, "Transcribing", None
                try:
                    self.bridge.stop_render()
                except Exception as exc:
                    stop_errors.append(repr(exc))
                    raise
                yield 100, "Done", str(self.output)
            finally:
                closed.append(True)
        self.pipeline.run.side_effect = cancelled
        with patch.object(janitor_module, "Janitor") as janitor:
            self.run_item(first)
        self.assertEqual(self.statuses(), ["cancelled", "queued"])
        self.assertEqual(self.terminal_events(), [])
        self.assertEqual(closed, [True])
        self.assertEqual(stop_errors, [])
        janitor.return_value.kill_rogue_processes.assert_not_called()
        janitor.return_value.sweep.assert_not_called()

    def test_stop_at_generator_exhaustion_does_not_finish(self):
        def cancelled(*args):
            yield 100, "Done", str(self.output)
            self.bridge._render_killed = True
        self.pipeline.run.side_effect = cancelled
        self.run_item(self.add())
        self.assertEqual(self.statuses(), ["cancelled"])
        self.assertEqual(self.terminal_events(), [])

    def test_cleanup_failure_does_not_change_result_or_block_next(self):
        first = self.add()
        self.add("next.mp4")
        self.bridge.settings["auto_cleanup_temp"] = True
        with patch.object(api.RenderContext, "cleanup", side_effect=RuntimeError("file busy")) as cleanup:
            self.run_item(first)
        self.assertEqual(self.statuses(), ["completed", "completed"])
        self.assertEqual(cleanup.call_count, 2)
        self.assertTrue(any("cleanup failed" in str(call) for call in self.events.call_args_list))

    def test_state_cleanup_failure_does_not_block_next(self):
        first = self.add()
        self.add("next.mp4")
        self.state.clear.side_effect = OSError("locked")
        self.run_item(first)
        self.assertEqual(self.statuses(), ["completed", "completed"])

    def test_stop_during_cleanup_preserves_already_completed_result(self):
        first = self.add()
        self.add("next.mp4")
        self.bridge.settings["auto_cleanup_temp"] = True
        with patch.object(api.RenderContext, "cleanup", side_effect=lambda: setattr(self.bridge, "_render_killed", True)):
            self.run_item(first)
        self.assertEqual(self.statuses(), ["completed", "queued"])
        self.assertEqual([event[0] for event in self.terminal_events()], ["render_finished"])

    def test_direct_render_preserves_finished_event(self):
        self.bridge._run_render("direct.mp4", {}, "video_dub")
        self.assertEqual(self.bridge.get_queue_items(), [])
        self.assertEqual(self.terminal_events(), [("render_finished", {"outputPath": str(self.output)})])

    def test_active_worker_rejects_overlapping_start(self):
        entered, release = threading.Event(), threading.Event()
        def blocking(*args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test worker timed out")
            return iter_render(self.output)
        self.pipeline.run.side_effect = blocking
        self.assertTrue(self.bridge.start_render("first.mp4", {})["ok"])
        try:
            self.assertTrue(entered.wait(3))
            original_worker = self.bridge._render_thread
            self.assertFalse(self.bridge.start_render("second.mp4", {})["ok"])
            self.assertIs(self.bridge._render_thread, original_worker)
        finally:
            release.set()
            self.bridge._render_thread.join(3)
        self.assertFalse(self.bridge._render_thread.is_alive())
        self.assertTrue(self.bridge.start_render("later.mp4", {})["ok"])
        self.bridge._render_thread.join(3)
        self.assertFalse(self.bridge._render_thread.is_alive())


def iter_render(output):
    yield 20, "Transcribing", None
    yield 100, "Done", str(output) if output is not None else None


if __name__ == "__main__":
    unittest.main()
