"""Owned Marketplace failure/retry checks; no network or models."""
import json
import unittest
from unittest.mock import patch
from dev import test_deletion_safety as fixtures
api = fixtures.api
from core.model_registry import ModelRegistry


class MarketplaceRecoveryTests(unittest.TestCase):
    setUp = fixtures.DeletionSafetyTests.setUp

    def test_missing_hub_creates_no_registry_entry_or_job(self):
        with patch('importlib.util.find_spec', return_value=None), patch.object(api.threading, 'Thread') as thread:
            result = self.bridge.add_local_model('stt', 'https://huggingface.co/example/repo', 'Fixture')
        self.assertFalse(result['ok'])
        self.assertIn('download', result['message'].lower())
        self.assertEqual(self.bridge.registry.list(), [])
        thread.assert_not_called()
        self.assertFalse(self.bridge._active_downloads)

    def test_cloud_persistence_failure_never_returns_os_details(self):
        with patch.object(api,'set_credential'), patch.object(self.bridge.registry,'add',side_effect=OSError('SENTINEL_PRIVATE_PATH')):
            result=self.bridge.add_cloud_model('voice','Fixture','https://example.test','secret','elevenlabs_sts',{'voice_id':'fixture'})
        self.assertFalse(result['ok']);self.assertNotIn('SENTINEL',str(result));self.credentials.assert_called_once()

    def test_failure_is_safe_and_persistent(self):
        entry = self.bridge.registry.add('stt', 'local_file', 'Fixture', source_url='https://example.test/model.bin')
        with patch.object(api, 'download_with_progress', side_effect=RuntimeError('token=SENTINEL https://private.test/key C:/private/path')):
            self.bridge._run_local_download(entry['id'], 'stt', entry['source_url'])
        saved = ModelRegistry().get(entry['id'])
        self.assertEqual(saved['status'], 'error')
        self.assertEqual(saved['meta']['download_error']['code'], 'transfer_failed')
        text = json.dumps(saved['meta']) + str(self.events.call_args_list)
        self.assertNotIn('SENTINEL', text)
        self.assertNotIn('private.test', text)
        self.assertNotIn('C:/private/path', text)

    def test_cancel_is_not_persisted_as_failure(self):
        entry = self.bridge.registry.add('stt', 'local_file', 'Fixture')
        with patch.object(api, 'download_with_progress', side_effect=api.RenderCancelled('cancel')):
            self.bridge._run_local_download(entry['id'], 'stt', 'https://example.test/model.bin')
        self.assertEqual(self.bridge.registry.get(entry['id'])['status'], 'not_downloaded')
        self.assertNotIn('download_error', self.bridge.registry.get(entry['id'])['meta'])

    def test_unusable_worker_creates_no_registry_entry(self):
        with patch.dict(api.os.environ, {'REFLOW_WORKER_PYTHON': str(self.root/'missing-python.exe')}), patch.object(api.threading, 'Thread'):
            result=self.bridge.add_local_model('stt','https://huggingface.co/example/repo','Fixture')
        self.assertFalse(result['ok'])
        self.assertEqual(self.bridge.registry.list(), [])

    def test_direct_file_does_not_require_hub(self):
        with patch('importlib.util.find_spec', return_value=None), patch.object(api.threading, 'Thread') as thread:
            result = self.bridge.add_local_model('stt', 'https://example.test/model.bin', 'Fixture')
        self.assertTrue(result['ok'])
        thread.return_value.start.assert_called_once()
        for job in getattr(self.bridge, '_download_contexts', {}).values(): job.cleanup()

    def test_retry_keeps_identity_and_starts_only_one_owned_worker(self):
        entry = self.bridge.registry.add('stt', 'local_file', 'Fixture', source_url='https://example.test/model.bin', status='error', custom_instructions='preserve', meta={'download_error': {'code':'network_error','message':'safe'}})
        with patch.object(api.threading, 'Thread') as thread:
            first = self.bridge.retry_model_download(entry['id'])
            second = self.bridge.retry_model_download(entry['id'])
        self.assertTrue(first['ok']); self.assertFalse(second['ok'])
        self.assertEqual(len(self.bridge.registry.list()), 1)
        saved = self.bridge.registry.get(entry['id'])
        self.assertEqual(saved['custom_instructions'], 'preserve')
        self.assertNotIn('download_error', saved['meta'])
        self.assertTrue(saved['meta']['download_attempt_id'])
        thread.return_value.start.assert_called_once()
        for job in self.bridge._download_contexts.values(): job.cleanup()

    def test_equivalent_recommendation_keeps_its_preset(self):
        with patch.object(api,'require_hub_transport'), patch.object(api.threading,'Thread'):
            result=self.bridge.add_local_model('filter','https://huggingface.co/Falconsai/nsfw_image_detection/?download=true','Fixture')
        self.assertTrue(result['ok']);self.assertEqual(result['model']['request_preset'],'image_classifier')
        for job in self.bridge._download_contexts.values():job.cleanup()

    def test_startup_cleanup_failure_still_persists_safe_error(self):
        entry=self.bridge.registry.add('stt','local_file','Fixture',source_url='https://example.test/model.bin',status='error')
        with patch.object(api.threading.Thread,'start',side_effect=RuntimeError('SENTINEL')), patch.object(api.RenderContext,'cleanup',side_effect=OSError('SENTINEL')):
            result=self.bridge.retry_model_download(entry['id'])
        self.assertFalse(result['ok']);self.assertEqual(self.bridge.registry.get(entry['id'])['status'],'error')
        self.assertNotIn('SENTINEL',str(result))

    def test_retry_thread_start_failure_releases_ownership_and_is_safe(self):
        entry = self.bridge.registry.add('stt', 'local_file', 'Fixture', source_url='https://example.test/model.bin', status='error')
        with patch.object(api.threading.Thread, 'start', side_effect=RuntimeError('SENTINEL')):
            result = self.bridge.retry_model_download(entry['id'])
        self.assertFalse(result['ok']); self.assertNotIn('SENTINEL', str(result))
        self.assertFalse(self.bridge._active_downloads)
        self.assertFalse(self.bridge._download_contexts)
        self.assertEqual(self.bridge.registry.get(entry['id'])['status'], 'error')

    def test_retry_rejects_invalid_and_ready_or_cloud_models(self):
        for status, kind in [('installed','local_file'),('error','cloud_api')]:
            entry = self.bridge.registry.add('stt', kind, 'Fixture', status=status)
            self.assertFalse(self.bridge.retry_model_download(entry['id'])['ok'])
        self.assertFalse(self.bridge.retry_model_download('../outside')['ok'])

    def test_retry_preserves_previous_attempt_files(self):
        entry = self.bridge.registry.add('stt','local_file','Fixture',source_url='https://example.test/model.bin',status='error')
        path = self.root/'models/_downloads'/entry['id']/'old/model.bin'
        path.parent.mkdir(parents=True);path.write_bytes(b'keep')
        with patch.object(api.threading, 'Thread'):
            result = self.bridge.retry_model_download(entry['id'])
        self.assertTrue(result['ok']);self.assertEqual(path.read_bytes(), b'keep')
        for job in self.bridge._download_contexts.values(): job.cleanup()

    def test_cancel_cannot_overwrite_terminal_adapter_metadata(self):
        entry=self.bridge.registry.add('stt','local_file','Fixture',source_url='https://example.test/model.bin',status='error')
        with patch.object(api.threading,'Thread'):self.bridge.retry_model_download(entry['id'])
        original=self.bridge.registry.get
        def interleave(model_id):
            old=original(model_id)
            self.bridge.registry.update(model_id,status='installed',meta={'adapter':'fixture','checkpoint':'keep'})
            return old
        with patch.object(self.bridge.registry,'get',side_effect=interleave):self.bridge.cancel_model_download(entry['id'])
        saved=original(entry['id']);self.assertEqual(saved['status'],'installed');self.assertEqual(saved['meta'],{'adapter':'fixture','checkpoint':'keep'})
        for job in self.bridge._download_contexts.values():job.cleanup()

    def test_cancel_is_visible_and_releases_only_after_worker_exit(self):
        entry=self.bridge.registry.add('stt','local_file','Fixture',source_url='https://example.test/model.bin',status='error')
        with patch.object(api.threading,'Thread'):
            self.bridge.retry_model_download(entry['id'])
        self.assertTrue(self.bridge.cancel_model_download(entry['id'])['ok'])
        self.assertNotIn('cancel_requested', self.bridge.registry.get(entry['id'])['meta'])
        self.assertTrue(self.bridge.list_models('stt')[0]['meta']['cancel_requested'])
        self.assertFalse(self.bridge.retry_model_download(entry['id'])['ok'])
        for job in self.bridge._download_contexts.values():job.cleanup()


if __name__ == '__main__':
    unittest.main()
