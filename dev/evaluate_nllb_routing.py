"""Real isolated NLLB from a Torch-free desktop, with stage lifetime checks."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
import importlib.util,json,os,sys,time,threading,types
from pathlib import Path
root,scratch,label=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3];sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  PYTHONDONTWRITEBYTECODE='1',REFLOW_WORKER_PYTHON='invalid-general-override',
                  PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
report=dict(passed=False,checks={},models_downloaded=False,packages_added=False,defaults_changed=False)
def check(name,value):
    report['checks'][name]=bool(value);print(name,bool(value),flush=True)
    if not value:raise AssertionError(name)
job=None
try:
    from core.settings import Settings
    from core.pipeline_contracts import SettingsSnapshot,RegistrySnapshot,PipelineSpec
    from core.render_context import RenderContext,bind_job,RenderCancelled
    from core.runtime_checks import preflight
    from core.nllb_runtime import validate
    from core.runtime_probe import probe
    from core.run_manifest import RunManifest,bind_manifest
    from core.source_language import resolve_source_language
    from pipeline import ReflowPipeline,_translation_stage
    store=Settings();store.update(dict(nllb_runtime='isolated'))
    settings=SettingsSnapshot(store.all());route=validate();report['runtime']=route
    entry=dict(id='nllb-fixture',stage_type='translation',kind='local_file',status='installed',
               local_path=str(root/'models/translation/nllb_600M'),display_name='Existing NLLB')
    registry=RegistrySnapshot(dict(entries=[entry],active={'translation':entry['id']}))
    preflight(registry,dict(lang='hi',nllb_runtime=settings.get('nllb_runtime')),'subtitle_translate')
    check('saved_selection_and_real_preflight',Settings().get('nllb_runtime')=='isolated')
    report['probe']=probe('nllb',route['executable'],'cpu')
    check('actual_dependency_probe',report['probe']['status']=='passed' and report['probe']['model_loaded'] is False)
    pipeline=ReflowPipeline.__new__(ReflowPipeline);pipeline.registry=registry
    source=scratch/'source.srt';source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello world.\n')
    pipeline._manifest=RunManifest(scratch/'records',PipelineSpec('subtitle_translate',dict(target_lang='hi',source_language='en')),source,registry,settings)
    pipeline._manifest.capture_source(source)
    provider,instructions,filter_provider,filter_instructions=pipeline._resolve_translation_and_filter(settings)
    job=RenderContext(root/'temp')
    with bind_job(job),bind_manifest(pipeline._manifest),_translation_stage(provider):
        first=pipeline._translate_line('Hello world.','Hindi',provider,'',None,'',source_language=resolve_source_language('en'))
        first_pid=provider.last_result['worker_pid'];session=provider.session
        second=pipeline._translate_line('नमस्ते दुनिया।','English',provider,'',None,'',source_language=resolve_source_language('hi'))
        check('same_process_single_model_load',provider.last_result['worker_pid']==first_pid and provider.last_result['model_loads']==1)
        check('model_never_loaded_in_desktop',provider._model is None and provider._tokenizer is None)
        check('hindi_and_english_outputs',any('\u0900'<=c<='\u097f' for c in first) and second=='Hello world.')
        report['translations']=dict(hindi=first,english=second)
    check('stage_release_does_not_cancel_job',provider.session is None and session.finished.is_set() and not job.cancelled.is_set() and not job.processes)
    operation=next(row for row in pipeline._manifest.data['operations'] if row['stage']=='translation')
    check('manifest_records_actual_runtime',operation['engine']['runtime_identity']==route['identity'] and operation['engine']['worker_interpreter']==route['executable'])
    job.cleanup();check('success_workspace_removed',not job.workspace.exists());job=None
    # A second warm session proves cancellation while decoder checks are active.
    job=RenderContext(root/'temp')
    with bind_job(job):provider.translate('Good morning.','Hindi',source_language='en')
    session=provider.session;marker=session.folder/'token-boundary'
    marker.unlink(missing_ok=True);outcomes=[]
    def run():
        try:
            with bind_job(job):provider.translate('Before long, a standard news report visual language established itself, one that is immediately recognisable to anyone. '*4,'Hindi',source_language='en')
        except RenderCancelled:outcomes.append('cancelled')
        except BaseException as error:outcomes.append(repr(error))
        else:outcomes.append('unexpected_success')
    thread=threading.Thread(target=run);thread.start();deadline=time.monotonic()+60
    while thread.is_alive() and not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
    check('active_decoder_boundary_observed',marker.exists() and thread.is_alive())
    started=time.monotonic();job.request_stop();thread.join(30)
    check('generation_cancel_acknowledged',not thread.is_alive() and outcomes==['cancelled'])
    provider.release();report['cancel_and_release_seconds']=round(time.monotonic()-started,3)
    check('cancelled_worker_exited',session.finished.is_set() and not job.processes)
    job.cleanup();check('cancel_workspace_removed',not job.workspace.exists());job=None
    check('desktop_remains_without_torch_transformers',all(importlib.util.find_spec(name) is None for name in ['torch','transformers']))
    report['semantic_quality_accepted']=False
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    if job is not None:job.cleanup()
    (root/f'docs/validation/2026-10-16-nllb-routing-{label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''


def main():
    label = sys.argv[1] if len(sys.argv)>1 else 'real'
    assert label.replace('-', '').isalnum()
    with tempfile.TemporaryDirectory(prefix='nllb-routing-', dir=ROOT/'temp') as scratch:
        with (ROOT/f'docs/validation/2026-10-16-nllb-routing-{label}.log').open('wb') as log:
            result = subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'), '-B', '-X', 'utf8',
                                     '-c', CODE, str(ROOT), scratch, label], stdout=log, stderr=subprocess.STDOUT, timeout=480,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('NLLB routing exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
