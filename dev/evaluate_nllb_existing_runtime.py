"""Offline feasibility check with existing NLLB weights and CPU packages."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
import hashlib,json,os,sys,time
from pathlib import Path
root,scratch=Path(sys.argv[1]),Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',HF_HOME=str(scratch/'hf'))
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Offline translation feasibility forbids networking')
sys.addaudithook(offline)
report=dict(passed=False,packages_added=False,models_downloaded=False,checks={})
def check(name,value):
    report['checks'][name]=bool(value)
    print(name,bool(value),flush=True)
    if not value:raise AssertionError(name)
try:
    from core.runtime_integrity import sha
    from core.xtts_runtime import validate
    report['runtime']=validate()
    from core.providers.translation.nllb_local import NLLBLocalProvider
    import torch,transformers
    torch.set_num_threads(2)
    report['versions']=dict(torch=torch.__version__,transformers=transformers.__version__)
    model=root/'models/translation/nllb_600M'
    baseline={path.name:sha(path) for path in model.iterdir() if path.is_file()}
    provider=NLLBLocalProvider(str(model),device='cpu')
    started=time.monotonic()
    provider._ensure_loaded()
    check('loaded_existing_nllb',provider._model is not None)
    print('tokenizer',type(provider._tokenizer).__name__,flush=True)
    cases=[('Hello world.','Hindi','en'),('Good morning. This is a short test.','Hindi','en'),
           ('नमस्ते दुनिया।','English','hi')]
    report['cases']=[]
    for text,target,source in cases:
        translated=provider.translate(text,target,source_language=source)
        report['cases'].append(dict(text=text,target=target,source=source,translation=translated))
        check('nonempty_case_'+str(len(report['cases'])),bool(translated.strip()))
    check('model_files_unchanged',all(sha(model/name)==value for name,value in baseline.items()))
    report['model_sha256']=baseline
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    report['semantic_quality_accepted']=False
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (root/'docs/validation/2026-10-16-nllb-existing-runtime-feasibility.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''


def main():
    with tempfile.TemporaryDirectory(prefix='nllb-feasibility-', dir=ROOT/'temp') as scratch:
        with (ROOT/'docs/validation/2026-10-16-nllb-existing-runtime-feasibility.log').open('wb') as log:
            result = subprocess.run([str(ROOT/'runtime_profiles/xtts-security-candidate/python.exe'), '-B', '-X', 'utf8',
                                     '-c', CODE, str(ROOT), scratch], stdout=log, stderr=subprocess.STDOUT, timeout=480,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('NLLB feasibility exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
