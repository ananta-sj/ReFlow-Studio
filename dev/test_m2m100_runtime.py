"""Explicit fallback routing and candidate integrity with disposable fixtures."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from core import m2m100_runtime as runtime,settings
from core.runtime_integrity import sha
from core.providers.translation.m2m100_isolated import IsolatedM2M100Provider
from core.render_context import RenderContext,bind_job

ROOT=Path(__file__).resolve().parents[1]


class M2M100RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'temp');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'runtime_profiles/translation-candidate'
        self.folder.mkdir(parents=True)
        (self.folder/'python.exe').write_bytes(b'fixture-python')
        packages=[]
        for index in range(41):
            name='fixture-'+str(index);packages.append(dict(name=name,version='1.0'))
            path=self.folder/f'Lib/site-packages/{name}-1.0.dist-info/METADATA'
            path.parent.mkdir(parents=True);path.write_text(f'Name: {name}\nVersion: 1.0\n')
        plan=self.root/runtime.PLAN;plan.parent.mkdir(parents=True)
        plan.write_text(json.dumps(dict(bootstrap=[dict(name='python.exe')],packages=packages)))
        for name in runtime.SOURCES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        (self.folder/'profile.json').write_text(json.dumps(dict(python='3.13.16',device='cpu',proposal_sha256=sha(plan),bootstrap_sha256={'python.exe':sha(self.folder/'python.exe')})))
        self.recipe=self.folder/'routing-recipe.json'
        self.recipe.write_text(json.dumps(dict(schema='reflow.m2m100-runtime.v1',source_sha256={name:sha(self.root/name) for name in runtime.SOURCES})))

    def test_bound_identity_is_stable_and_trial_only(self):
        self.assertEqual(runtime.validate(self.root),runtime.validate(self.root))
        self.assertEqual(runtime.readiness(self.root)['status'],'ready-for-explicit-trial')
        self.assertFalse(runtime.readiness(self.root)['release_ready'])

    def test_worker_bootstrap_metadata_and_proposal_drift_rejected(self):
        for path in [self.root/'core/m2m100_worker.py',self.folder/'python.exe',self.root/runtime.PLAN,
                     next((self.folder/'Lib/site-packages').glob('*/METADATA'))]:
            before=path.read_bytes()
            try:
                path.write_bytes(b'changed')
                with self.subTest(path=path),self.assertRaises(RuntimeError):runtime.validate(self.root)
            finally:path.write_bytes(before)

    def test_missing_or_bad_recipe_reports_unavailable(self):
        for value in [None,[],{},'bad']:
            self.recipe.write_text(json.dumps(value));self.assertEqual(runtime.readiness(self.root)['status'],'unverified')
        self.recipe.unlink();self.assertEqual(runtime.readiness(self.root)['status'],'unverified')

    def test_duplicate_metadata_rejected(self):
        source=next((self.folder/'Lib/site-packages').glob('*/METADATA'))
        duplicate=source.parent.with_name('duplicate.dist-info')/'METADATA';duplicate.parent.mkdir()
        duplicate.write_bytes(source.read_bytes())
        with self.assertRaisesRegex(RuntimeError,'Duplicate'):runtime.validate(self.root)

    def test_language_validation_precedes_runtime_or_model_load(self):
        provider=IsolatedM2M100Provider()
        with patch.object(provider,'_call',return_value='नमस्ते') as call:
            for target,instructions,source in [('Nigerian Pidgin','','en'),('Hindi','shorter','en'),('Hindi','','auto')]:
                with self.assertRaises(ValueError):provider.translate('Hello',target,instructions,source)
            call.assert_not_called()
            self.assertEqual(provider.translate('Hello','Hindi',source_language='en'),'नमस्ते')
            call.assert_called_once_with(dict(text='Hello',target='Hindi',source='en'))

    def test_job_reuses_worker_and_release_is_idempotent(self):
        job=RenderContext(self.root);provider=IsolatedM2M100Provider()
        route=dict(executable='fixture-python',identity='fixture-identity')
        try:
            with patch.object(runtime,'validate',return_value=route),patch.object(runtime,'model_contract',return_value=dict(model_path='model',revision='fixture')),patch('core.feature_session.FeatureSession') as factory:
                session=factory.return_value;session.job=job;session.call.return_value=dict(translation='नमस्ते')
                with bind_job(job):
                    provider.translate('Hello','Hindi',source_language='en')
                    provider.translate('World','Hindi',source_language='en')
                factory.assert_called_once();self.assertEqual(session.call.call_count,2)
                provider.release();provider.release();session.close.assert_called_once()
        finally:job.cleanup()

    def test_session_cannot_cross_jobs(self):
        provider=IsolatedM2M100Provider();provider.session=Mock(job=object())
        job=RenderContext(self.root)
        try:
            with bind_job(job),self.assertRaisesRegex(RuntimeError,'another job'):
                provider.translate('Hello','Hindi',source_language='en')
        finally:job.cleanup()

    def test_fallback_routes_locally_after_mocked_service_failure(self):
        import llm_translator,requests
        from core.providers.translation.ollama_m2m100_local import OllamaM2M100LocalProvider
        with patch.object(llm_translator.requests,'get',side_effect=requests.ConnectionError('fixture offline')),patch.object(llm_translator,'wait_or_cancel'),patch('core.providers.translation.m2m100_isolated.IsolatedM2M100Provider') as factory:
            factory.return_value.translate.return_value='नमस्ते'
            provider=OllamaM2M100LocalProvider(runtime='isolated')
            self.assertEqual(provider.translate('Hello','Hindi',source_language='en'),'नमस्ते')
            self.assertEqual(provider._translator.mode,'m2m100_isolated')
            factory.assert_called_once();provider.release();factory.return_value.release.assert_called_once()

    def test_successful_ollama_does_not_initialize_local_fallback(self):
        import llm_translator
        from core.providers.translation.ollama_m2m100_local import OllamaM2M100LocalProvider
        tags=Mock();tags.json.return_value=dict(models=[dict(name='llama3:latest')])
        reply=Mock();reply.json.return_value=dict(response='नमस्ते')
        with patch.object(llm_translator.requests,'get',return_value=tags),patch.object(llm_translator.requests,'post',return_value=reply),patch('core.providers.translation.m2m100_isolated.IsolatedM2M100Provider') as factory:
            provider=OllamaM2M100LocalProvider(runtime='isolated')
            self.assertEqual(provider.translate('Hello','Hindi',source_language='en'),'नमस्ते')
            factory.assert_not_called();provider.release()

    def test_saved_default_and_bad_value_preserve_settings(self):
        path=self.root/'settings.json';path.write_text('{}')
        with patch.object(settings,'SETTINGS_PATH',str(path)):
            store=settings.Settings();self.assertEqual(store.get('m2m100_runtime'),'legacy')
            self.assertEqual(path.read_text(),'{}')
            with self.assertRaises(ValueError):store.update(dict(m2m100_runtime='bad'))
            self.assertEqual(path.read_text(),'{}')

    def test_bridge_unavailable_runtime_cannot_be_saved(self):
        from bridge.api import PythonBridge
        bridge=PythonBridge.__new__(PythonBridge);bridge.settings=Mock()
        with patch.object(runtime,'validate',side_effect=RuntimeError('missing')):
            with self.assertRaises(RuntimeError):bridge.update_settings(dict(m2m100_runtime='isolated'))
        bridge.settings.update.assert_not_called()

    def test_resolver_keeps_connected_engines_independent(self):
        from core.providers.resolve import resolve_translation
        registry=Mock(get_active=Mock(return_value=None))
        with patch('core.providers.translation.ollama_m2m100_local.OllamaM2M100LocalProvider') as factory:
            resolve_translation(registry,'http://localhost',fallback_runtime='isolated')
            factory.assert_called_once_with(ollama_host='http://localhost',runtime='isolated')
        registry.get_active.return_value=dict(kind='local_file',local_path='nllb')
        with patch('core.providers.resolve._local',return_value=dict(adapter='nllb')),patch('core.providers.translation.nllb_local.NLLBLocalProvider') as factory:
            resolve_translation(registry,'localhost',fallback_runtime='isolated')
            factory.assert_called_once_with('nllb')

    def test_default_fallback_preflight_avoids_parent_transformers(self):
        from core.runtime_checks import preflight
        registry=Mock(get_active=Mock(return_value=None))
        with patch.object(runtime,'validate') as validate,patch.object(runtime,'model_contract') as contract,patch('core.runtime_checks._engine') as engine:
            preflight(registry,dict(lang='hi',m2m100_runtime='isolated'),'subtitle_translate')
        validate.assert_called_once();contract.assert_called_once();engine.assert_not_called()

    def test_portable_contains_bound_plan_and_recipe(self):
        spec=importlib.util.spec_from_file_location('m2m_portable',ROOT/'packaging/build_portable.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with patch.object(builder,'ROOT',self.root),patch.object(builder,'ROOT_FILES',()),patch.object(builder,'TREES',()):
            paths={relative for _,relative,_ in builder.entries([builder.TRANSLATION_PROFILE])}
        self.assertIn(runtime.PLAN,paths)
        self.assertIn('runtime_profiles/translation-candidate/routing-recipe.json',paths)
        self.assertNotIn('settings.json',paths)


if __name__=='__main__':unittest.main()
