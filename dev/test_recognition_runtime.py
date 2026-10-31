"""Recognition runtime selection, drift rejection and route independence."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import recognition_runtime as runtime
from core import settings
from core.pipeline_contracts import SettingsSnapshot
from core.providers.resolve import resolve_stt
from core.xtts_runtime import sha

ROOT = Path(__file__).resolve().parents[1]


class RecognitionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root/'runtime_profiles'/runtime.PROFILE
        self.folder.mkdir(parents=True)
        for name in ('python.exe', 'python313.dll', 'python313.zip'):
            (self.folder/name).write_bytes(name.encode())
        for name in runtime.SOURCES:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        self.lock = self.root/runtime.LOCK
        self.lock.parent.mkdir(parents=True)
        self.lock.write_text(json.dumps(dict(packages=[dict(name='faster-whisper', version='1.2.1')])))
        self.meta = self.folder/'Lib/site-packages/faster_whisper-1.2.1.dist-info/METADATA'
        self.meta.parent.mkdir(parents=True)
        self.meta.write_text('Name: faster-whisper\nVersion: 1.2.1\n')
        self.recipe = dict(schema='reflow.recognition-runtime.v1', python='3.13.16', device='cpu',
            bootstrap_sha256={name: sha(self.folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')},
            source_sha256={name: sha(self.root/name) for name in runtime.SOURCES}, lock_sha256=sha(self.lock))
        (self.folder/'routing-recipe.json').write_text(json.dumps(self.recipe))

    def test_verified_route_has_stable_identity_and_remains_trial(self):
        self.assertEqual(runtime.validate(self.root), runtime.validate(self.root))
        self.assertEqual(runtime.readiness(self.root)['status'], 'ready-for-explicit-trial')
        self.assertFalse(runtime.readiness(self.root)['release_ready'])

    def test_bootstrap_worker_lock_and_metadata_drift_rejected(self):
        for path in [self.folder/'python313.dll', self.root/'core/run_stt.py', self.lock, self.meta]:
            before = path.read_bytes()
            try:
                path.write_bytes(b'changed')
                with self.subTest(path=path), self.assertRaises(RuntimeError):
                    runtime.validate(self.root)
            finally:
                path.write_bytes(before)

    def test_duplicate_metadata_rejected(self):
        other = self.meta.parent.with_name('duplicate.dist-info')/'METADATA'
        other.parent.mkdir()
        other.write_bytes(self.meta.read_bytes())
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            runtime.validate(self.root)

    def test_missing_recipe_is_unverified(self):
        (self.folder/'routing-recipe.json').unlink()
        self.assertEqual(runtime.readiness(self.root)['status'], 'unverified')

    def test_malformed_recipe_is_unverified(self):
        for value in [[], None, 1, 'invalid', {}]:
            (self.folder/'routing-recipe.json').write_text(json.dumps(value))
            self.assertEqual(runtime.readiness(self.root)['status'], 'unverified')

    def test_isolated_route_ignores_global_worker_override(self):
        expected = runtime.validate(self.root)
        with patch.dict(os.environ, REFLOW_WORKER_PYTHON='invalid-global-override'), patch.object(runtime, 'validate', return_value=expected):
            self.assertEqual(runtime.resolve('isolated'), expected)

    def test_current_route_keeps_existing_worker_resolver(self):
        with patch.object(runtime, 'worker_python', return_value='current-python'):
            self.assertEqual(runtime.resolve()['executable'], 'current-python')
        with self.assertRaises(ValueError):
            runtime.resolve('unknown')

    def test_existing_settings_read_without_changing_file(self):
        path = self.root/'settings.json'
        path.write_text('{"default_language":"hi"}')
        before = path.read_bytes()
        with patch.object(settings, 'SETTINGS_PATH', str(path)):
            store = settings.Settings()
            self.assertEqual(store.get('recognition_runtime'), 'legacy')
            self.assertEqual(path.read_bytes(), before)
            frozen = SettingsSnapshot(store.all())
            store.update(dict(recognition_runtime='isolated'))
            self.assertEqual(frozen.get('recognition_runtime'), 'legacy')
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                store.update(dict(recognition_runtime='guess'))
            self.assertEqual(path.read_bytes(), before)

    def test_saved_selection_reaches_only_cpu_provider(self):
        registry = Mock()
        registry.get_active.return_value = None
        with patch('core.providers.stt.whisper_local.WhisperLocalProvider') as factory:
            resolve_stt(registry, 'medium', runtime='isolated')
            factory.assert_called_once_with(model_size='medium', runtime='isolated')
        registry.get_active.return_value = dict(kind='cloud_api', api_base_url='https://example.invalid')
        with patch('core.providers.stt.cloud_rest.STTCloudRestProvider') as cloud, patch.object(runtime, 'validate') as validate:
            resolve_stt(registry, 'medium', runtime='isolated')
            cloud.assert_called_once()
            validate.assert_not_called()
        registry.get_active.return_value = dict(kind='local_file', stage_type='stt', local_path='model')
        with patch('core.providers.resolve._local', return_value=dict(adapter='whisper_turbo')), patch('core.providers.stt.whisper_turbo_local.WhisperTurboLocalProvider') as gpu:
            resolve_stt(registry, 'medium', runtime='isolated')
            gpu.assert_called_once_with('model')

    def test_bridge_rejects_missing_recipe_before_saving(self):
        from bridge.api import PythonBridge
        bridge = PythonBridge.__new__(PythonBridge)
        bridge.settings = Mock()
        with patch.object(runtime, 'validate', side_effect=RuntimeError('missing')):
            with self.assertRaises(RuntimeError):
                bridge.update_settings(dict(recognition_runtime='isolated'))
        bridge.settings.update.assert_not_called()

    def test_preflight_does_not_import_recognition_in_desktop_parent(self):
        from core.runtime_checks import preflight
        registry = Mock(get_active=Mock(side_effect=lambda stage:
            dict(kind='cloud_api', api_base_url='https://example.invalid') if stage=='tts' else None))
        with patch.object(runtime, 'validate') as validate, patch('core.runtime_checks._engine') as engine, patch('core.runtime_checks._selection'):
            preflight(registry, dict(lang='source', keep_bg=False, recognition_runtime='isolated'), 'audio_dub')
        validate.assert_called_once()
        engine.assert_not_called()

    def test_readiness_failed_probe_stays_failed_for_selected_local_model(self):
        from core.engine_readiness import inspect
        entry = dict(kind='local_file', status='installed', local_path='fixture')
        registry = Mock(get_active=Mock(side_effect=lambda stage: entry if stage=='stt' else None))
        route = runtime.validate(self.root)
        with patch.object(runtime, 'validate', return_value=route), patch('core.engine_readiness.local_contract', return_value=dict(adapter='faster_whisper')), patch('core.engine_readiness.preflight_speech'), patch('core.runtime_probe.probe', return_value=dict(status='failed', problems=['fixture import failure'])), patch('core.engine_readiness.shutil.which', return_value='ffmpeg'):
            result = inspect(registry, 'audio_dub', dict(target_lang='source', source_language='en', keep_background=False), verify_runtime=True, recognition_runtime='isolated')
        row = next(row for row in result['checks'] if row['stage']=='stt')
        self.assertEqual(row['status'], 'needs_setup')
        self.assertEqual(row['runtime']['selection'], 'isolated')
        self.assertEqual(result['status'], 'needs_setup')

    def test_portable_contains_recipe_lock_and_no_personal_settings(self):
        spec = importlib.util.spec_from_file_location('recognition_portable', ROOT/'packaging/build_portable.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with patch.object(builder, 'ROOT', self.root), patch.object(builder, 'ROOT_FILES', ()), patch.object(builder, 'TREES', ()):
            paths = {relative for _, relative, _ in builder.entries([runtime.PROFILE])}
        self.assertIn(runtime.LOCK, paths)
        self.assertIn('runtime_profiles/recognition-candidate/routing-recipe.json', paths)
        self.assertNotIn('settings.json', paths)


if __name__ == '__main__':
    unittest.main()
