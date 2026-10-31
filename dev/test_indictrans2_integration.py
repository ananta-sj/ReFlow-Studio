"""Language, asset, worker-lifetime, routing and connection boundaries."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from core.providers.translation.indictrans2_local import IndicTrans2LocalProvider
from core.render_context import RenderContext, RenderCancelled, bind_job
from core.source_language import SourceLanguage
from core.providers import resolve
from core.model_registry import ModelRegistry
from dev.test_render_queue import api
from dev.test_speech_integrity import pipeline

ROOT = Path(__file__).resolve().parents[1]


class IndicTrans2IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT / 'temp')))
        self.assets = self.stack.enter_context(patch('core.providers.translation.indictrans2_local.validate_assets',
            return_value={'adapter':'indictrans2','model_path':'fixture'}))
        self.provider = IndicTrans2LocalProvider('fixture')
        self.runtime = self.stack.enter_context(patch('core.providers.translation.indictrans2_local.isolated_interpreter', return_value='fixture-python'))
        self.worker = self.stack.enter_context(patch('core.feature_session.FeatureSession'))

    def test_dialogue_options_are_bounded_and_use_existing_session(self):
        self.worker.return_value.call.return_value = {'candidates':['एक पंक्ति','दूसरी पंक्ति']}
        job = RenderContext(self.root)
        try:
            with bind_job(job):
                result = self.provider.suggest_dialogue('A source line','Hindi',source_language='en')
                self.assertEqual(len(result),2)
                self.worker.return_value.call.assert_called_once_with(dict(text='A source line',source='eng_Latn',target='hin_Deva',mode='dialogue_options',max_candidates=3), timeout=180)
                self.provider.release()
        finally: job.cleanup()
        self.worker.return_value.close.assert_called_once()

    def test_dialogue_option_budget_and_language_fail_before_worker(self):
        for limit in (0,4,True):
            with self.assertRaises(ValueError): self.provider.suggest_dialogue('Source','Hindi',source_language='en',max_candidates=limit)
        with self.assertRaises(ValueError): self.provider.suggest_dialogue('Source','French',source_language='en')
        self.worker.assert_not_called()

    def test_wrong_source_target_and_instructions_fail_before_worker(self):
        for target, source, instructions in [('Hindi','ta',''), ('English','en',''),
                ('Hindi',None,''), ('Hindi',SourceLanguage('en','detected',.5),''),
                ('Hindi','en','make casual')]:
            with self.subTest(target=target, source=source), self.assertRaises(ValueError):
                self.provider.translate('hello', target, instructions, source)
        self.worker.assert_not_called()
        self.runtime.assert_not_called()

    def test_reuses_one_worker_and_releases_at_stage_boundary(self):
        job = RenderContext(self.root)
        try:
            self.worker.return_value.job = job
            self.worker.return_value.call.side_effect = [{'translation':'नमस्ते'}, {'translation':'धन्यवाद'}]
            with bind_job(job):
                self.assertEqual(self.provider.translate('Hello','Hindi',source_language='en'),'नमस्ते')
                self.assertEqual(self.provider.translate('Thanks','Hindi',source_language='en'),'धन्यवाद')
                pipeline._release_translation(self.provider)
            self.worker.assert_called_once()
            self.worker.return_value.close.assert_called_once()
            self.assertIsNone(self.provider.session)
        finally:
            job.cleanup()

    def test_blank_response_is_failure_and_cannot_cross_jobs(self):
        job = RenderContext(self.root)
        other = RenderContext(self.root)
        try:
            self.worker.return_value.job = job
            self.worker.return_value.call.return_value = {'translation':' '}
            with bind_job(job), self.assertRaisesRegex(RuntimeError, 'nonempty'):
                self.provider.translate('Hello','Hindi',source_language='en')
            with bind_job(other), self.assertRaisesRegex(RuntimeError, 'different render job'):
                self.provider.translate('Hello','Hindi',source_language='en')
            self.provider.release()
        finally:
            job.cleanup()
            other.cleanup()

    def test_selected_contract_routes_to_indictrans_instead_of_nllb(self):
        registry = Mock()
        registry.get_active.return_value = dict(stage_type='translation',kind='local_file',local_path='fixture')
        with patch.object(resolve, '_local', return_value={'adapter':'indictrans2'}):
            self.assertIsInstance(resolve.resolve_translation(registry, ''), IndicTrans2LocalProvider)

    def test_translation_stage_closes_worker_before_returning(self):
        subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        subject.registry = Mock()
        subject.clear_vram = Mock()
        subject._transcribe_source = Mock(return_value=pipeline.normalize_transcription(
            {'segments':[dict(start=0,end=2,text='hello')], 'language':'en','language_probability':.99}))
        self.provider.translate = Mock(return_value='नमस्ते')
        self.provider.release = Mock()
        subject._resolve_translation_and_filter = Mock(return_value=(self.provider,'',None,''))
        with patch.object(pipeline.providers, 'resolve_stt'):
            subject._transcribe_and_translate('fixture.wav','hi',Mock(),source_language='en')
        self.provider.release.assert_called_once()
        subject.clear_vram.assert_called_once()

    def test_failed_or_cancelled_translation_releases_worker_and_keeps_original_error(self):
        for error in (RuntimeError('translation fixture failure'), RenderCancelled('Stopped')):
            subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
            subject.registry = Mock()
            subject.clear_vram = Mock()
            subject._save_cues = Mock()
            subject._transcribe_source = Mock(return_value=pipeline.normalize_transcription(
                {'segments':[dict(start=0,end=2,text='hello')], 'language':'en','language_probability':.99}))
            self.provider.translate = Mock(side_effect=error)
            self.provider.release = Mock(side_effect=OSError('cleanup fixture failure'))
            subject._resolve_translation_and_filter = Mock(return_value=(self.provider,'',None,''))
            with patch.object(pipeline.providers, 'resolve_stt'), self.assertRaises(type(error)) as caught:
                subject._transcribe_and_translate('fixture.wav','hi',Mock(),source_language='en')
            self.provider.release.assert_called_once()
            self.assertIn(str(error), str(caught.exception))
            subject._save_cues.assert_not_called()

    def test_release_failure_after_success_is_visible_before_next_stage(self):
        provider = Mock(engine_id='indictrans2')
        provider.release.side_effect = OSError('release fixture failure')
        with self.assertRaisesRegex(OSError, 'release fixture failure'):
            with pipeline._translation_stage(provider):
                pass
        provider.release.assert_called_once()


class IndicTrans2ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT / 'temp')))
        self.stack.enter_context(patch('core.model_registry.REGISTRY_PATH',str(self.root/'registry.json')))
        self.stack.enter_context(patch('core.indictrans2_assets.installed_path',return_value=self.root))
        (self.root / 'model.safetensors').write_bytes(b'fixture weights')
        self.validation = self.stack.enter_context(patch('core.indictrans2_assets.validate_assets',return_value={'revision':'pinned'}))
        self.runtime = self.stack.enter_context(patch('core.indictrans2_assets.isolated_interpreter',return_value='fixture-python'))
        self.bridge = api.PythonBridge.__new__(api.PythonBridge)
        self.bridge.registry = ModelRegistry()
        self.bridge._render_lock = threading.Lock()
        self.bridge._deletion_busy = Mock(return_value=False)

    def test_connect_is_idempotent_and_preserves_active_selection(self):
        old = self.bridge.registry.add('translation','cloud_api','Existing')
        first = self.bridge.connect_indictrans2()
        self.assertTrue(first['ok'],first)
        second = self.bridge.connect_indictrans2()
        self.assertEqual(first['model']['id'],second['model']['id'])
        self.assertEqual(self.bridge.registry.get_active('translation')['id'],old['id'])
        self.assertEqual(len(self.bridge.registry.list('translation')),2)

    def test_busy_or_missing_assets_do_not_mutate_registry(self):
        self.bridge._deletion_busy.return_value = True
        self.assertFalse(self.bridge.connect_indictrans2()['ok'])
        self.bridge._deletion_busy.return_value = False
        self.validation.side_effect = ValueError('Pinned asset changed')
        self.assertFalse(self.bridge.connect_indictrans2()['ok'])
        self.assertFalse(self.bridge.indictrans2_status()['ready'])
        self.assertEqual(self.bridge.registry.list(),[])

    def test_cpu_workspace_still_reports_gpu_translation_route_and_memory(self):
        connected = self.bridge.connect_indictrans2()
        self.assertTrue(connected['ok'], connected)
        self.bridge.registry.set_active('translation', connected['model']['id'])
        self.bridge.monitor = Mock()
        self.bridge.monitor.base_stage_cost.return_value = 2
        self.bridge.monitor.base_stage_vram_mb.return_value = 2000
        self.bridge.monitor.device_kind.side_effect = lambda device: 'cpu' if device == 'cpu' else 'cuda'
        result = self.bridge._resource_estimate(10, ['translate'], 'cpu', {'parallel_workers':1})
        self.assertEqual(result['stage_devices']['translate'], 'cuda:0')
        self.assertTrue(any('IndicTrans2' in warning for warning in result['warnings']))
        self.assertGreater(result['peak_vram_by_device_mb']['cuda:0'], 0)


class IndicTrans2AssetTests(unittest.TestCase):
    def test_changed_model_code_is_rejected_before_execution(self):
        from core import indictrans2_assets as assets
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as name:
            root = Path(name)
            model = root/'model'
            model.mkdir()
            (root/'core/vendor/indictrans2').mkdir(parents=True)
            processor = root/'core/vendor/indictrans2/processor.py'
            processor.write_bytes(b'reviewed processor')
            code = model/'modeling_indictrans.py'
            code.write_bytes(b'reviewed code')
            weight = model/'model.safetensors'
            weight.write_bytes(b'original')
            manifest = dict(revision='fixture',processor_sha256=hashlib.sha256(processor.read_bytes()).hexdigest(),
                files=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                       for p in (code,weight)])
            (root/'core/indictrans2_manifest.json').write_text(json.dumps(manifest))
            with patch.object(assets,'project_root',return_value=root):
                self.assertEqual(assets.validate_assets(model)['adapter'],'indictrans2')
                code.write_bytes(b'modified code')
                with self.assertRaisesRegex(ValueError,'identity changed'):
                    assets.validate_assets(model)
                code.write_bytes(b'reviewed code')
                weight.write_bytes(b'modified')  # Same length; worker must check the full hash.
                assets.validate_assets(model)
                with self.assertRaisesRegex(ValueError,'identity changed'):
                    assets.validate_assets(model,verify_weights=True)


class DialogueProcessorTests(unittest.TestCase):
    def test_every_alternative_has_a_fresh_consumable_source_record(self):
        from core.indictrans2_worker import postprocess_candidate
        from types import SimpleNamespace
        instances=[]
        class Processor:
            def __init__(self,inference):
                self.records=[]
                instances.append(self)
            def preprocess_batch(self,texts,src_lang,tgt_lang):
                self.records.extend(texts)
            def postprocess_batch(self,decoded,lang):
                if not self.records: raise AssertionError('Source record consumed twice')
                source=self.records.pop(0)
                return [item.replace('<ID>',source) for item in decoded]
        module=SimpleNamespace(IndicProcessor=Processor)
        results=[postprocess_candidate(module,'42','eng_Latn','hin_Deva',[f'<ID> beam{i}']) for i in range(3)]
        self.assertEqual(results,['42 beam0','42 beam1','42 beam2'])
        self.assertEqual(len(instances),3)
        self.assertTrue(all(not p.records for p in instances))


if __name__ == '__main__':
    unittest.main()
