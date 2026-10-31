"""Bounded stack capture after the exact-source F5 lazy-ASR adapter."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CODE=r'''
import sys,json,time,faulthandler
from pathlib import Path
destination,root=map(Path,sys.argv[1:]);sys.path.insert(0,str(root))
faulthandler.dump_traceback_later(20,repeat=True)
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Diagnostic network access disabled')
sys.addaudithook(offline);started=time.monotonic()
try:
    import torch
    torch.set_num_threads(2)
    from core import f5_imports
    original=f5_imports.deferred_source
    def observed(payload):
        result=original(payload);destination.with_suffix('.phase.json').write_text(json.dumps(dict(source_transformed=True,source_transformed_at_seconds=time.monotonic()-started)));return result
    f5_imports.deferred_source=observed
    engine=f5_imports.load_f5_api()
    result=dict(import_passed=True,seconds=time.monotonic()-started,model_constructed=False,transformers_loaded='transformers' in sys.modules,trainer_loaded='f5_tts.model.trainer' in sys.modules,wandb_loaded='wandb' in sys.modules)
except Exception as error:
    import traceback
    result=dict(import_passed=False,error=repr(error),traceback=traceback.format_exc(),model_constructed=False)
finally:
    faulthandler.cancel_dump_traceback_later();destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
'''
def main():
    from core.optional_runtime import interpreter
    from core.render_context import RenderContext,bind_job,run_process
    job=RenderContext(ROOT/'temp');report=dict(import_passed=False,model_constructed=False)
    try:
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'2','REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
            'TEMP':str(job.workspace),'TMP':str(job.workspace),'MPLCONFIGDIR':str(job.workspace/'matplotlib')}
        with bind_job(job),(ROOT/'docs/validation/2026-10-16-f5-lazy-startup-stack.log').open('wb') as log:
            try:run_process([interpreter('f5'),'-B','-X','utf8','-c',CODE,str(job.workspace/'result.json'),str(ROOT)],env=env,stdout=log,stderr=log,timeout=55,check=True)
            except subprocess.TimeoutExpired:report['timed_out']=True
        for name in ['result.json','result.phase.json']:
            path=job.workspace/name
            if path.is_file():report.update(json.loads(path.read_text(encoding='utf-8')))
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-f5-lazy-startup.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
