"""One seeded local XTTS take for the exact failing cue; retain raw evidence."""
import json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
CODE=r'''
import sys,os,random,json
from pathlib import Path
root,reference,output=map(Path,sys.argv[1:]);sys.path[:0]=[str(root),str(root/'core')]
import torch,numpy as np
torch.set_num_threads(2)
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Speech diagnosis forbids network access')
sys.addaudithook(offline)
from core.xtts_compat import activate
activate()
from core.tts.tts_handler import TTSHandler
engine=TTSHandler(device='cpu',model_path=str(root/'models/xtts/default'))
random.seed(7);np.random.seed(7);torch.manual_seed(7)
engine.generate_audio("Before long a standard news report visual language established itself, one that's immediately recognizable to any",str(output),'en',str(reference))
'''

def main():
    from core.xtts_runtime import validate
    from core.render_context import RenderContext,bind_job,run_process
    from core.audio_utils import AudioEngineer,load_speech_audio
    from core.runtime_integrity import sha
    report=dict(passed=False,seed=7,models_downloaded=False,packages_installed=False,quality_accepted=False)
    job=RenderContext(ROOT/'temp');started=time.monotonic()
    try:
        route=validate()
        with bind_job(job):
            reference=job.workspace/'reference.wav';output=job.workspace/'raw.wav'
            AudioEngineer().clean_reference_audio(str(ROOT/'docs/validation/2026-10-14-desktop-candidate-speech.wav'),str(reference))
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'2',
                'TEMP':str(job.workspace),'TMP':str(job.workspace),'MPLCONFIGDIR':str(job.workspace),'PATH':str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')}
            with (ROOT/'docs/validation/2026-10-16-speech-overflow-worker.log').open('wb') as log:
                run_process([route['executable'],'-B','-X','utf8','-c',CODE,str(ROOT),str(reference),str(output)],env=env,stdout=log,stderr=log,timeout=600,check=True)
            clip=load_speech_audio(output);frames=clip.get_array_of_samples();channels=clip.channels
            leading=0
            for start in range(0,len(frames),channels):
                if any(frames[start:start+channels]):break
                leading+=1
            trailing=0
            for end in range(len(frames),0,-channels):
                if any(frames[end-channels:end]):break
                trailing+=1
            destination=ROOT/'docs/validation/2026-10-16-speech-overflow-raw.wav';job.publish(output,destination)
            report.update(passed=True,raw_seconds=len(clip)/1000,leading_digital_silence_seconds=leading/clip.frame_rate,
                trailing_digital_silence_seconds=trailing/clip.frame_rate,reference_sha256=sha(reference),output=str(destination),output_sha256=sha(destination),runtime_identity=route['identity'])
    except BaseException as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        report['owned_processes_exited']=not job.processes;job.cleanup();report.update(workspace_removed=not job.workspace.exists(),seconds=round(time.monotonic()-started,3))
        (ROOT/'docs/validation/2026-10-16-speech-overflow-diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
