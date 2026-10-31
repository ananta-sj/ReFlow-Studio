"""Exercise actual XTTS speech/cancellation offline, preserving existing app state."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import argparse
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'runtime_profiles/xtts-candidate'
OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
                  PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def main():
    global PROFILE
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='initial')
    parser.add_argument('--profile',choices=['xtts-candidate','xtts-security-candidate'],default='xtts-candidate')
    parser.add_argument('--probe-label',default='audited-network')
    args=parser.parse_args()
    PROFILE=ROOT/'runtime_profiles'/args.profile
    assert args.label.replace('-','').isalnum()
    label=args.label
    assert Path(sys.executable).resolve()==(PROFILE/'python.exe').resolve()
    probe_file=f'2026-10-13-{args.profile}-runtime-probe'+('' if args.probe_label=='initial' else '-'+args.probe_label)+'.json'
    probe=json.loads((OUT/probe_file).read_text(encoding='utf-8'))
    assert probe['passed']
    network=[]
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
            import traceback
            network.append(dict(event=event,address=repr(args[1:]),blocked=True,
                stack=traceback.format_stack(limit=8)))
            raise RuntimeError('XTTS evaluation forbids network operations')
    sys.addaudithook(offline)
    from core.render_context import RenderContext,RenderCancelled,bind_job,run_process
    from core.audio_utils import load_speech_audio
    from core import generation_control
    from transformers import StoppingCriteria
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(0)
    job=RenderContext(ROOT/'temp')
    os.environ.update(HF_HOME=str(job.workspace/'hf'),TORCH_HOME=str(job.workspace/'torch'),
                     XDG_CACHE_HOME=str(job.workspace/'cache'),XDG_DATA_HOME=str(job.workspace/'data'),
                     TTS_HOME=str(job.workspace/'tts'),MPLCONFIGDIR=str(job.workspace/'matplotlib'),
                     NUMBA_CACHE_DIR=str(job.workspace/'numba'),TEMP=str(job.workspace),TMP=str(job.workspace))
    report=dict(acceptance=False,offline=True,release_eligible=False,model_downloaded=False,
                application_defaults_changed=False,network_attempts=network,checks={},python=sys.version)
    started=time.monotonic()
    try:
        if args.profile=='xtts-security-candidate':
            from dev.xtts_security_compat import activate
            report['compatibility_adapter']=activate()
        from core.tts.tts_handler import TTSHandler
        reference=job.workspace/'reference.wav'
        with bind_job(job):
            run_process(['ffmpeg','-v','error','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),
                         '-t','6','-vn','-ar','24000','-ac','1',str(reference)],check=True,timeout=60)
        before=time.monotonic()
        model=TTSHandler(device='cpu',model_path=str(ROOT/'models/xtts/default'),language='en')
        report['model_load_seconds']=round(time.monotonic()-before,3)
        synthesizer_id=id(model.tts.synthesizer.tts_model)
        output=job.workspace/'successful.wav'
        text='Good morning. This is a test of the isolated Reflow speech runtime.'
        before=time.monotonic()
        with bind_job(job):model.generate_audio(text,str(output),'en',str(reference))
        report['generation_seconds']=round(time.monotonic()-before,3)
        clip=load_speech_audio(str(output))
        report['checks']['real_non_silent_speech']=len(clip)>500 and clip.max>0
        report['checks']['decoder_rate_preserved']=clip.frame_rate==model.tts.synthesizer.tts_model.hifigan_decoder.output_sample_rate==24000
        report.update(output_duration_seconds=len(clip)/1000,output_sample_rate=clip.frame_rate,
                      output_dbfs=clip.dBFS,spoken_text=text)
        retained=OUT/(f'2026-10-13-{args.profile}-success.wav' if label=='initial' else f'2026-10-13-{args.profile}-success-{label}.wav')
        assert not retained.exists(),'Preserve previous evaluation audio'
        retained.write_bytes(output.read_bytes())
        report['output_file']=str(retained)
        report['output_sha256']=hashlib.sha256(retained.read_bytes()).hexdigest()
        prior=hashlib.sha256(output.read_bytes()).hexdigest()
        observed=threading.Event()
        original=generation_control.generation_kwargs
        class ObservedCriteria(StoppingCriteria):
            def __init__(self,criteria):self.criteria=criteria
            def __call__(self,input_ids,scores,**kwargs):
                observed.set()
                return self.criteria(input_ids,scores,**kwargs)
            def __deepcopy__(self,memo):return self
        def instrument():
            values=original()
            values['stopping_criteria']=[ObservedCriteria(c) for c in values['stopping_criteria']]
            return values
        def synthesize():
            with bind_job(job):model.generate_audio('This is a longer speech cancellation check. '*8,str(output),'en',str(reference))
        with patch.object(generation_control,'generation_kwargs',instrument),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(synthesize)
            if not observed.wait(120):
                job.request_stop()
                if future.done():future.result()
                raise RuntimeError('No real generation token boundary observed')
            before=time.monotonic();job.request_stop()
            try:future.result(timeout=20)
            except RenderCancelled:report['cancellation_seconds']=round(time.monotonic()-before,3)
            else:raise RuntimeError('Real XTTS did not honor cancellation')
        report['checks']['real_token_boundary_cancellation']=True
        report['checks']['successful_output_preserved']=hashlib.sha256(output.read_bytes()).hexdigest()==prior
        report['checks']['cancelled_staging_removed']=not list(job.workspace.glob('.reflow-*'))
        report['checks']['loaded_model_reused']=id(model.tts.synthesizer.tts_model)==synthesizer_id
        report['checks']['all_network_operations_blocked']=all(row['blocked'] for row in network)
        report['checks']['no_outbound_or_dns_attempts']=not any(row['event']!='socket.bind' for row in network)
        report['acceptance']=all(report['checks'].values())
    except Exception as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        job.cleanup()
        report['checks']['workspace_removed']=not job.workspace.exists()
        report['acceptance']=report['acceptance'] and report['checks']['workspace_removed']
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        destination=OUT/(f'2026-10-13-{args.profile}-live-evaluation.json' if label=='initial' else f'2026-10-13-{args.profile}-live-evaluation-{label}.json')
        assert not destination.exists(),'Preserve previous evaluation evidence'
        destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    return not report['acceptance']

if __name__=='__main__':raise SystemExit(main())
