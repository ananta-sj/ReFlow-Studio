"""Windows executable=None auditing permits only bundled media tools."""
import contextlib,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import run_visual
ROOT=Path(__file__).resolve().parents[1]

class VisualProcessGuardTests(unittest.TestCase):
    def setUp(self):
        environment=patch.dict('os.environ',clear=False);environment.start();self.addCleanup(environment.stop)
        folder=tempfile.TemporaryDirectory(dir=ROOT/'temp');self.addCleanup(folder.cleanup)
        request=Path(folder.name)/'request.json';request.write_text(json.dumps(dict(device='cpu',upscale=1,model_path='fixture',input_path='in',output_path='out')))
        hooks=[];engine=Mock();engine_module=types.ModuleType('core.enhancer');engine_module.FaceEnhancer=Mock(return_value=engine)
        with patch.object(sys,'argv',['worker',str(request)]),patch('core.visual_runtime.validate',return_value=dict(executable=sys.executable)),patch('core.visual_runtime.model_contract'),patch.dict(sys.modules,{'torch':Mock(),'core.enhancer':engine_module}),patch('core.visual_imports.guarded_imports',return_value=contextlib.nullcontext()),patch.object(sys,'addaudithook',side_effect=hooks.append):
            run_visual.main()
        self.audit=hooks[0]
    def test_windows_none_executable_and_quoted_command_line_are_allowed(self):
        path=ROOT/'ffmpeg/bin/ffprobe.exe'
        with patch('shutil.which',return_value=str(path)):
            self.audit('subprocess.Popen',(None,'"'+str(path)+'" -v error "a b.mp4"',None,{}))
    def test_shell_and_external_media_tools_are_rejected(self):
        for executable in ['cmd.exe','C:/elsewhere/ffmpeg.exe']:
            with self.subTest(executable=executable),patch('shutil.which',return_value=executable):
                with self.assertRaisesRegex(RuntimeError,'Only bundled media utilities'):
                    self.audit('subprocess.Popen',(None,'"'+executable+'" /c test',None,{}))
    def test_network_and_shell_events_are_rejected(self):
        for event in ['socket.connect','socket.bind','socket.getaddrinfo','os.system']:
            with self.subTest(event=event),self.assertRaisesRegex(RuntimeError,'disabled'):self.audit(event,())
