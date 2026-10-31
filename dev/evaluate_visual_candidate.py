"""Actual guarded face restoration and owned-child stop from a clean parent."""
import importlib.util,json,os,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',REFLOW_OFFLINE='1',REFLOW_WORKER_PYTHON='invalid-global-override')

def main():
    from core.visual_runtime import validate,MODELS
    from core.providers.enhancer.gfpgan_local import GFPGANLocalProvider
    from core.runtime_probe import probe
    from core.render_context import RenderContext,bind_job,run_process,RenderCancelled
    from core.runtime_integrity import sha
    report=dict(passed=False,checks={},models_downloaded=False,quality_accepted=False)
    def check(name,value):
        report['checks'][name]=bool(value);print(name,bool(value),flush=True)
        if not value:raise AssertionError(name)
    hashes={name:sha(ROOT/'gfpgan/weights'/name) for name in MODELS}
    job=RenderContext(ROOT/'temp');done=threading.Event();thread=None
    try:
        route=validate();report['runtime']=route
        # The root gfpgan/weights folder is a namespace, not an installed engine.
        check('clean_parent_without_ai',all(importlib.util.find_spec(name) is None for name in ['torch','cv2']) and importlib.util.find_spec('gfpgan').origin is None)
        result=probe('gfpgan',route['executable'],'cpu');report['probe']=result
        check('guarded_dependency_probe',result['status']=='passed' and result.get('training_launchers_disabled') and not result['model_loaded'])
        with bind_job(job):
            source=job.workspace/'source.mp4';output=job.workspace/'result.mp4'
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-ss','2','-i',str(ROOT/'Sample/2.mp4'),'-t','1','-vf','fps=3,scale=640:-2','-an','-c:v','libx264',str(source)],check=True,timeout=60)
            engine=GFPGANLocalProvider(device='cpu',runtime='isolated');started=time.monotonic()
            engine.enhance(str(source),str(output));report['inference_seconds']=round(time.monotonic()-started,3)
            check('actual_face_model_forwards',engine.last_worker_evidence['face_model_forward_calls']==3 and engine.last_worker_evidence['guarded'])
            info=json.loads(run_process([str(ROOT/'ffmpeg/bin/ffprobe.exe'),'-v','error','-show_streams','-of','json',str(output)],capture_output=True,text=True,check=True,timeout=30).stdout)
            video=next(row for row in info['streams'] if row['codec_type']=='video')
            check('three_decodable_frames',int(video['nb_frames'])==3 and abs(float(video['duration'])-1)<.1)
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-i',str(output),'-f','null','-'],capture_output=True,check=True,timeout=30)
            check('actual_runtime_evidence',engine.runtime_identity==route['identity'] and engine.worker_interpreter==route['executable'])
            check('worker_exited',not job.processes)
            original=sha(output)
            # Invalid input must fail through the real worker and preserve an existing result.
            try:engine.enhance(str(job.workspace/'missing.mp4'),str(output))
            except RuntimeError:check('worker_failure_preserves_output',sha(output)==original)
            else:check('worker_failure_preserves_output',False)
            def stop():
                deadline=time.monotonic()+60
                while not done.wait(.02) and time.monotonic()<deadline:
                    with job.lock:active=[process for process in job.processes if process.poll() is None]
                    if active:report['cancel_pid']=active[0].pid;report['stop_at']=time.monotonic();job.request_stop();return
            thread=threading.Thread(target=stop,daemon=True);thread.start()
            try:engine.enhance(str(source),str(output))
            except RenderCancelled:check('cancellation_type_preserved',True)
            else:check('cancellation_type_preserved',False)
            report['cancel_return_seconds']=round(time.monotonic()-report.pop('stop_at'),3)
            check('cancelled_worker_exited',not job.processes)
            check('cancellation_preserves_output',sha(output)==original)
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        done.set()
        if thread:thread.join(timeout=2)
        job.cleanup();report['workspace_removed']=not job.workspace.exists()
        report['model_hashes_preserved']=hashes=={name:sha(ROOT/'gfpgan/weights'/name) for name in MODELS}
        report['model_sha256']=hashes
        (ROOT/'docs/validation/2026-10-16-visual-candidate-real.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
