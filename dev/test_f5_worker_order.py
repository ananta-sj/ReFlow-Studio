"""Prepare/release reference ASR before loading speech weights; reuse sessions."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import feature_worker as worker
ROOT=Path(__file__).resolve().parents[1]

class F5WorkerOrderTests(unittest.TestCase):
    def params(self):return dict(device='cpu',checkpoint_path='fixture',vocab_path='fixture',recipe='F5TTS_v1_Base',text='Hello',output_path='fixture.wav')
    def test_reference_preparation_precedes_single_shot_model_construction(self):
        events=[];engine=Mock();factory=Mock(side_effect=lambda **kwargs:events.append('construct') or engine)
        with patch.object(worker,'speech_setup'),patch('core.f5_imports.load_f5_api',return_value=factory),patch.object(worker,'prepare_f5_reference',side_effect=lambda params:events.append('reference') or ('ref.wav','Reference.')):
            worker.f5_speech(self.params())
        self.assertEqual(events,['reference','construct']);engine.infer.assert_called_once_with(ref_file='ref.wav',ref_text='Reference.',gen_text='Hello',file_wave='fixture.wav')
    def test_reference_failure_does_not_construct_speech_model(self):
        factory=Mock()
        with patch.object(worker,'speech_setup'),patch('core.f5_imports.load_f5_api',return_value=factory),patch.object(worker,'prepare_f5_reference',side_effect=RuntimeError('ASR failed')):
            with self.assertRaisesRegex(RuntimeError,'ASR failed'):worker.f5_speech(self.params())
        factory.assert_not_called()
    def test_persistent_session_loads_model_after_first_reference_and_reuses_it(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as scratch:
            folder=Path(scratch);events=[];engine=Mock()
            for index in [1,2]:(folder/f'call-{index:08d}.json').write_text(json.dumps(dict(reference_audio='ref.wav',text='Hello',output_path='out.wav')))
            def infer(**kwargs):
                events.append('infer')
                if events.count('infer')==2:(folder/'stop').touch()
            engine.infer.side_effect=infer
            factory=Mock(side_effect=lambda **kwargs:events.append('construct') or engine)
            with patch.object(worker,'speech_setup'),patch('core.f5_imports.load_f5_api',return_value=factory),patch.object(worker,'prepare_f5_reference',side_effect=lambda *args:events.append('reference') or ('ref.wav','Reference.')),patch.object(worker.time,'sleep'):
                worker.f5_session({**self.params(),'session_dir':str(folder)})
            self.assertEqual(events,['reference','construct','infer','reference','infer']);factory.assert_called_once()
            self.assertTrue(all(json.loads(path.read_text())['ok'] for path in folder.glob('*.response.json')))
if __name__=='__main__':unittest.main()
