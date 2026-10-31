"""Real subprocess boundaries without Torch; inference/HTTP use test fixtures."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
import importlib.abc,sys,types,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
root=Path(sys.argv[1]);sys.path[:0]=[str(root),str(root/'core')]
attempts=[]
class NoTorch(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0]=='torch':
            attempts.append(fullname)
            raise ModuleNotFoundError('Torch deliberately unavailable')
sys.meta_path.insert(0,NoTorch())
if sys.argv[2]=='translation':
    from llm_translator import LLMTranslator
    tags=Mock();tags.json.return_value={'models':[{'name':'llama3:latest'}]}
    reply=Mock();reply.json.return_value={'response':'नमस्ते दुनिया।'}
    with patch('llm_translator.requests.get',return_value=tags),patch('llm_translator.requests.post',return_value=reply):
        provider=LLMTranslator()
        result=provider.translate('Hello world.','Hindi',source_language='en')
    assert result=='नमस्ते दुनिया।' and provider.mode=='ollama'
else:
    fake=types.ModuleType('faster_whisper')
    class Engine:
        supported_languages=['en','hi']
        def __init__(self,*args,**kwargs):
            assert kwargs['device']=='cpu' and kwargs['compute_type']=='int8'
            assert kwargs['local_files_only'] is True
        def transcribe(self,path,**kwargs):
            expected={'beam_size':5,'vad_filter':True}
            if sys.argv[2]=='recognition-hint':expected['language']='hi'
            assert kwargs==expected
            return [types.SimpleNamespace(start=0,end=1,text='Hello world.')],types.SimpleNamespace(duration=1,language='en',language_probability=.99)
    fake.WhisperModel=Engine;sys.modules['faster_whisper']=fake
    from stt.stt_handler import STTHandler
    with tempfile.TemporaryDirectory(dir=root/'temp') as folder:
        selected='hi' if sys.argv[2]=='recognition-hint' else 'auto'
        result=STTHandler(model_size=folder).transcribe('fixture.wav',source_language=selected)
        if sys.argv[2]=='recognition-unsupported':
            try:STTHandler(model_size=folder).transcribe('fixture.wav',source_language='pcm')
            except ValueError as error:assert 'does not support' in str(error)
            else:raise AssertionError('Unsupported hint silently accepted')
    assert result[0]['text']=='Hello world.'
    if selected=='hi':assert result.language=='hi' and result.language_probability is None and result.language_origin=='hint'
    else:assert result.language=='en' and result.language_probability==.99
assert not attempts,attempts
print('No Torch import attempted:',sys.argv[2])
'''


class EngineImportBoundaryTests(unittest.TestCase):
    def run_phase(self, phase):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', CODE, str(ROOT), phase],
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('No Torch import attempted', result.stdout)

    def test_ollama_wrapper_does_not_require_torch(self):
        self.run_phase('translation')

    def test_faster_whisper_handler_does_not_require_torch(self):
        self.run_phase('recognition')

    def test_faster_whisper_explicit_hint_reaches_engine(self):
        self.run_phase('recognition-hint')

    def test_faster_whisper_rejects_unsupported_language(self):
        self.run_phase('recognition-unsupported')


if __name__ == '__main__':
    unittest.main()
