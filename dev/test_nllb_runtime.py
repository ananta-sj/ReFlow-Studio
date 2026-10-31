"""Isolated NLLB routing without importing models or contacting services."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import nllb_runtime as runtime, settings
from core.providers.translation.nllb_local import NLLBLocalProvider
from core.providers.resolve import resolve_translation
from core.render_context import RenderContext, bind_job
from core.runtime_integrity import sha

ROOT = Path(__file__).resolve().parents[1]


class NLLBRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'temp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.route = dict(identity='approved-package-runtime', executable='fixture-python', device='cpu', profile='fixture-profile')
        for name in runtime.SOURCES:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
        self.manifest = self.root/runtime.MANIFEST
        self.manifest.write_text(json.dumps(dict(schema='reflow.nllb-runtime.v1',
            package_runtime_identity=self.route['identity'], source_sha256={name: sha(self.root/name) for name in runtime.SOURCES})))
        patcher = patch('core.xtts_runtime.validate', return_value=self.route)
        patcher.start();self.addCleanup(patcher.stop)

    def test_valid_recipe_is_stable_cpu_trial(self):
        self.assertEqual(runtime.validate(self.root), runtime.validate(self.root))
        self.assertEqual(runtime.readiness(self.root)['status'], 'ready-for-explicit-trial')
        self.assertFalse(runtime.readiness(self.root)['release_ready'])

    def test_source_drift_is_rejected(self):
        (self.root/'core/nllb_worker.py').write_text('changed')
        self.assertEqual(runtime.readiness(self.root)['status'], 'unverified')

    def test_underlying_runtime_drift_is_rejected(self):
        self.route['identity'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            runtime.validate(self.root)

    def test_malformed_missing_recipe_is_unverified(self):
        for value in [None, [], {}, 'invalid']:
            self.manifest.write_text(json.dumps(value))
            self.assertEqual(runtime.readiness(self.root)['status'], 'unverified')
        self.manifest.unlink()
        self.assertEqual(runtime.readiness(self.root)['status'], 'unverified')

    def test_legacy_default_unknown_and_gpu_choices(self):
        self.assertEqual(NLLBLocalProvider('model').runtime, 'legacy')
        with self.assertRaises(ValueError):NLLBLocalProvider('model', runtime='guess')
        with self.assertRaisesRegex(ValueError, 'CPU only'):NLLBLocalProvider('model', runtime='isolated', device='cuda:0')

    def test_isolated_hint_and_target_validate_before_loading(self):
        provider = NLLBLocalProvider('model', runtime='isolated')
        with patch.object(provider, '_isolated_call', return_value='नमस्ते') as call, patch.object(provider, '_ensure_loaded') as load:
            self.assertEqual(provider.translate('Hello', 'Hindi', source_language='en'), 'नमस्ते')
            call.assert_called_once_with('Hello', 'Hindi', 'eng_Latn')
            for target, instructions, source in [('Nigerian Pidgin', '', 'en'), ('Hindi', 'shorter', 'en'), ('Hindi', '', 'auto')]:
                with self.assertRaises(ValueError):provider.translate('Hello', target, instructions, source)
            load.assert_not_called()
        with self.assertRaises(ValueError):provider.translate(123, 'Hindi', source_language='en')

    def test_session_reused_and_released_for_owned_job(self):
        job = RenderContext(self.root)
        provider = NLLBLocalProvider('model', runtime='isolated')
        with patch.object(runtime, 'validate', return_value=self.route), patch('core.feature_session.FeatureSession') as factory:
            session = factory.return_value
            session.job = job
            session.call.return_value = dict(translation='नमस्ते', model_loads=1)
            try:
                with bind_job(job):
                    provider.translate('Hello', 'Hindi', source_language='en')
                    provider.translate('World', 'Hindi', source_language='en')
                self.assertEqual(factory.call_count, 1)
                self.assertEqual(session.call.call_count, 2)
                self.assertEqual(provider.runtime_identity, self.route['identity'])
                provider.release()
                session.close.assert_called_once()
                self.assertIsNone(provider.session)
            finally:job.cleanup()

    def test_stage_failure_releases_worker(self):
        from core.pipeline import _translation_stage
        provider = NLLBLocalProvider('model', runtime='isolated')
        provider.session = Mock()
        session = provider.session
        with self.assertRaisesRegex(RuntimeError, 'original'):
            with _translation_stage(provider):raise RuntimeError('original')
        session.close.assert_called_once()

    def test_standalone_call_releases_owned_session(self):
        provider = NLLBLocalProvider('model', runtime='isolated')
        with patch.object(runtime, 'validate', return_value=self.route), patch('core.feature_session.FeatureSession') as factory:
            factory.return_value.call.return_value = dict(translation='नमस्ते')
            self.assertEqual(provider.translate('Hello', 'Hindi', source_language='en'), 'नमस्ते')
            factory.return_value.close.assert_called_once()
            self.assertFalse(factory.call_args.args[0].workspace.exists())

    def test_missing_worker_result_cannot_publish_translation(self):
        provider = NLLBLocalProvider('model', runtime='isolated')
        with patch.object(runtime, 'validate', return_value=self.route), patch('core.feature_session.FeatureSession') as factory:
            factory.return_value.call.return_value = {}
            with self.assertRaisesRegex(RuntimeError, 'nonempty'):
                provider.translate('Hello', 'Hindi', source_language='en')
            factory.return_value.close.assert_called_once()

    def test_selection_reaches_nllb_without_changing_api_route(self):
        registry = Mock(get_active=Mock(return_value=dict(kind='local_file', local_path='model')))
        with patch('core.providers.resolve._local', return_value=dict(adapter='nllb')), patch('core.providers.translation.nllb_local.NLLBLocalProvider') as factory:
            resolve_translation(registry, 'localhost', runtime='isolated')
            factory.assert_called_once_with('model', runtime='isolated')
        registry.get_active.return_value = dict(kind='cloud_api', api_base_url='https://example.invalid')
        with patch('core.providers.translation.cloud_rest.TranslationCloudRestProvider') as cloud:
            resolve_translation(registry, 'localhost', runtime='isolated')
            cloud.assert_called_once()

    def test_settings_read_default_without_writing_and_reject_bad_values(self):
        path = self.root/'settings.json';path.write_text('{}')
        with patch.object(settings, 'SETTINGS_PATH', str(path)):
            store = settings.Settings()
            self.assertEqual(store.get('nllb_runtime'), 'legacy')
            self.assertEqual(path.read_text(), '{}')
            with self.assertRaises(ValueError):store.update(dict(nllb_runtime='guess'))
            self.assertEqual(path.read_text(), '{}')

    def test_bridge_rejects_unavailable_choice_before_save(self):
        from bridge.api import PythonBridge
        bridge = PythonBridge.__new__(PythonBridge);bridge.settings = Mock()
        with patch.object(runtime, 'validate', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):bridge.update_settings(dict(nllb_runtime='isolated'))
        bridge.settings.update.assert_not_called()

    def test_subtitle_preflight_uses_worker_instead_of_parent_import(self):
        from core.runtime_checks import preflight
        registry = Mock(get_active=Mock(side_effect=lambda stage:dict(kind='local_file', stage_type='translation', local_path='model') if stage=='translation' else None))
        with patch('core.runtime_checks.local_contract', return_value=dict(adapter='nllb')), patch.object(runtime, 'validate') as validate, patch('core.runtime_checks._engine') as engine:
            preflight(registry, dict(lang='hi', nllb_runtime='isolated'), 'subtitle_translate')
        validate.assert_called_once();engine.assert_not_called()


if __name__ == '__main__':
    unittest.main()
