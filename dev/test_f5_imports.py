"""Exact-source lazy import preserves upstream invocation and fails on drift."""
import hashlib,sys,types,unittest
from unittest.mock import Mock,patch
from core import f5_imports as adapter

class F5ImportTests(unittest.TestCase):
    def test_transcription_dependency_is_loaded_only_when_called_and_arguments_survive(self):
        payload=b'from transformers import pipeline\ndef invoke(*args, **kwargs):\n    return pipeline(*args, **kwargs)\n'
        with patch.object(adapter,'SOURCE_SHA256',hashlib.sha256(payload).hexdigest()):source=adapter.deferred_source(payload)
        module={};real_import=__import__
        def blocked(name,*args,**kwargs):
            if name=='transformers':raise AssertionError('Eager Transformers import')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=blocked):exec(compile(source,'fixture.py','exec'),module)
        upstream=Mock(return_value='actual result');fake=types.ModuleType('transformers');fake.pipeline=upstream
        with patch.dict(sys.modules,{'transformers':fake}):self.assertEqual(module['invoke']('automatic-speech-recognition',model='local',device='cpu'),'actual result')
        upstream.assert_called_once_with('automatic-speech-recognition',model='local',device='cpu')
        self.assertTrue(module['__reflow_reference_asr_deferred__'])
    def test_source_drift_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'source changed'):adapter.deferred_source(b'changed')
    def test_training_is_deferred_but_export_preserved_and_cached(self):
        payload=(adapter.TRAINER_IMPORT+'__all__ = ["Trainer"]\n').encode()
        with patch.object(adapter,'MODEL_SHA256',hashlib.sha256(payload).hexdigest()):source=adapter.deferred_model_source(payload)
        module=types.ModuleType('fixture');real_import=__import__
        def blocked(name,*args,**kwargs):
            if name=='f5_tts.model.trainer':raise AssertionError('Eager training import')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=blocked):exec(compile(source,'fixture.py','exec'),module.__dict__)
        trainer=object()
        with patch('builtins.__import__',return_value=types.SimpleNamespace(Trainer=trainer)) as load:
            self.assertIs(module.Trainer,trainer);self.assertIs(module.Trainer,trainer)
        load.assert_called_once();self.assertIn('Trainer',module.__all__)
        with self.assertRaises(AttributeError):module.unknown
    def test_model_source_drift_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'source changed'):adapter.deferred_model_source(b'changed')
    def test_ambiguous_import_is_rejected_even_with_matching_digest(self):
        payload=(adapter.NEEDLE*2).encode()
        with patch.object(adapter,'SOURCE_SHA256',hashlib.sha256(payload).hexdigest()):
            with self.assertRaisesRegex(RuntimeError,'reviewed source'):adapter.deferred_source(payload)
    def test_wrong_version_is_rejected_before_import(self):
        with patch.object(adapter.metadata,'version',return_value='other'),patch.object(adapter.importlib,'import_module') as load:
            with self.assertRaisesRegex(RuntimeError,'reviewed f5-tts'):adapter.load_f5_api()
        load.assert_not_called()
    def test_import_hook_is_removed_on_failure(self):
        before=list(sys.meta_path)
        with self.assertRaisesRegex(RuntimeError,'stop'):
            with adapter.defer_reference_asr():raise RuntimeError('stop')
        self.assertEqual(sys.meta_path,before)
    def test_finder_ignores_unrelated_modules(self):
        with patch.object(adapter.importlib.machinery.PathFinder,'find_spec') as locate:
            self.assertIsNone(adapter._Finder().find_spec('unrelated'))
        locate.assert_not_called()
if __name__=='__main__':unittest.main()
