"""Guarded CPU GFPGAN child; only local media utilities may spawn processes."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]

def main():
    from core.visual_runtime import validate,model_contract
    route=validate()
    if Path(sys.executable).resolve()!=Path(route['executable']).resolve():raise RuntimeError('Visual worker started in the wrong interpreter')
    params=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if params.get('device')!='cpu':raise ValueError('Isolated face enhancement supports CPU only')
    model_contract(params.get('model_path'),verify_weights=True)
    import torch
    torch.set_num_threads(2)
    os.environ.update(BASICSR_JIT='False',BASICSR_EXT='False',TORCH_FORCE_WEIGHTS_ONLY_LOAD='1')
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo','os.system'}:raise RuntimeError('Network/shell execution disabled in isolated face enhancement')
        if event=='subprocess.Popen':
            # Windows may report executable=None and a quoted command line.
            import shlex
            argv=args[1]
            command=shlex.split(argv,posix=False)[0].strip('"') if isinstance(argv,str) else argv[0]
            executable=Path(args[0] or command)
            import shutil
            resolved=Path(shutil.which(str(executable)) or executable).resolve()
            expected=ROOT/'ffmpeg/bin'/resolved.name
            if executable.name.lower() not in {'ffmpeg','ffprobe','ffmpeg.exe','ffprobe.exe'} or resolved!=expected.resolve():raise RuntimeError('Only bundled media utilities may run in this visual worker')
    sys.addaudithook(offline)
    from core.visual_imports import guarded_imports
    with guarded_imports():
        from core.enhancer import FaceEnhancer
    enhancer=FaceEnhancer(device='cpu',upscale=params['upscale'],model_path=params['model_path'])
    forwards=[];hook=enhancer.restorer.gfpgan.register_forward_hook(lambda *args:forwards.append(1))
    try:enhancer.enhance(params['input_path'],params['output_path'])
    finally:hook.remove()
    if params.get('evidence_path'):
        Path(params['evidence_path']).write_text(json.dumps(dict(face_model_forward_calls=len(forwards),guarded=True,device='cpu')),encoding='utf-8')
if __name__=='__main__':main()
