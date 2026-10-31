"""One bounded, offline F5 import with stack evidence; no model construction."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CODE=r'''
import faulthandler,json,sys,time
from pathlib import Path
destination=Path(sys.argv[1]);faulthandler.dump_traceback_later(40)
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('F5 diagnostic networking disabled')
sys.addaudithook(offline);started=time.monotonic()
try:
    import torch
    torch.set_num_threads(2)
    from f5_tts.api import F5TTS
    result=dict(import_passed=True,api_present=callable(F5TTS) and callable(getattr(F5TTS,'infer',None)),model_constructed=False,seconds=round(time.monotonic()-started,3))
except Exception as error:
    import traceback
    result=dict(import_passed=False,error=repr(error),traceback=traceback.format_exc(),model_constructed=False,seconds=round(time.monotonic()-started,3))
finally:
    faulthandler.cancel_dump_traceback_later()
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
'''
def main():
    from core.optional_runtime import interpreter
    from core.render_context import RenderContext,bind_job,run_process
    job=RenderContext(ROOT/'temp');report=dict(import_passed=False,model_constructed=False,packages_installed=False,models_downloaded=False)
    try:
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','REFLOW_OFFLINE':'1','PYTHONIOENCODING':'utf-8',
            'OMP_NUM_THREADS':'2','TEMP':str(job.workspace),'TMP':str(job.workspace),'HF_HOME':str(job.workspace/'hf'),'TORCH_HOME':str(job.workspace/'torch'),'MPLCONFIGDIR':str(job.workspace/'matplotlib')}
        with bind_job(job),(ROOT/'docs/validation/2026-10-16-f5-import-stack.log').open('wb') as log:
            try:
                run_process([interpreter('f5'),'-B','-X','utf8','-c',CODE,str(job.workspace/'result.json')],env=env,stdout=log,stderr=log,check=True,timeout=75)
            except subprocess.TimeoutExpired:report['timed_out']=True
        result=job.workspace/'result.json'
        if result.is_file():report.update(json.loads(result.read_text()))
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-f5-import-diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
