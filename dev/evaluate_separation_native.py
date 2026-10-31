"""Exact installed closure and native origins in the approved interpreter."""
import subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import os,sys,json,importlib,importlib.metadata as metadata
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root))
from core.separation_runtime import validate,LOCK
route=validate();profile=Path(route['profile']);dll=os.add_dll_directory(str(root/'ffmpeg/shared_libs'))
report=dict(passed=False,checks={},model_loaded=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
try:
    check('python_31316',sys.version_info[:3]==(3,13,16))
    check('selected_interpreter',Path(sys.executable).resolve()==Path(route['executable']).resolve())
    actual={}
    for dist in metadata.distributions():
        name=dist.metadata['Name'].lower().replace('_','-').replace('.','-')
        check('unique_'+name,name not in actual);actual[name]=dist.version
    lock=json.loads((root/LOCK).read_text());check('exact_32_package_closure',actual=={row['name']:row['version'] for row in lock['packages']})
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Native checks forbid network access')
    sys.addaudithook(offline)
    for name in ['torch','torchaudio','torchcodec.decoders','numpy','demucs.separate','dora','julius','lameenc','openunmix','omegaconf','soundfile','psutil']:
        module=importlib.import_module(name);check('origin_'+name,Path(module.__file__).resolve().is_relative_to(profile))
    import torch
    check('cpu_arithmetic',bool(torch.all(torch.ones((2,2))@torch.ones((2,2))==2)))
    report.update(passed=True,runtime_identity=route['identity'])
except Exception as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (root/'docs/validation/2026-10-16-separation-candidate-native.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''
def main():return subprocess.run([str(ROOT/'runtime_profiles/separation-candidate/python.exe'),'-B','-X','utf8','-c',CODE,str(ROOT)],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=120).returncode
if __name__=='__main__':raise SystemExit(main())
