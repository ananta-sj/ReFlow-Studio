"""Voice/lip-sync stop signals survive wrappers without publishing partial output."""
import io,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from core.render_context import RenderCancelled
from core.rvc.rvc_handler import RVCHandler
from core.lipsync_handler import LipSyncHandler
ROOT=Path(__file__).resolve().parents[1]

class OptionalCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'temp');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.wav';self.source.write_bytes(b'original input')
        self.output=self.root/'output.wav';self.output.write_bytes(b'previous valid output')
        self.weights=self.root/'actor.pth';self.weights.write_bytes(b'fixture only; never loaded')
        self.clean=self.root/'owned-preprocessed.wav';self.clean.write_bytes(b'owned temporary data')
    def test_rvc_asset_cancellation_does_not_become_initialization_error(self):
        stop=RenderCancelled('stop during assets');factory=Mock()
        with patch.dict(sys.modules,{'rvc_python.infer':SimpleNamespace(RVCInference=factory)}),patch('core.model_assets.ensure_assets',side_effect=stop):
            with self.assertRaises(RenderCancelled) as result:RVCHandler('cpu')
        self.assertIs(result.exception,stop);factory.assert_not_called()
    def rvc_stop(self,phase):
        stop=RenderCancelled('stop '+phase);subject=RVCHandler.__new__(RVCHandler);subject.ready=True
        def load_model(path,**kwargs):
            if phase=='load':raise stop
        def infer_file(input_path,output_path):
            Path(output_path).write_bytes(b'partial owned output')
            raise stop
        subject.inference=SimpleNamespace(load_model=load_model,infer_file=infer_file,set_params=Mock())
        with patch('core.model_contract.local_contract',return_value=dict(rvc_version='v2')),patch.object(subject,'preprocess_audio',return_value=str(self.clean)):
            with self.assertRaises(RenderCancelled) as result:subject.infer(str(self.source),str(self.output),'actor',model_path=str(self.weights))
        self.assertIs(result.exception,stop);self.assertEqual(self.output.read_bytes(),b'previous valid output')
        self.assertEqual(self.source.read_bytes(),b'original input');self.assertFalse(self.clean.exists());self.assertFalse(list(self.root.glob('.reflow-*')))
    def test_rvc_model_load_cancellation_preserves_output_and_cleans_preprocessing(self):self.rvc_stop('load')
    def test_rvc_conversion_cancellation_preserves_output_and_cleans_pending(self):self.rvc_stop('infer')
    def test_wav2lip_worker_cancellation_survives_cp1252_console(self):
        stop=RenderCancelled('stop live child');stream=io.TextIOWrapper(io.BytesIO(),encoding='cp1252')
        try:
            with patch('core.lipsync_handler.config.BASE_DIR',str(self.root)),patch('core.lipsync_handler.config.TEMP_PATH',str(self.root)), \
                 patch('core.lipsync_handler.worker_python',return_value='fixture-python'),patch('core.lipsync_handler.run_process',side_effect=stop),patch('sys.stdout',stream):
                subject=LipSyncHandler(model_path=str(self.weights),device='cpu')
                with self.assertRaises(RenderCancelled) as result:subject.execute(str(self.source),str(self.source),str(self.output))
                stream.flush()
            self.assertIs(result.exception,stop);self.assertEqual(self.output.read_bytes(),b'previous valid output')
        finally:stream.close()
if __name__=='__main__':unittest.main()
