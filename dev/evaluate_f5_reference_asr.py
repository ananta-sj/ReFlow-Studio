"""Actual automatic reference transcription with installed F5/Whisper assets."""
import json,os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CODE=r'''
import sys,os,json,time,re,faulthandler
from pathlib import Path
root,destination=map(Path,sys.argv[1:]);sys.path.insert(0,str(root));faulthandler.dump_traceback_later(60,repeat=True)
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Reference ASR audit is offline')
sys.addaudithook(offline);started=time.monotonic();report=dict(passed=False,f5_speech_model_constructed=False,models_downloaded=False)
try:
    from core.feature_worker import speech_setup,prepare_f5_reference
    dll=speech_setup()
    import torch
    torch.set_num_threads(2)
    from core.f5_imports import load_f5_api
    load_f5_api()
    reference=root/'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/examples/basic/basic_ref_en.wav'
    audio,text=prepare_f5_reference(dict(reference_audio=str(reference),device='cpu'))
    from f5_tts.infer import utils_infer
    words=lambda value:re.findall(r'\w+',value.casefold())
    report.update(passed=bool(text.strip()),transcript=text,expected_words_match=words(text)==words('Some call me nature, others call me mother nature.'),
        reference_asr_released=utils_infer.asr_pipe is None,preprocessed_reference_exists=Path(audio).is_file())
except Exception as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    faulthandler.cancel_dump_traceback_later();report['seconds']=time.monotonic()-started;destination.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
'''
def main():
    from core.optional_runtime import interpreter
    from core.render_context import RenderContext,bind_job,run_process
    job=RenderContext(ROOT/'temp');report=dict(passed=False,models_downloaded=False,packages_installed=False)
    try:
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'2',
            'TEMP':str(job.workspace),'TMP':str(job.workspace),'MPLCONFIGDIR':str(job.workspace/'matplotlib'),'PATH':str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')}
        with bind_job(job),(ROOT/'docs/validation/2026-10-16-f5-reference-asr-worker.log').open('wb') as log:
            try:run_process([interpreter('f5'),'-B','-X','utf8','-c',CODE,str(ROOT),str(job.workspace/'result.json')],env=env,stdout=log,stderr=log,timeout=300,check=True)
            except subprocess.TimeoutExpired:report['timed_out']=True
        if (job.workspace/'result.json').is_file():report.update(json.loads((job.workspace/'result.json').read_text(encoding='utf-8')))
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-f5-reference-asr.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
