"""Durable queue/recovery contracts, synthetic payloads and owned storage only."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core.queue_manager import QueueManager
from core import render_state
from dev import test_render_queue as queue_fixture
api = queue_fixture.api


class DurableQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'queue.json'
        self.warnings = []
        self.queue = QueueManager(str(self.path), self.warnings.append)

    def reload(self):
        return QueueManager(str(self.path), self.warnings.append)

    def test_restart_preserves_ids_order_frozen_params_and_drafts(self):
        params = {'lang': 'hi', 'nested': {'voice': 'one'}}
        first = self.queue.add_item('one.mp4', params)
        self.queue.add_item('two.mp4', params)
        self.queue.add_item('later.mp4')
        self.queue.claim_next()
        params['nested']['voice'] = 'changed'
        restored = self.reload()
        self.assertTrue(restored.is_paused())
        self.assertEqual([it['status'] for it in restored.get_items()], ['queued', 'queued', 'draft'])
        self.assertEqual(restored.get_items()[0]['id'], first['id'])
        self.assertEqual(restored.get_items()[1]['params']['nested']['voice'], 'one')
        self.assertIsNone(restored.claim_next())
        restored.set_paused(False)
        self.assertEqual(restored.claim_next().id, first['id'])

    def test_failed_atomic_save_rolls_back_and_retains_prior_disk(self):
        self.queue.add_item('one.mp4', {})
        before, raw = self.queue.get_items(), self.path.read_bytes()
        with patch('core.json_store.atomic_bytes', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.queue.add_item('two.mp4', {})
        self.assertEqual(self.queue.get_items(), before)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertIn('previous queue retained', self.warnings[-1])

    def test_corrupt_snapshot_preserved_without_starting_jobs(self):
        raw = b'{broken queue'
        self.path.write_bytes(raw)
        restored = self.reload()
        self.assertEqual(restored.get_items(), [])
        self.assertEqual(next(self.path.parent.glob('*.corrupt-*.bak')).read_bytes(), raw)
        self.assertTrue(self.warnings)

    def test_terminal_history_and_remove_survive_reload(self):
        one = self.queue.add_item('one.mp4', {})
        two = self.queue.add_item('two.mp4', {})
        self.queue.update_item(one['id'], status='failed', error='decode error')
        self.assertEqual(self.reload().get_items()[0]['error'], 'decode error')
        self.queue.clear_completed()
        self.assertEqual([it['id'] for it in self.reload().get_items()], [two['id']])
        self.queue.remove_item(two['id'])
        self.assertEqual(self.reload().get_items(), [])

    def test_progress_does_not_write_each_tick_but_terminal_state_does(self):
        one = self.queue.add_item('one.mp4', {})
        self.queue.claim_next()
        with patch.object(self.queue._store, 'replace', wraps=self.queue._store.replace) as save:
            self.queue.update_item(one['id'], progress=25, status_text='working')
            self.assertEqual(save.call_count, 0)
            self.queue.update_item(one['id'], status='completed', progress=100, output_path='output.mp4')
            self.assertEqual(save.call_count, 1)
        self.assertEqual(self.reload().get_items()[0]['status'], 'completed')

    def test_claim_is_one_commit_and_failed_claim_does_not_consume_job(self):
        self.queue.add_item('one.mp4', {})
        with patch.object(self.queue._store, 'replace', wraps=self.queue._store.replace) as save:
            self.queue.claim_next()
            self.assertEqual(save.call_count, 1)
        self.queue.update_item(self.queue.get_items()[0]['id'], status='queued')
        with patch.object(self.queue._store, 'replace', side_effect=OSError('unwritable')):
            with self.assertRaises(OSError):
                self.queue.claim_next()
        self.assertEqual(self.queue.get_items()[0]['status'], 'queued')

    def test_batch_acceptance_is_atomic_and_rejected_save_preserves_drafts(self):
        self.queue.add_item('one.mp4')
        self.queue.add_item('two.mp4')
        before, raw = self.queue.get_items(), self.path.read_bytes()
        with patch.object(self.queue._store, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.queue.prepare_batch({'lang': 'hi'}, 'video_dub')
        self.assertEqual(self.queue.get_items(), before)
        self.assertEqual(self.path.read_bytes(), raw)
        with patch.object(self.queue._store, 'replace', wraps=self.queue._store.replace) as save:
            self.queue.prepare_batch({'lang': 'hi'}, 'video_dub')
            self.assertEqual(save.call_count, 1)
        self.assertEqual([it['status'] for it in self.queue.get_items()], ['processing', 'queued'])


class LinkedRecoveryTests(unittest.TestCase):
    def setUp(self):
        queue_fixture.RenderQueueTests.setUp(self)
        # Replace the render-state mock with actual fixture storage.
        self.stack.enter_context(patch.object(api, 'render_state', render_state))
        self.stack.enter_context(patch.object(render_state, 'STATE_PATH', str(Path(self.temp) / 'render.json')))
        self.path = Path(self.temp) / 'queue.json'
        self.bridge.queue_manager = QueueManager(str(self.path))
        one = self.bridge.add_queue_item('one.mp4', {'lang': 'hi'})
        self.bridge.add_queue_item('two.mp4', {'lang': 'fr'})
        self.first_id = one['id']
        self.bridge.queue_manager.claim_next()
        render_state.mark_started(one['input_path'], one['params'], one['template_id'], queue_item_id=one['id'])
        self.bridge.queue_manager = QueueManager(str(self.path))
        self.offer = self.bridge.get_interrupted_render()

    def test_token_resume_runs_original_once_then_leaves_rest_paused(self):
        self.assertTrue(self.bridge.resume_interrupted_render(self.offer['recovery_token'])['ok'])
        self.bridge._render_thread.join(5)
        self.assertFalse(self.bridge._render_thread.is_alive())
        self.assertEqual([it['status'] for it in self.bridge.get_queue_items()], ['completed', 'queued'])
        self.assertEqual(self.bridge.get_queue_items()[0]['id'], self.first_id)
        self.assertTrue(self.bridge.queue_manager.is_paused())
        self.assertIsNone(self.bridge.get_interrupted_render())
        self.assertTrue(self.bridge.resume_queue_batch()['ok'])
        self.bridge._render_thread.join(5)
        self.assertEqual([it['status'] for it in self.bridge.get_queue_items()], ['completed', 'completed'])
        self.assertEqual(self.pipeline.run.call_count, 2)

    def test_stale_offer_or_changed_accepted_params_cannot_resume(self):
        self.assertFalse(self.bridge.resume_interrupted_render('stale')['ok'])
        self.bridge.queue_manager.update_item(self.first_id, params={'lang': 'different'})
        self.assertFalse(self.bridge.resume_interrupted_render(self.offer['recovery_token'])['ok'])
        self.assertFalse(self.pipeline.run.called)
        self.assertEqual(render_state.get_interrupted(), self.offer)

    def test_failed_thread_start_preserves_recovery_and_accepted_queue(self):
        before = self.bridge.get_queue_items()
        with patch.object(api.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('start denied')
            self.assertFalse(self.bridge.resume_interrupted_render(self.offer['recovery_token'])['ok'])
        self.assertEqual(self.bridge.get_queue_items(), before)
        self.assertEqual(render_state.get_interrupted(), self.offer)
        self.assertEqual(QueueManager(str(self.path)).get_items(), before)

    def test_explicit_discard_cancels_only_linked_job(self):
        self.assertFalse(self.bridge.discard_interrupted_render('stale')['ok'])
        self.assertTrue(self.bridge.discard_interrupted_render(self.offer['recovery_token'])['ok'])
        self.assertEqual([it['status'] for it in self.bridge.get_queue_items()], ['cancelled', 'queued'])
        self.assertIsNone(render_state.get_interrupted())

    def test_terminal_commit_before_marker_cleanup_does_not_offer_duplicate(self):
        self.bridge.queue_manager.update_item(self.first_id, status='completed', progress=100)
        self.assertIsNone(self.bridge.get_interrupted_render())
        self.assertFalse(self.bridge.resume_interrupted_render(self.offer['recovery_token'])['ok'])

    def test_terminal_save_failure_halts_batch_without_skipping_unsaved_job(self):
        original = self.bridge.queue_manager._store.replace
        def save(candidate):
            if candidate['items'][0]['status'] in ('completed', 'failed'):
                raise OSError('disk full during completion')
            return original(candidate)
        with patch.object(self.bridge.queue_manager._store, 'replace', side_effect=save):
            self.assertTrue(self.bridge.resume_interrupted_render(self.offer['recovery_token'])['ok'])
            self.bridge._render_thread.join(5)
        self.assertFalse(self.bridge._render_thread.is_alive())
        session = self.bridge.get_session_state()
        self.assertEqual(self.pipeline.run.call_count, 1)
        self.assertEqual([it['status'] for it in session['queue']], ['queued', 'queued'])
        self.assertTrue(session['paused'])
        self.assertFalse(session['busy'])
        self.assertEqual(session['render']['status'], 'error')
        self.assertIn('disk full during completion', session['render']['errorMessage'])
        self.assertEqual([it['status'] for it in QueueManager(str(self.path)).get_items()], ['queued', 'queued'])


if __name__ == '__main__':
    unittest.main()
