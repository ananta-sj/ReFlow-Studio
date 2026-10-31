"""Hindi voice discovery, connection and feature-specific startup checks."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from core import indicf5_profiles as profiles
from core.providers import resolve
from core import runtime_checks
from core.model_registry import ModelRegistry
from dev.test_render_queue import api


class HindiControlsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        original = Path(api.config.MODELS_DIR) / 'indicf5/references/abhishek/profile.json'
        from core.providers.tts.indicf5_local import load_reference_profile
        self.confirmed = load_reference_profile(original)
        self.stack.enter_context(patch.object(api.config, 'MODELS_DIR', str(self.root)))
        folder = self.root / 'indicf5/references/abhishek'
        folder.mkdir(parents=True)
        (folder / 'profile.json').write_text(json.dumps(self.confirmed), encoding='utf-8')
        assets = self.root / 'indicf5/evaluation/assets'
        (assets / 'checkpoints').mkdir(parents=True)
        (assets / 'config.json').write_text(json.dumps(dict(model_type='inf5', architectures=['INF5Model'])))
        (assets / 'model.safetensors').write_bytes(b'fixture only')
        (assets / 'checkpoints/vocab.txt').write_text('a\n')
        self.stack.enter_context(patch('core.model_registry.REGISTRY_PATH', str(self.root / 'registry.json')))
        self.bridge = api.PythonBridge.__new__(api.PythonBridge)
        self.bridge._render_lock = threading.Lock()
        self.bridge.registry = ModelRegistry()
        self.bridge._deletion_busy = Mock(return_value=False)
        self.runtime = self.stack.enter_context(patch('core.providers.tts.indicf5_local.isolated_interpreter', return_value='fixture-python'))
        self.stack.enter_context(patch.object(profiles, 'isolated_interpreter', self.runtime))

    def test_library_and_preview_are_read_only(self):
        result = self.bridge.list_hindi_voices()
        self.assertTrue(result['model_ready'])
        self.assertEqual(result['profiles'][0]['id'], 'abhishek')
        preview = self.bridge.preview_hindi_voice('abhishek')
        self.assertTrue(preview['ok'])
        self.assertTrue(preview['audio'].startswith('data:audio/wav;base64,'))
        self.assertEqual(self.bridge.registry.list(), [])

    def test_explicit_confirmation_and_valid_device_required(self):
        for confirmed, device in [(False, 'cpu'), ('yes', 'cpu'), (True, 'cuda:99')]:
            self.assertFalse(self.bridge.connect_hindi_voice('abhishek', device, confirmed)['ok'])
        self.assertEqual(self.bridge.registry.list(), [])

    def test_connect_reuses_entry_and_preserves_existing_active_voice(self):
        old = self.bridge.registry.add('tts', 'cloud_api', 'Existing')
        result = self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.bridge.registry.get_active('tts')['id'], old['id'])
        identifier = result['model']['id']
        updated = self.bridge.connect_hindi_voice('abhishek', 'cpu', True)
        self.assertEqual(updated['model']['id'], identifier)
        self.assertEqual(updated['model']['meta']['speech_device'], 'cpu')
        self.assertEqual(len(self.bridge.registry.list()), 2)

    def test_busy_and_path_traversal_rejected(self):
        self.assertFalse(self.bridge.preview_hindi_voice('../abhishek')['ok'])
        self.bridge._deletion_busy.return_value = True
        self.assertFalse(self.bridge.connect_hindi_voice('abhishek', 'cpu', True)['ok'])
        self.assertEqual(self.bridge.registry.list(), [])

    def test_bad_reference_cannot_connect(self):
        path = self.root / 'indicf5/references/abhishek/profile.json'
        data = json.loads(path.read_text())
        data['reference_sha256'] = '0' * 64
        path.write_text(json.dumps(data))
        self.assertEqual(self.bridge.list_hindi_voices()['profiles'], [])
        self.assertFalse(self.bridge.connect_hindi_voice('abhishek', 'cpu', True)['ok'])

    def test_selected_speech_processor_reaches_provider(self):
        self.assertTrue(self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)['ok'])
        provider = resolve.resolve_tts(self.bridge.registry, 'cpu')
        self.assertEqual(provider.device, 'cuda:0')

    def test_indic_preflight_does_not_require_xtts(self):
        self.assertTrue(self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)['ok'])
        with patch.object(runtime_checks, '_engine') as engine:
            runtime_checks.preflight(self.bridge.registry,
                dict(lang='source', keep_bg=False, cast_list=['CLONED_USER']), 'video_dub')
        self.assertEqual([call.args[0] for call in engine.call_args_list], ['faster_whisper'])
        self.runtime.assert_called_with('cuda:0')

    def test_missing_runtime_prevents_connection(self):
        self.runtime.side_effect = RuntimeError('runtime missing')
        self.assertFalse(self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)['ok'])
        self.assertEqual(self.bridge.registry.list(), [])

    def test_activation_rechecks_runtime_before_changing_selection(self):
        old = self.bridge.registry.add('tts', 'cloud_api', 'Existing')
        connected = self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)
        self.runtime.side_effect = RuntimeError('runtime missing')
        self.assertFalse(self.bridge.set_active_model('tts', connected['model']['id'])['ok'])
        self.assertEqual(self.bridge.registry.get_active('tts')['id'], old['id'])

    def test_indic_estimate_does_not_discount_serial_speech(self):
        self.assertTrue(self.bridge.connect_hindi_voice('abhishek', 'cuda:0', True)['ok'])
        self.bridge.monitor = Mock()
        self.bridge.monitor.base_stage_cost.return_value = 4
        self.bridge.monitor.base_stage_vram_mb.return_value = 4000
        self.bridge._model_resource_override = Mock(return_value=None)
        one, _ = self.bridge._estimate_overrides('cpu', 1, ['CLONED_USER'])
        eight, _ = self.bridge._estimate_overrides('cpu', 8, ['CLONED_USER'])
        self.assertEqual(one['tts_rvc'], eight['tts_rvc'])


if __name__ == '__main__':
    unittest.main()
