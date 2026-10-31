"""Actual isolated CPU stems, repeatability, probe and process cancellation."""
import json,os,sys,threading,time,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='2',REFLOW_WORKER_PYTHON='invalid-global-override')

def main():
    from core.separation_runtime import validate
    from core.runtime_probe import probe
    from core.audio_separator import AudioSeparator
    from core.audio_utils import load_playable_audio
    from core.render_context import RenderContext,bind_job,run_process,RenderCancelled
    from core.runtime_integrity import sha
    report=dict(passed=False,checks={},quality_accepted=False,models_downloaded=False)
    def check(name,value):
        report['checks'][name]=bool(value);print(name,bool(value),flush=True)
        if not value:raise AssertionError(name)
    job=RenderContext(ROOT/'temp');done=threading.Event();thread=None
    try:
        route=validate();report['runtime']=route
        check('parent_has_no_ai_packages',all(importlib.util.find_spec(name) is None for name in ['torch','torchaudio','demucs']))
        result=probe('demucs',route['executable'],'cpu');report['probe']=result
        check('actual_dependency_probe',result['status']=='passed' and result['model_loaded'] is False)
        with bind_job(job):
            source=job.workspace/'source.wav'
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-i',str(ROOT/'Sample/2.mp4'),'-t','1','-vn','-ac','2','-ar','44100',str(source)],check=True,timeout=60)
            report['runs']=[]
            for index in range(2):
                engine=AudioSeparator('cpu',runtime='isolated');before=time.monotonic();paths=engine.separate(str(source))
                clips=[load_playable_audio(path) for path in paths]
                check('playable_stems_'+str(index),all(abs(len(clip)-1000)<=50 and clip.channels==2 and clip.frame_rate==44100 for clip in clips))
                check('actual_candidate_evidence_'+str(index),engine.worker_interpreter==route['executable'] and engine.runtime_identity==route['identity'])
                check('worker_exited_'+str(index),not job.processes)
                report['runs'].append(dict(hashes=[sha(path) for path in paths],sample_width=[clip.sample_width for clip in clips],rms=[clip.rms for clip in clips],seconds=round(time.monotonic()-before,3)))
            check('repeated_output_identical',report['runs'][0]['hashes']==report['runs'][1]['hashes'])
            check('pcm16_output',report['runs'][0]['sample_width']==[2,2])
            engine=AudioSeparator('cpu',runtime='isolated')
            def stop():
                deadline=time.monotonic()+60
                while not done.wait(.02) and time.monotonic()<deadline:
                    with job.lock:active=[process for process in job.processes if process.poll() is None]
                    if active:
                        report['cancel_pid']=active[0].pid;report['stop_at']=time.monotonic();job.request_stop();return
            thread=threading.Thread(target=stop,daemon=True);thread.start()
            try:engine.separate(str(source))
            except RenderCancelled:check('exact_cancellation',True)
            else:check('exact_cancellation',False)
            report['cancel_return_seconds']=round(time.monotonic()-report.pop('stop_at'),3)
            check('cancelled_child_exited',not job.processes)
        report['passed']=True
    except BaseException as error:
        import traceback
        report.update(error=repr(error),traceback=traceback.format_exc());raise
    finally:
        done.set()
        if thread:thread.join(timeout=2)
        job.cleanup();report['workspace_removed']=not job.workspace.exists()
        (ROOT/'docs/validation/2026-10-16-separation-candidate-real.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
