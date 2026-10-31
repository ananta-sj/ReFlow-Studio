"""Python 3.13 syntax and limited wheel smoke; not a Demucs runtime acceptance."""
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import json,sys,zipfile,hashlib,os,tempfile
from pathlib import Path
root=Path(sys.argv[1]);folder=root/'docs/validation'
build=json.loads((folder/'2026-10-16-separation-helpers/build-receipt.json').read_text())
report=dict(passed=False,checks={},full_demucs_import_tested=False,dora_import_tested=False,runtime_installed=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
try:
    check('target_python',sys.version_info[:3]==(3,13,16))
    # Initialize the unchanged vetted Torch before restricting helper execution;
    # its Windows loader queries the operating-system version in a subprocess.
    dll_handle=os.add_dll_directory(str(root/'ffmpeg/shared_libs'))
    import torch
    torch.set_num_threads(2)
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen'}:raise RuntimeError('Smoke networking and child processes disabled')
    sys.addaudithook(offline)
    wheels=[];count=0
    for row in build['packages']:
        wheel=root/row['wheel'];check('hash_'+row['name'],hashlib.sha256(wheel.read_bytes()).hexdigest()==row['wheel_sha256'])
        wheels.append(str(wheel))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith('.py'):
                    compile(archive.read(name),str(wheel)+'/'+name,'exec');count+=1
    check('all_126_sources_compile',count==126)
    sys.path[:0]=wheels
    import antlr4
    from antlr4.Token import CommonToken
    stream=antlr4.InputStream('hello');check('antlr_stream',stream.LA(1)==ord('h'))
    token=CommonToken(type=7);token.text='hello';check('antlr_token',token.type==7 and token.text=='hello')
    import demucs
    check('demucs_package_version',demucs.__version__=='4.0.1')
    import torch,julius
    torch.set_num_threads(2)
    audio=torch.ones((1,100))
    value=julius.resample_frac(audio,100,200)
    check('julius_real_resampling',tuple(value.shape)==(1,200) and bool(torch.isfinite(value).all()))
    import torchaudio,soundfile
    with tempfile.TemporaryDirectory(prefix='separation-audio-io-',dir=root/'temp') as scratch:
        path=Path(scratch)/'stem.wav'
        signal=torch.sin(torch.arange(4410,dtype=torch.float32)*.03).repeat(2,1)*.1
        torchaudio.save(str(path),signal,sample_rate=44100,encoding='PCM_S',bits_per_sample=16)
        decoded,rate=soundfile.read(path)
        check('modern_audio_writer_roundtrip',decoded.shape==(4410,2) and rate==44100)
    for module in (antlr4,demucs,julius):check('wheel_origin_'+module.__name__,any(str(module.__file__).startswith(wheel) for wheel in wheels))
    report.update(passed=True,compiled_sources=count,torch_version=torch.__version__)
except Exception as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (folder/'2026-10-16-separation-helpers-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''


def main():
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'2'}
    return subprocess.run([str(ROOT/'runtime_profiles/xtts-security-candidate/python.exe'),'-B','-X','utf8','-c',CODE,str(ROOT)],env=env,timeout=90).returncode


if __name__=='__main__':raise SystemExit(main())
