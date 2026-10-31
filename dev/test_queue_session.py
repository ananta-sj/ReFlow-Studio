"""Managed UI-equivalent batch and snapshot contracts with simulated pipelines."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch

from dev import test_render_queue as queue_fixture
from core.queue_manager import QueueManager
from core.session_state import SessionState

api = queue_fixture.api
iter_render = queue_fixture.iter_render


class BatchSessionTests(unittest.TestCase):
    setUp = queue_fixture.RenderQueueTests.setUp

    def wait(self):
        self.bridge._render_thread.join(5)
        self.assertFalse(self.bridge._render_thread.is_alive())

    def items(self):
        return self.bridge.get_session_state()['queue']

    def test_three_drafts_run_once_with_middle_failure(self):
        self.assertTrue(self.bridge.add_queue_drafts(['one.mp4', 'bad.mp4', 'three.mp4'])['ok'])
        self.assertEqual([it['status'] for it in self.items()], ['draft'] * 3)
        paths = []
        def run(template, path, kwargs):
            paths.append(path)
            if path == 'bad.mp4':
                raise RuntimeError('bad input')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.assertTrue(self.bridge.start_queue_batch({})['ok'])
        self.wait()
        self.assertEqual(paths, ['one.mp4', 'bad.mp4', 'three.mp4'])
        self.assertEqual([it['status'] for it in self.items()], ['completed', 'failed', 'completed'])
        self.assertEqual(self.items()[1]['error'], 'bad input')
        self.assertFalse(self.bridge.resume_queue_batch()['ok'])
        self.assertFalse(self.bridge.get_session_state()['busy'])

    def test_batch_params_are_copied_and_new_drafts_do_not_autostart(self):
        entered, release = threading.Event(), threading.Event()
        seen = []
        def run(template, path, kwargs):
            seen.append(path)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4', 'two.mp4'])
        params = {'lang': 'fr', 'nested': {'value': 1}}
        self.assertTrue(self.bridge.start_queue_batch(params)['ok'])
        try:
            self.assertTrue(entered.wait(5))
            params['lang'], params['nested']['value'] = 'de', 99
            self.bridge.add_queue_drafts(['later.mp4'])
            records = self.items()
            self.assertEqual(records[1]['params']['lang'], 'fr')
            self.assertEqual(records[1]['params']['nested']['value'], 1)
            records[1]['params']['lang'] = 'fake'
            self.assertEqual(self.items()[1]['params']['lang'], 'fr')
        finally:
            release.set()
            self.wait()
        self.assertEqual(seen, ['one.mp4', 'two.mp4'])
        self.assertEqual(self.items()[2]['status'], 'draft')

    def test_pause_then_resume_preserves_pending_jobs_and_settings(self):
        entered, release = threading.Event(), threading.Event()
        paths = []
        def run(template, path, kwargs):
            paths.append(path)
            if path == 'one.mp4':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4', 'two.mp4'])
        self.bridge.start_queue_batch({'lang': 'fr'})
        try:
            self.assertTrue(entered.wait(5))
            self.bridge.set_queue_paused(True)
            self.assertTrue(self.bridge.get_session_state()['paused'])
        finally:
            release.set()
            self.wait()
        self.assertEqual([it['status'] for it in self.items()], ['completed', 'queued'])
        self.assertTrue(self.bridge.resume_queue_batch()['ok'])
        self.wait()
        self.assertEqual(paths, ['one.mp4', 'two.mp4'])
        self.assertEqual(self.items()[1]['params']['lang'], 'fr')

    def test_stop_cancels_current_leaves_rest_and_can_resume(self):
        entered, release = threading.Event(), threading.Event()
        def run(template, path, kwargs):
            if path == 'one.mp4':
                entered.set()
                if not release.wait(5):
                    raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4', 'two.mp4'])
        self.bridge.start_queue_batch({})
        try:
            self.assertTrue(entered.wait(5))
            self.bridge.stop_render()
            snapshot = self.bridge.get_session_state()
            self.assertTrue(snapshot['busy'])
            self.assertEqual(snapshot['render']['status'], 'stopping')
            self.assertFalse(self.bridge.resume_queue_batch()['ok'])
        finally:
            release.set()
            self.wait()
        self.assertEqual([it['status'] for it in self.items()], ['cancelled', 'queued'])
        self.assertTrue(self.bridge.resume_queue_batch()['ok'])
        self.wait()
        self.assertEqual([it['status'] for it in self.items()], ['cancelled', 'completed'])

    def test_repeated_batch_start_rejected_without_consuming_drafts(self):
        entered, release = threading.Event(), threading.Event()
        def run(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4'])
        self.bridge.start_queue_batch({})
        try:
            self.assertTrue(entered.wait(5))
            self.bridge.add_queue_drafts(['later.mp4'])
            before = self.items()
            self.assertFalse(self.bridge.start_queue_batch({'lang': 'de'})['ok'])
            self.assertEqual(self.items(), before)
            self.assertEqual(self.bridge.get_session_state()['render']['inputPath'], 'one.mp4')
        finally:
            release.set()
            self.wait()

    def test_worker_start_failure_restores_drafts_and_pause(self):
        self.bridge.add_queue_drafts(['one.mp4'])
        self.bridge.set_queue_paused(True)
        before = self.items()
        with patch.object(api.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('cannot start')
            result = self.bridge.start_queue_batch({'lang': 'fr'})
        self.assertFalse(result['ok'])
        self.assertEqual(self.items(), before)
        self.assertTrue(self.bridge.get_session_state()['paused'])
        self.assertFalse(self.bridge.get_session_state()['busy'])

    def test_failed_start_preserves_previous_output_snapshot(self):
        self.bridge._emit_render('render_finished', {'outputPath': str(self.output)})
        before = self.bridge.get_session_state()['render']
        with patch.object(api.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('cannot start')
            result = self.bridge.start_render('one.mp4', {})
        self.assertFalse(result['ok'])
        self.assertEqual(self.bridge.get_session_state()['render'], before)

    def test_invalid_batch_template_and_empty_queue_leave_state(self):
        self.assertFalse(self.bridge.start_queue_batch({})['ok'])
        self.bridge.add_queue_drafts(['one.mp4'])
        self.assertFalse(self.bridge.start_queue_batch({}, 'audio_dub')['ok'])
        self.assertEqual(self.items()[0]['status'], 'draft')

    def test_changed_confirmation_ids_rejected_without_freezing_jobs(self):
        self.bridge.add_queue_drafts(['one.mp4'])
        ids = [it['id'] for it in self.items()]
        self.bridge.add_queue_drafts(['two.mp4'])
        result = self.bridge.start_queue_batch({}, expected_ids=ids)
        self.assertFalse(result['ok'])
        self.assertIn('changed', result['message'])
        self.assertEqual([it['status'] for it in self.items()], ['draft', 'draft'])
        current_ids = [it['id'] for it in self.items()]
        self.assertTrue(self.bridge.start_queue_batch({}, expected_ids=current_ids)['ok'])
        self.wait()
        self.assertEqual([it['status'] for it in self.items()], ['completed', 'completed'])

    def test_simultaneous_start_accepts_one_worker(self):
        gate = threading.Barrier(2)
        entered, release = threading.Event(), threading.Event()
        paths = []
        def run(template, path, kwargs):
            paths.append(path)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4'])
        def start():
            gate.wait(timeout=5)
            return self.bridge.start_queue_batch({})
        try:
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda _: start(), range(2)))
            self.assertEqual(sum(result['ok'] for result in results), 1)
            self.assertTrue(entered.wait(5))
        finally:
            release.set()
            self.wait()
        self.assertEqual(paths, ['one.mp4'])

    def test_lost_snapshot_notification_recovers_with_read(self):
        self.bridge.add_queue_drafts(['one.mp4'])
        def emit(event, payload):
            if event == 'session_state':
                raise RuntimeError('notification unavailable')
        self.events.side_effect = emit
        self.assertTrue(self.bridge.start_queue_batch({})['ok'])
        self.wait()
        snapshot = self.bridge.get_session_state()
        self.assertEqual(snapshot['queue'][0]['status'], 'completed')
        self.assertFalse(snapshot['busy'])
        self.assertEqual(snapshot['render']['outputPath'], str(self.output))

    def test_active_removal_refused_and_pending_removal_applies_by_id(self):
        entered, release = threading.Event(), threading.Event()
        def run(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.bridge.add_queue_drafts(['one.mp4', 'two.mp4'])
        self.bridge.start_queue_batch({})
        try:
            self.assertTrue(entered.wait(5))
            first, second = self.items()
            self.assertFalse(self.bridge.remove_queue_item(first['id'])['ok'])
            self.assertTrue(self.bridge.remove_queue_item(second['id'])['ok'])
        finally:
            release.set()
            self.wait()
        self.assertEqual(len(self.items()), 1)
        self.bridge.add_queue_drafts(['new.mp4'])
        self.bridge.clear_completed_queue()
        self.assertEqual([it['input_path'] for it in self.items()], ['new.mp4'])

    def test_single_audio_job_does_not_consume_video_queue(self):
        self.bridge.add_queue_item('queued.mp4', {})
        self.bridge.add_queue_drafts(['draft.mp4'])
        self.assertTrue(self.bridge.start_render('audio.wav', {}, 'audio_dub')['ok'])
        self.wait()
        self.assertEqual([it['status'] for it in self.items()], ['queued', 'draft'])

    def test_frontend_reconnect_does_not_offer_active_job_as_interrupted(self):
        entered, release = threading.Event(), threading.Event()
        def run(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return iter_render(self.output)
        self.pipeline.run.side_effect = run
        self.state.get_interrupted.return_value = {'input_path': 'previous.mp4'}
        self.bridge.start_render('active.mp4', {})
        try:
            self.assertTrue(entered.wait(5))
            self.assertIsNone(self.bridge.get_interrupted_render())
            self.state.get_interrupted.assert_not_called()
        finally:
            release.set()
            self.wait()
        self.assertEqual(self.bridge.get_interrupted_render(), {'input_path': 'previous.mp4'})

    def test_busy_remains_true_during_cleanup_and_preserves_history(self):
        entered, release = threading.Event(), threading.Event()
        self.bridge.settings['auto_cleanup_temp'] = True
        def cleanup():
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
        self.bridge.add_queue_drafts(['one.mp4'])
        with patch.object(api.RenderContext, 'cleanup', side_effect=cleanup):
            self.bridge.start_queue_batch({})
            try:
                self.assertTrue(entered.wait(5))
                snapshot = self.bridge.get_session_state()
                self.assertTrue(snapshot['busy'])
                self.assertEqual(snapshot['render']['status'], 'finished')
                job_id = self.items()[0]['id']
                self.assertFalse(self.bridge.remove_queue_item(job_id)['ok'])
                self.bridge.clear_completed_queue()
                self.assertEqual(len(self.items()), 1)
                self.assertFalse(self.bridge.start_render('other.wav', {})['ok'])
            finally:
                release.set()
                self.wait()
        self.assertFalse(self.bridge.get_session_state()['busy'])

    def test_snapshot_revisions_source_feedback_and_returned_copy(self):
        initial = self.bridge.get_session_state()
        self.bridge._emit_render('render_started', {'inputPath': 'one.mp4'})
        self.bridge._emit_render('source_language', {'source_name': 'Hindi'})
        self.bridge._emit_render('progress', {'percent': 42, 'status': 'Transcribing'})
        later = self.bridge.get_session_state()
        self.assertGreater(later['revision'], initial['revision'])
        self.assertEqual(later['render']['sourceFeedback'], {'source_name': 'Hindi'})
        later['render']['sourceFeedback']['source_name'] = 'fake'
        self.assertEqual(self.bridge.get_session_state()['render']['sourceFeedback']['source_name'], 'Hindi')

    def test_late_progress_does_not_overwrite_stopping_queue_progress(self):
        item = self.bridge.add_queue_item('one.mp4', {})
        self.bridge._current_queue_item = item['id']
        self.bridge._emit_render('render_started', {'inputPath': 'one.mp4'})
        self.bridge._emit_render('progress', {'percent': 10, 'status': 'Working'})
        self.bridge._emit_render('render_stopping', {})
        self.bridge._emit_render('progress', {'percent': 99, 'status': 'Late progress'})
        snapshot = self.bridge.get_session_state()
        self.assertEqual(snapshot['render']['percent'], 10)
        self.assertEqual(snapshot['queue'][0]['progress'], 10)
        self.assertEqual(snapshot['queue'][0]['status_text'], 'Working')

    def test_legacy_queued_start_validates_id_and_retains_settings(self):
        item = self.bridge.add_queue_item('one.mp4', {'lang': 'fr'})
        self.assertFalse(self.bridge.start_render('wrong.mp4', {}, queue_item_id=item['id'])['ok'])
        self.assertTrue(self.bridge.start_render('one.mp4', {'lang': 'fake'}, queue_item_id=item['id'])['ok'])
        self.wait()
        self.assertEqual(self.items()[0]['params']['lang'], 'fr')


class QueueClaimTests(unittest.TestCase):
    def test_concurrent_claims_are_unique_and_snapshots_are_copies(self):
        queue = QueueManager()
        params = {'nested': {'value': 1}}
        for index in range(8):
            queue.add_item(str(index), params)
        params['nested']['value'] = 9
        with ThreadPoolExecutor(8) as pool:
            jobs = list(pool.map(lambda _: queue.claim_next(), range(8)))
        self.assertEqual(len({job.id for job in jobs}), 8)
        self.assertTrue(all(job.params['nested']['value'] == 1 for job in jobs))
        self.assertIsNone(queue.claim_next())

    def test_duplicate_pending_drafts_are_not_added(self):
        queue = QueueManager()
        first = queue.add_item('one')
        second = queue.add_item('one')
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(queue.get_items()), 1)

    def test_stopping_snapshot_ignores_late_progress(self):
        session = SessionState()
        session.event('render_started', {'inputPath': 'one'})
        session.event('render_stopping', {})
        session.event('progress', {'percent': 100, 'status': 'Done'})
        state = session.snapshot([], True, True)
        self.assertEqual(state['render']['status'], 'stopping')
        self.assertEqual(state['render']['percent'], 0)


if __name__ == '__main__':
    unittest.main()
