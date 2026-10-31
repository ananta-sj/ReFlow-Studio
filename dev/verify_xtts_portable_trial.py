"""Run the relocated portable interpreter/provider without copied model weights."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'dist/portable-xtts-trial-2026-10-13'
CODE=r'''
import json,os,sys,hashlib,threading,time
from pathlib import Path
from types import SimpleNamespace
root=Path(sys.argv[1]);source=Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
from core.xtts_runtime import validate
from core.providers.resolve import resolve_tts
from core.providers.base import release_speech
from core.render_context import RenderContext,bind_job,run_process,RenderCancelled
from core.settings import Settings
from core.audio_utils import load_speech_audio
import core.xtts_runtime
report=dict(passed=False,checks={},native_ui_test=False,model_weights_copied=False)
job=RenderContext(root/'temp')
settings_path=root/'settings.json';owned_settings=False
try:
    if settings_path.exists():raise RuntimeError('Expected a fresh portable copy without saved settings')
    report['checks']['imports_relocated']=Path(core.xtts_runtime.__file__).is_relative_to(root)
    report['runtime']=validate();report['checks']['runtime_relocated']=Path(report['runtime']['executable']).is_relative_to(root)
    settings=Settings();report['checks']['fresh_default_legacy']=settings.get('xtts_runtime')=='legacy'
    settings.update({'xtts_runtime':'isolated'})
    owned_settings=True
    entry=dict(kind='local_file',stage_type='tts',local_path=str(source/'models/xtts/default'))
    registry=SimpleNamespace(get_active=lambda stage:entry if stage=='tts' else None)
    with bind_job(job):
        reference=job.workspace/'reference.wav'
        run_process(['ffmpeg','-v','error','-y','-ss','2','-i',str(source/'Sample/2.mp4'),'-t','6','-vn','-ar','24000','-ac','1',str(reference)],check=True,timeout=60)
        provider=resolve_tts(registry,'cpu',runtime=settings.get('xtts_runtime'))
        output=job.workspace/'speech.wav'
        provider.synthesize('Good morning. This is the portable speech test.',str(output),'en',str(reference))
        load_speech_audio(str(output));report['checks']['saved_selection_generated_speech']=provider.runtime=='isolated'
        retained=source/'docs/validation/2026-10-13-xtts-portable-trial-speech.wav'
        retained.write_bytes(output.read_bytes());report['speech_sha256']=hashlib.sha256(output.read_bytes()).hexdigest()
        before=output.read_bytes();previous_session=provider.session
        owned_children=list(job.processes)
        release_speech(provider)
        report['checks']['speech_stage_worker_released']=len(owned_children)==1 and previous_session.closed and all(child.poll() is not None for child in owned_children)
        report['checks']['release_keeps_job_running']=not job.cancelled.is_set()
        if job.cancelled.is_set():raise RuntimeError('Speech-stage release cancelled the enclosing job')
        outcome=[]
        def cancelled_call():
            try:
                with bind_job(job):provider.synthesize('This deliberately longer sentence tests cancellation during portable speech generation.',str(output),'en',str(reference))
            except RenderCancelled:outcome.append('cancelled')
            except BaseException as error:outcome.append(type(error).__name__+': '+str(error))
            else:outcome.append('unexpected-success')
        thread=threading.Thread(target=cancelled_call);thread.start();deadline=time.monotonic()+240
        boundary=False
        while thread.is_alive() and time.monotonic()<deadline:
            active=getattr(provider,'session',None)
            if active is not previous_session and (active.folder/'token-boundary').exists():
                boundary=True;break
            time.sleep(.02)
        if not boundary:
            active=getattr(provider,'session',None)
            report['cancel_call_outcome']=outcome
            report['call_thread_alive']=thread.is_alive()
            report['second_worker_finished']=active.finished.is_set()
            report['second_model_ready']=(active.folder/'model-ready').exists()
            report['worker_diagnostic']=active._diagnostic()
            raise RuntimeError('No generation token boundary observed within startup allowance')
        started=time.monotonic();job.request_stop();thread.join(timeout=30)
        report['cancel_seconds']=round(time.monotonic()-started,3)
        report['checks']['generation_cancelled']=not thread.is_alive() and outcome==['cancelled']
        report['checks']['cancel_preserved_output']=output.read_bytes()==before
        release_speech(provider)
except BaseException as error:
    import traceback
    report.update(error=str(error),traceback=traceback.format_exc())
finally:
    job.cleanup();report['checks']['workspace_removed']=not job.workspace.exists()
    if owned_settings:settings_path.unlink(missing_ok=True)
    report['checks']['test_settings_removed']=owned_settings and not settings_path.exists()
    report['checks']['no_weights_installed']=not (root/'models/xtts/default').exists()
report['passed']='error' not in report and all(report['checks'].values())
(source/'docs/validation/2026-10-13-xtts-portable-trial-live.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
'''
def main():
    if not (TARGET/'portable-manifest.json').is_file():raise RuntimeError('Portable build must finish before this trial')
    return subprocess.run([str(TARGET/'build/windows-portable/python.exe'),'-B','-X','utf8','-c',CODE,str(TARGET),str(ROOT)],cwd=TARGET,timeout=600).returncode
if __name__=='__main__':raise SystemExit(main())
