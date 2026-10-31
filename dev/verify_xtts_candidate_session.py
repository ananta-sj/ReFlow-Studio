"""Real existing FeatureSession bridge: model reuse, errors, cancellation/cleanup."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['xtts-candidate','xtts-security-candidate'],default='xtts-candidate');args=parser.parse_args()
    from core.render_context import RenderContext,bind_job,run_process
    from core.feature_session import FeatureSession
    job=RenderContext(ROOT/'temp');session=None;started=time.monotonic()
    report=dict(passed=False,production_integration=False,application_defaults_changed=False,
                existing_model_only=True,checks={})
    try:
        reference=job.workspace/'reference.wav'
        with bind_job(job):
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),
                '-t','6','-vn','-ar','24000','-ac','1',str(reference)],check=True,timeout=60)
        session=FeatureSession(job,str(ROOT/'runtime_profiles'/args.profile/'python.exe'),
            dict(session_label='XTTS candidate',model_path=str(ROOT/'models/xtts/default')),
            worker=ROOT/'dev/xtts_candidate_worker.py',operation='xtts_candidate_session')
        calls=[]
        for index,text in enumerate(['Good morning.','This is a second request using the same voice model.']):
            output=job.workspace/f'speech-{index}.wav'
            response=session.call(dict(text=text,output_path=str(output),language='en',reference_audio=str(reference)),timeout=240)
            assert output.stat().st_size>1000
            calls.append(response)
        report['checks']['two_real_speech_calls']=len(calls)==2
        report['checks']['one_persistent_worker']=len({r['worker_pid'] for r in calls})==1 and all(r['model_loads']==1 for r in calls)
        report['checks']['one_loaded_model']=len({r['model_identity'] for r in calls})==1
        rejected=job.workspace/'rejected.wav'
        try:session.call(dict(text='Test.',output_path=str(rejected),language='source',reference_audio=str(reference)),timeout=30)
        except RuntimeError as error:report['checks']['invalid_language_rejected']='language' in str(error).lower() or 'source' in str(error).lower()
        else:report['checks']['invalid_language_rejected']=False
        report['checks']['rejected_output_not_created']=not rejected.exists()
        output=job.workspace/'speech-1.wav';before=hashlib.sha256(output.read_bytes()).hexdigest()
        (session.folder/'token-boundary').unlink(missing_ok=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(session.call,dict(text='This is a longer cancellation check. '*8,
                output_path=str(output),language='en',reference_audio=str(reference)),240)
            deadline=time.monotonic()+90
            while not (session.folder/'token-boundary').exists():
                if future.done():future.result();raise RuntimeError('Generation ended before cancellation boundary')
                if time.monotonic()>deadline:raise TimeoutError('No real worker generation boundary')
                time.sleep(.05)
            stop=time.monotonic();session.close()
            try:future.result(timeout=15)
            except RuntimeError as error:report['cancel_error']=str(error)
            else:raise RuntimeError('Worker completed long speech instead of cancelling')
            report['stop_seconds']=round(time.monotonic()-stop,3)
        report['checks']['worker_stopped']=session.finished.is_set() and not session.thread.is_alive()
        report['checks']['previous_output_preserved']=hashlib.sha256(output.read_bytes()).hexdigest()==before
        report['checks']['no_incomplete_publication']=not list(job.workspace.glob('.reflow-*'))
        report['worker_pid']=calls[0]['worker_pid']
        report['passed']=all(report['checks'].values())
    except Exception as error:
        import traceback
        report.update(error=str(error),traceback=traceback.format_exc())
    finally:
        if session is not None:
            session.close()
            if session.log.exists():
                (OUT/f'2026-10-13-{args.profile}-session-worker.log').write_bytes(session.log.read_bytes())
        job.cleanup()
        report['checks']['parent_workspace_removed']=not job.workspace.exists()
        report['passed'] &= report['checks']['parent_workspace_removed']
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        (OUT/f'2026-10-13-{args.profile}-session.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return not report['passed']

if __name__=='__main__':raise SystemExit(main())
