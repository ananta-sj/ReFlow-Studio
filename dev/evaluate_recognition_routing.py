"""Offline saved-setting to pipeline acceptance in the clean desktop runtime."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
import importlib.util,json,os,re,sys,threading,time,types
from pathlib import Path
root,scratch,label=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',
                  REFLOW_WORKER_PYTHON='invalid-global-worker-override',
                  PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
report=dict(passed=False,checks={},packages_added=False,models_downloaded=False,defaults_changed=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
try:
    from core.settings import Settings
    from core.pipeline_contracts import SettingsSnapshot,RegistrySnapshot,PipelineSpec
    from core.runtime_checks import preflight
    from core.recognition_runtime import validate
    from core.runtime_probe import probe
    from core.render_context import RenderContext,bind_job,RenderCancelled
    from core.providers.resolve import resolve_stt
    from core.run_manifest import RunManifest
    from pipeline import ReflowPipeline
    store=Settings();store.update(dict(recognition_runtime='isolated',xtts_runtime='isolated'))
    snapshot=SettingsSnapshot(store.all())
    check('saved_setting_reloaded',Settings().get('recognition_runtime')=='isolated')
    route=validate();report['runtime']=route
    entry=dict(id='recognition-evaluation',stage_type='stt',kind='local_file',status='installed',
               display_name='Existing converted Whisper',local_path=str(root/'models/whisper/ct2-turbo-candidate-compat/model'))
    registry=RegistrySnapshot(dict(entries=[entry],active={'stt':entry['id']}))
    preflight(registry,dict(lang='source',keep_bg=False,recognition_runtime=snapshot.get('recognition_runtime'),
              xtts_runtime='isolated',compute_device='cpu'),'audio_dub')
    check('real_preflight_without_parent_engine',True)
    status=probe('faster_whisper',route['executable'],'cpu');report['probe']=status
    check('real_dependency_probe',status['status']=='passed' and status['model_loaded'] is False)
    audio=root/'docs/validation/2026-10-14-desktop-candidate-speech.wav'
    hindi_profile=root/'models/indicf5/references/abhishek/profile.json'
    hindi=json.loads(hindi_profile.read_text(encoding='utf-8'))
    outputs={}
    for language,source in [('auto',audio),('hi',hindi_profile.parent/hindi['reference_audio'])]:
        subject=ReflowPipeline.__new__(ReflowPipeline);subject.registry=registry
        subject._manifest=RunManifest(scratch/'records',PipelineSpec('audio_dub',dict(target_lang='source',source_language=language)),source,registry,snapshot)
        subject._manifest.capture_source(source)
        job=RenderContext(scratch/'jobs')
        try:
            with bind_job(job):result=subject._transcribe_and_translate(str(source),'source',snapshot,source_language=language)
            operation=next(row for row in subject._manifest.data['operations'] if row['stage']=='stt')
            check('manifest_runtime_'+language,operation['engine']['runtime']=='isolated' and operation['engine']['runtime_identity']==route['identity'] and operation['engine']['worker_interpreter']==route['executable'])
            check('worker_released_'+language,not job.processes)
            outputs[language]=result.to_payload()
        finally:
            job.cleanup();check('workspace_removed_'+language,not job.workspace.exists())
    report['transcripts']=outputs
    check('english_exact',re.findall(r'\w+',' '.join(row['text'] for row in outputs['auto']['segments']).casefold())==re.findall(r'\w+','Good morning. This is the portable speech test.'.casefold()))
    check('automatic_confidence_preserved',outputs['auto']['language']=='en' and outputs['auto']['language_probability']>.8)
    check('explicit_hindi_metadata',outputs['hi']['language']=='hi' and outputs['hi']['language_origin']=='hint' and outputs['hi']['language_probability'] is None)
    check('hindi_script',any('\u0900'<=c<='\u097f' for row in outputs['hi']['segments'] for c in row['text']))
    # A later setting change cannot redirect an accepted job snapshot.
    store.update(dict(recognition_runtime='legacy'))
    check('running_snapshot_unchanged',snapshot.get('recognition_runtime')=='isolated')
    provider=resolve_stt(registry,'medium',runtime=snapshot.get('recognition_runtime'))
    job=RenderContext(scratch/'jobs')
    try:
        try:
            with bind_job(job):provider.transcribe(str(scratch/'missing.wav'))
        except RuntimeError as error:check('bounded_worker_error','Transcription worker failed' in str(error) and len(str(error))<6500)
        else:check('bounded_worker_error',False)
    finally:job.cleanup()
    job=RenderContext(scratch/'jobs');outcomes=[]
    def run():
        try:
            with bind_job(job):provider.transcribe(str(audio))
        except RenderCancelled:outcomes.append('cancelled')
        except BaseException as error:outcomes.append(repr(error))
        else:outcomes.append('unexpected success')
    thread=threading.Thread(target=run);thread.start();deadline=time.monotonic()+30;children=[]
    try:
        while thread.is_alive() and time.monotonic()<deadline:
            with job.lock:children=list(job.processes)
            if children:break
            time.sleep(.02)
        check('owned_worker_observed',bool(children))
        started=time.monotonic();job.request_stop();thread.join(30)
        report['cancel_seconds']=round(time.monotonic()-started,3)
        check('cancelled_child_exited',not thread.is_alive() and outcomes==['cancelled'] and all(child.poll() is not None for child in children))
    finally:job.cleanup()
    check('desktop_has_no_ai_packages',all(importlib.util.find_spec(name) is None for name in ['torch','transformers','faster_whisper']))
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (root/f'docs/validation/2026-10-16-recognition-routing-{label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
'''


def main():
    label = sys.argv[1] if len(sys.argv)>1 else 'real'
    assert label.replace('-', '').isalnum()
    with tempfile.TemporaryDirectory(prefix='recognition-routing-', dir=ROOT/'temp') as scratch:
        with (ROOT/f'docs/validation/2026-10-16-recognition-routing-{label}.log').open('wb') as log:
            result = subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'), '-B', '-X', 'utf8', '-c',
                                     CODE, str(ROOT), scratch, label], stdout=log, stderr=subprocess.STDOUT, timeout=360,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('Recognition routing exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
