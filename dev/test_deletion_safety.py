"""Deletion safety checks against disposable storage; never real user files."""
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import Mock, patch

from dev.test_render_queue import api
from core import deletion_plan, model_registry, credential_store


class DeletionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=Path(api.config.BASE_DIR) / 'temp')))
        for name, value in {'BASE_DIR': self.root, 'TEMP_PATH': self.root / 'temp',
                            'OUTPUT_PATH': self.root / 'outputs', 'MODELS_DIR': self.root / 'models'}.items():
            self.stack.enter_context(patch.object(api.config, name, str(value)))
        self.stack.enter_context(patch.object(model_registry, 'REGISTRY_PATH', str(self.root / 'models.json')))
        self.bridge = api.PythonBridge.__new__(api.PythonBridge)
        self.bridge._render_lock = threading.Lock()
        self.bridge._render_thread = None
        self.bridge._active_job = None
        self.bridge._active_downloads = set()
        self.bridge._deletion_previews = {}
        self.bridge.registry = model_registry.ModelRegistry()
        self.credentials = self.stack.enter_context(patch.object(api, 'delete_credential'))
        self.events = self.stack.enter_context(patch.object(api.push, 'emit'))

    def file(self, relative, data=b'keep'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def entry(self, **kwargs):
        return self.bridge.registry.add('stt', 'local_file', 'Test', **kwargs)

    def remove(self, entry):
        preview = self.bridge.preview_model_removal(entry['id'])
        self.assertTrue(preview['ok'], preview)
        return self.bridge.remove_model(entry['id'], preview['token'])

    def test_execution_requires_preview(self):
        entry = self.entry()
        self.assertFalse(self.bridge.remove_model(entry['id'])['ok'])
        self.assertFalse(self.bridge.factory_reset()['ok'])
        self.assertIsNotNone(self.bridge.registry.get(entry['id']))

    def test_owned_directory_removed_and_sibling_preserved(self):
        entry = self.entry()
        own = self.file(f"models/_downloads/{entry['id']}/model.bin")
        sibling = self.file('models/_downloads/other/model.bin')
        self.bridge.registry.update(entry['id'], local_path=str(own))
        result = self.remove(entry)
        self.assertTrue(result['ok'], result)
        self.assertFalse(own.exists())
        self.assertTrue(sibling.exists())
        self.assertIsNone(self.bridge.registry.get(entry['id']))

    def test_external_local_path_connection_only_removed(self):
        path = self.file('samples/user-model.bin')
        entry = self.entry(local_path=str(path))
        preview = self.bridge.preview_model_removal(entry['id'])
        self.assertEqual(preview['files'], 0)
        self.assertEqual(preview['retained'][0]['path'], str(path))
        result = self.bridge.remove_model(entry['id'], preview['token'])
        self.assertTrue(result['ok'])
        self.assertEqual(path.read_bytes(), b'keep')

    def test_path_outside_project_is_retained(self):
        entry = self.entry(local_path=str(self.root.parent))
        result = self.remove(entry)
        self.assertTrue(result['ok'])
        self.assertTrue(result['retained'])
        self.assertTrue(self.root.parent.exists())

    def test_shared_owned_directory_retained(self):
        first = self.entry()
        own = self.file(f"models/_downloads/{first['id']}/model.bin")
        self.bridge.registry.update(first['id'], local_path=str(own))
        second = self.entry(local_path=str(own))
        result = self.remove(first)
        self.assertTrue(result['ok'])
        self.assertTrue(own.exists())
        self.assertIsNotNone(self.bridge.registry.get(second['id']))

    def test_invalid_identifier_rejected(self):
        entry = self.entry()
        entry['id'] = '../../outputs'
        self.assertFalse(self.bridge.preview_model_removal(entry['id'])['ok'])

    def test_storage_root_local_path_is_not_deleted(self):
        path = self.file('models/keep.bin')
        entry = self.entry(local_path=str(path.parent))
        self.assertTrue(self.remove(entry)['ok'])
        self.assertTrue(path.exists())

    def test_changed_files_reject_preview(self):
        entry = self.entry()
        own = self.file(f"models/_downloads/{entry['id']}/model.bin")
        preview = self.bridge.preview_model_removal(entry['id'])
        own.write_bytes(b'changed contents')
        result = self.bridge.remove_model(entry['id'], preview['token'])
        self.assertFalse(result['ok'])
        self.assertIn('changed', result['message'])
        self.assertTrue(own.exists())

    def test_new_output_after_reset_preview_rejects_execution(self):
        self.file('outputs/first.mp4')
        preview = self.bridge.preview_factory_reset()
        added = self.file('outputs/second.mp4')
        result = self.bridge.factory_reset(preview['token'])
        self.assertFalse(result['ok'])
        self.assertTrue(added.exists())

    def test_changed_registry_rejects_preview(self):
        entry = self.entry()
        preview = self.bridge.preview_model_removal(entry['id'])
        self.entry()
        self.assertFalse(self.bridge.remove_model(entry['id'], preview['token'])['ok'])

    def test_preview_token_not_reusable_or_interchangeable(self):
        first, second = self.entry(), self.entry()
        preview = self.bridge.preview_model_removal(first['id'])
        self.assertFalse(self.bridge.remove_model(second['id'], preview['token'])['ok'])
        self.assertFalse(self.bridge.remove_model(first['id'], preview['token'])['ok'])

    def test_file_deletion_failure_preserves_entry_and_credential(self):
        entry = self.entry(credential_ref='secret')
        own = self.file(f"models/_downloads/{entry['id']}/model.bin")
        preview = self.bridge.preview_model_removal(entry['id'])
        with patch.object(deletion_plan.shutil, 'rmtree', side_effect=PermissionError('busy file')):
            result = self.bridge.remove_model(entry['id'], preview['token'])
        self.assertFalse(result['ok'])
        self.assertTrue(result['remaining'])
        self.assertIsNotNone(self.bridge.registry.get(entry['id']))
        self.credentials.assert_not_called()
        self.assertTrue(own.exists())

    def test_shared_credential_preserved(self):
        first = self.entry(credential_ref='shared')
        self.entry(credential_ref='shared')
        self.assertTrue(self.remove(first)['ok'])
        self.credentials.assert_not_called()

    def test_unshared_credential_deleted_after_files(self):
        entry = self.entry(credential_ref='unique')
        own = self.file(f"models/_downloads/{entry['id']}/model.bin")
        self.credentials.side_effect = lambda reference, **kwargs: self.assertFalse(own.exists())
        self.assertTrue(self.remove(entry)['ok'])
        self.credentials.assert_called_once_with('unique', strict=True)

    def test_unavailable_os_store_is_not_reported_as_removed(self):
        with patch.object(credential_store.keyring, 'delete_password', side_effect=credential_store.keyring.errors.NoKeyringError()):
            with self.assertRaises(credential_store.CredentialError):
                credential_store.delete_credential('fixture', strict=True)

    def test_os_store_delete_failure_with_remaining_secret_is_error(self):
        with patch.object(credential_store.keyring, 'delete_password', side_effect=credential_store.keyring.errors.PasswordDeleteError()), patch.object(credential_store.keyring, 'get_password', return_value='fixture'):
            with self.assertRaises(credential_store.CredentialError):
                credential_store.delete_credential('fixture', strict=True)

    def test_already_absent_credential_is_idempotent(self):
        with patch.object(credential_store.keyring, 'delete_password', side_effect=credential_store.keyring.errors.PasswordDeleteError()), patch.object(credential_store.keyring, 'get_password', return_value=None):
            credential_store.delete_credential('fixture', strict=True)

    def test_credential_failure_reports_partial_outcome(self):
        entry = self.entry(credential_ref='unique')
        own = self.file(f"models/_downloads/{entry['id']}/model.bin")
        self.credentials.side_effect = RuntimeError('credential unavailable')
        result = self.remove(entry)
        self.assertFalse(result['ok'])
        self.assertTrue(result['removed'])
        self.assertFalse(own.exists())
        self.assertIsNotNone(self.bridge.registry.get(entry['id']))

    def test_reset_clears_only_selected_trees_and_project_cache(self):
        deleted = [self.file('temp/work'), self.file('outputs/result.mp4'), self.file('core/__pycache__/cache.pyc')]
        kept = [self.file(f'{name}/__pycache__/keep.pyc') for name in
                ('build', '.venv', '.git', 'models', 'Sample', 'frontend/node_modules')]
        kept.append(self.file('Sample/input.mp4'))
        preview = self.bridge.preview_factory_reset()
        self.assertTrue(preview['ok'], preview)
        self.assertEqual(preview['files'], 3)
        result = self.bridge.factory_reset(preview['token'])
        self.assertTrue(result['ok'], result)
        self.assertTrue(all(not path.exists() for path in deleted))
        self.assertTrue(all(path.exists() for path in kept))
        self.assertTrue((self.root / 'temp').is_dir())
        self.assertTrue((self.root / 'outputs').is_dir())

    def test_reset_failure_reports_partial_deletion(self):
        self.file('temp/work')
        output = self.file('outputs/result.mp4')
        preview = self.bridge.preview_factory_reset()
        real_remove = deletion_plan.shutil.rmtree
        def remove(path):
            if Path(path).name == 'outputs':
                raise PermissionError('output busy')
            real_remove(path)
        with patch.object(deletion_plan.shutil, 'rmtree', side_effect=remove):
            result = self.bridge.factory_reset(preview['token'])
        self.assertFalse(result['ok'])
        self.assertEqual(len(result['removed']), 1)
        self.assertTrue(output.exists())

    def test_root_recreation_failure_records_files_already_processed(self):
        self.file('temp/work')
        preview = self.bridge.preview_factory_reset()
        with patch.object(Path, 'mkdir', side_effect=PermissionError('cannot recreate')):
            result = self.bridge.factory_reset(preview['token'])
        self.assertFalse(result['ok'])
        self.assertIn(str(self.root / 'temp'), result['removed'])
        self.assertFalse((self.root / 'temp/work').exists())

    def test_new_download_waits_until_deletion_finalization_exits(self):
        entry = self.entry()
        self.file(f"models/_downloads/{entry['id']}/model.bin")
        preview = self.bridge.preview_model_removal(entry['id'])
        entered, release, attempted, finished = (threading.Event() for _ in range(4))
        real_execute = deletion_plan.execute
        real_tracked = self.bridge._download_tracked
        def execute(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return real_execute(*args)
        def tracked(*args):
            try:
                return real_tracked(*args)
            finally:
                finished.set()
        def add():
            attempted.set()
            return self.bridge.add_local_model('stt', 'unused', 'New')
        with patch.object(deletion_plan, 'execute', side_effect=execute), patch.object(self.bridge, '_run_local_download'), patch.object(self.bridge, '_download_tracked', side_effect=tracked), ThreadPoolExecutor(2) as pool:
            removal = pool.submit(self.bridge.remove_model, entry['id'], preview['token'])
            try:
                self.assertTrue(entered.wait(5))
                addition = pool.submit(add)
                self.assertTrue(attempted.wait(5))
                self.assertFalse(addition.done())
            finally:
                release.set()
            self.assertTrue(removal.result(timeout=5)['ok'])
            self.assertTrue(addition.result(timeout=5)['ok'])
            self.assertTrue(finished.wait(5))
        self.assertFalse(self.bridge._active_downloads)

    def test_reset_rejects_overlap_and_protected_root(self):
        for path in (self.root, self.root / 'models', self.root / 'temp/child', self.root.parent):
            with patch.object(api.config, 'OUTPUT_PATH', str(path)):
                self.assertFalse(self.bridge.preview_factory_reset()['ok'])

    def test_reparse_entry_refuses_deletion(self):
        path = self.file('temp/work')
        real_stat = Path.lstat
        def stat(item):
            value = real_stat(item)
            return SimpleNamespace(st_file_attributes=0x400, st_mode=value.st_mode) if item == path else value
        with patch.object(Path, 'lstat', stat):
            self.assertFalse(self.bridge.preview_factory_reset()['ok'])
        self.assertTrue(path.exists())

    def test_active_download_blocks_preview_and_execution(self):
        entry = self.entry()
        preview = self.bridge.preview_model_removal(entry['id'])
        self.bridge._active_downloads.add(entry['id'])
        self.assertFalse(self.bridge.preview_factory_reset()['ok'])
        self.assertFalse(self.bridge.preview_model_removal(entry['id'])['ok'])
        self.assertFalse(self.bridge.remove_model(entry['id'], preview['token'])['ok'])
        self.bridge._active_downloads.clear()
        self.assertTrue(self.bridge.remove_model(entry['id'], preview['token'])['ok'])

    def test_download_tracked_through_install_and_released_after_exit(self):
        entered, release = threading.Event(), threading.Event()
        def download(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
        with patch.object(self.bridge, '_run_local_download', side_effect=download):
            result = self.bridge.add_local_model('stt', 'https://unused/model', 'Test')
            model_id = result['model']['id']
            try:
                self.assertTrue(entered.wait(5))
                self.assertIn(model_id, self.bridge._active_downloads)
                self.assertFalse(self.bridge.preview_factory_reset()['ok'])
            finally:
                release.set()
            # Acquiring the lifecycle lock isn't enough to join the worker;
            # use its finalization event for a bounded exit acknowledgment.
            deadline = __import__('time').monotonic() + 5
            while model_id in self.bridge._active_downloads and __import__('time').monotonic() < deadline:
                threading.Event().wait(.01)
            self.assertNotIn(model_id, self.bridge._active_downloads)

    def test_failed_thread_start_releases_tracking(self):
        with patch.object(api.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('cannot start')
            result = self.bridge.add_local_model('stt', 'https://unused/model', 'Test')
        self.assertFalse(result['ok'])
        self.assertFalse(self.bridge._active_downloads)
        self.assertEqual(result['model']['status'], 'error')

    def test_cancel_keeps_download_owned_until_worker_exits(self):
        entered, release = threading.Event(), threading.Event()
        def download(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
        with patch.object(self.bridge, '_run_local_download', side_effect=download):
            result = self.bridge.add_local_model('stt', 'https://unused/model', 'Test')
            model_id = result['model']['id']
            try:
                self.assertTrue(entered.wait(5))
                self.assertTrue(self.bridge.cancel_model_download(model_id)['ok'])
                self.assertTrue(self.bridge._download_contexts[model_id].cancelled.is_set())
                self.assertIn(model_id, self.bridge._active_downloads)
                self.assertFalse(self.bridge.preview_model_removal(model_id)['ok'])
                self.assertFalse(self.bridge.preview_factory_reset()['ok'])
            finally:
                release.set()
            deadline = __import__('time').monotonic() + 5
            while model_id in self.bridge._active_downloads and __import__('time').monotonic() < deadline:
                threading.Event().wait(.01)
            self.assertNotIn(model_id, self.bridge._active_downloads)
            self.assertFalse(self.bridge.cancel_model_download(model_id)['ok'])

    def test_cancelled_download_never_installs(self):
        from core.render_context import RenderContext
        entry = self.entry(status='downloading')
        job = RenderContext(api.config.TEMP_PATH)
        self.bridge._download_contexts = {entry['id']: job}
        self.bridge._active_downloads.add(entry['id'])
        def producer(*args):
            yield {'phase': 'downloading'}
            job.request_stop()
            yield {'phase': 'done'}
        with patch.object(api, 'download_with_progress', side_effect=producer):
            self.bridge._download_tracked(entry['id'], 'stt', 'https://unused/model')
        self.assertEqual(self.bridge.registry.get(entry['id'])['status'], 'not_downloaded')
        self.assertFalse(self.bridge._active_downloads)
        self.assertFalse(self.bridge._download_contexts)

    def test_voice_node_ids_and_cast_order_survive_middle_removal(self):
        self.bridge.graph = api.build_default_graph()
        ids = [self.bridge.add_node_instance('tts_rvc')['nodeId'] for _ in range(10)]
        self.bridge.graph.nodes['tts_rvc'].values['voice'] = 'original'
        for number, node_id in enumerate(ids, 2):
            self.bridge.graph.nodes[node_id].values['voice'] = str(number)
        self.assertTrue(self.bridge.remove_node_instance('tts_rvc_3')['ok'])
        created = self.bridge.add_node_instance('tts_rvc')['nodeId']
        self.assertEqual(created, 'tts_rvc_12')
        self.assertEqual(self.bridge.graph.nodes['tts_rvc_11'].values['voice'], '11')
        self.assertEqual(self.bridge.get_cast_list(),
                         ['original', '2', *[str(n) for n in range(4, 12)], 'CLONED_USER'])

    def test_required_nodes_and_readonly_parameters_cannot_change(self):
        self.bridge.graph = api.build_default_graph()
        self.assertFalse(self.bridge.set_node_enabled('stt', False)['ok'])
        self.assertFalse(self.bridge.set_node_param('stt', 'engine', 'anything')['ok'])
        self.assertFalse(self.bridge.set_node_param('tts_rvc', 'voice', 'missing-model')['ok'])
        self.assertTrue(self.bridge.set_node_param('tts_rvc', 'voice', 'CLONED_USER')['ok'])
        self.assertTrue(self.bridge.graph.nodes['stt'].enabled)

    def test_service_configuration_is_validated_before_credentials(self):
        with patch.object(api, 'set_credential') as credentials:
            result = self.bridge.add_cloud_model('voice', 'Voice', 'https://example.test', 'secret', 'elevenlabs_sts')
        self.assertFalse(result['ok'])
        credentials.assert_not_called()
        self.assertFalse(self.bridge.registry.list())

    def test_reference_model_never_starts_heavy_download(self):
        with patch.object(api.threading, 'Thread') as thread:
            result = self.bridge.add_local_model('tts', 'https://huggingface.co/hexgrad/Kokoro-82M', 'Kokoro')
        self.assertFalse(result['ok'])
        thread.assert_not_called()
        self.assertFalse(self.bridge.registry.list())

    def test_service_configuration_reaches_provider_metadata(self):
        config = {'path': '/my-translator', 'body': {'input': '{text}'}, 'response_key': 'translated'}
        result = self.bridge.add_local_api_model('translation', 'Translator', 'http://localhost:8000', 'custom', config)
        self.assertTrue(result['ok'])
        self.assertEqual(result['model']['meta']['translation_request'], config)
        with patch.object(api, 'set_credential'):
            voice = self.bridge.add_cloud_model('voice', 'Voice', 'https://example.test', 'secret', 'elevenlabs_sts', {'voice_id': 'service-voice'})
        self.assertTrue(voice['ok'])
        self.assertEqual(voice['model']['meta']['voice_id'], 'service-voice')
        self.assertNotIn('secret', str(voice['model']))

    def test_graph_layout_cast_reload_and_failed_save_rollback(self):
        from core.graph_state import GraphState
        self.bridge._graph_state = GraphState(str(self.root / 'graph.json'))
        self.bridge.graph = self.bridge._graph_state.load()
        duplicate = self.bridge.add_node_instance('tts_rvc')['nodeId']
        self.assertTrue(self.bridge.set_node_position(duplicate, 120, 530)['ok'])
        loaded = self.bridge._graph_state.load()
        self.assertEqual((loaded.nodes[duplicate].x, loaded.nodes[duplicate].y), (120, 530))
        self.assertTrue(loaded.nodes[duplicate].removable)
        self.assertFalse(self.bridge.set_node_position(duplicate, float('nan'), 0)['ok'])
        with patch.object(self.bridge._graph_state, 'save', side_effect=OSError('disk full')):
            self.assertFalse(self.bridge.remove_node_instance(duplicate)['ok'])
        self.assertIn(duplicate, self.bridge.graph.nodes)
        self.assertIn(duplicate, self.bridge._graph_state.load().nodes)

    def test_invalid_graph_preserves_original_bytes(self):
        from core.graph_state import GraphState
        path = self.file('graph.json', b'{"nodes":[]}')
        state = GraphState(str(path))
        self.assertIn('stt', state.load().nodes)
        backups = list(self.root.glob('graph.json.corrupt-*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b'{"nodes":[]}')

    def test_download_exception_releases_tracking(self):
        model_id = str(uuid.uuid4())
        self.bridge._active_downloads.add(model_id)
        with patch.object(self.bridge, '_run_local_download', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.bridge._download_tracked(model_id, 'stt', 'unused')
        self.assertFalse(self.bridge._active_downloads)

    def test_missing_registry_entry_drains_download_producer(self):
        model_id = str(uuid.uuid4())
        ended = []
        def producer(*args):
            yield {'phase': 'downloading'}
            ended.append(True)
            yield {'phase': 'done'}
        with patch.object(api, 'download_with_progress', side_effect=producer):
            self.bridge._run_local_download(model_id, 'stt', 'https://unused/model')
        self.assertEqual(ended, [True])

    def test_notification_failure_drains_download_before_releasing_guard(self):
        entry = self.entry()
        self.bridge._active_downloads.add(entry['id'])
        ended = []
        def producer(*args):
            yield {'phase': 'downloading'}
            self.assertIn(entry['id'], self.bridge._active_downloads)
            ended.append(True)
            yield {'phase': 'done'}
        self.events.side_effect = [RuntimeError('notification failed'), None]
        with patch.object(api, 'download_with_progress', side_effect=producer):
            self.bridge._download_tracked(entry['id'], 'stt', 'https://unused/model')
        self.assertEqual(ended, [True])
        self.assertFalse(self.bridge._active_downloads)
        self.assertEqual(self.bridge.registry.get(entry['id'])['status'], 'error')


if __name__ == '__main__':
    unittest.main()
