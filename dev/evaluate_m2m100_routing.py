"""Actual offline fallback worker and complete subtitle pipeline acceptance."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import importlib.util,json,os,sys,time,threading,types
from pathlib import Path
from unittest.mock import patch
root,scratch,label=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  PYTHONDONTWRITEBYTECODE='1',REFLOW_WORKER_PYTHON='invalid-general-worker',
                  PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
report=dict(passed=False,checks={},models_downloaded=False,defaults_changed=False,
            ollama_discovery_mocked_unavailable=True,live_api_calls=False)
def check(name,value):
    report['checks'][name]=bool(value);print(name,bool(value),flush=True)
    if not value:raise AssertionError(name)
job=None;provider=None
try:
    import requests
    from core.m2m100_runtime import validate
    from core.runtime_probe import probe
    from core.settings import Settings
    from core.pipeline_contracts import RegistrySnapshot
    from core.render_context import RenderContext,bind_job,RenderCancelled
    from core.providers.translation.m2m100_isolated import IsolatedM2M100Provider
    from pipeline import ReflowPipeline
    from core.srt_utils import parse_srt
    route=validate();report['runtime']=route
    report['probe']=probe('m2m100',route['executable'],'cpu')
    check('real_dependency_probe',report['probe']['status']=='passed' and report['probe']['model_loaded'] is False)
    store=Settings();store.update(dict(m2m100_runtime='isolated'))
    check('saved_choice_reloaded',Settings().get('m2m100_runtime')=='isolated')
    source=scratch/'source.srt'
    source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello world.\n\n2\n00:00:02,000 --> 00:00:04,000\nGood morning.\n',encoding='utf-8')
    pipeline=ReflowPipeline.__new__(ReflowPipeline)
    pipeline.registry=RegistrySnapshot(dict(entries=[],active={}))
    pipeline.output_dir=str(scratch/'outputs');Path(pipeline.output_dir).mkdir(exist_ok=True)
    job=RenderContext(root/'temp')
    with patch('llm_translator.requests.get',side_effect=requests.ConnectionError('offline discovery fixture')),patch('llm_translator.wait_or_cancel'),bind_job(job):
        events=list(pipeline.run('subtitle_translate',str(source),dict(target_lang='hi',source_language='en')))
    output=Path(events[-1][2]);cues=parse_srt(str(output))
    check('complete_subtitle_pipeline_published',output.is_file() and len(cues)==2 and events[-1][0]==100)
    check('subtitle_windows_preserved',[(cue['start'],cue['end']) for cue in cues]==[(0.,2.),(2.,4.)])
    check('subtitle_hindi_output',all(any('\u0900'<=c<='\u097f' for c in cue['text']) for cue in cues))
    manifest=json.loads(Path(pipeline.last_manifest_path).read_text(encoding='utf-8'))
    operations=[row for row in manifest['operations'] if row['stage']=='translation']
    check('manifest_completed_and_runtime_recorded',manifest['status']=='completed' and len(operations)==2 and all(row['engine']['runtime_identity']==route['identity'] and row['engine']['worker_interpreter']==route['executable'] and row['engine']['translation_mode']=='m2m100_isolated' for row in operations))
    report['subtitle_output']=cues
    check('pipeline_worker_released',not job.processes and not job.cancelled.is_set())
    job.cleanup();check('pipeline_workspace_removed',not job.workspace.exists());job=None
    # A direct session supplies real PID/load receipts and stays warm for errors/cancel.
    job=RenderContext(root/'temp');provider=IsolatedM2M100Provider()
    with bind_job(job):
        english_hindi=provider.translate('Hello world.','Hindi',source_language='en')
        pid=provider.last_result['worker_pid'];session=provider.session
        hindi_english=provider.translate('नमस्ते दुनिया।','English',source_language='hi')
        english_french=provider.translate('Good morning.','French',source_language='en')
        check('worker_reused_once_loaded',provider.last_result['worker_pid']==pid and provider.last_result['model_loads']==1)
        check('three_pairs_nonempty',all(isinstance(text,str) and text.strip() for text in [english_hindi,hindi_english,english_french]))
        report['translations']=dict(english_hindi=english_hindi,hindi_english=hindi_english,english_french=english_french)
        try:provider.translate('hello '*2000,'Hindi',source_language='en')
        except RuntimeError as error:check('oversize_input_rejected','limit' in str(error) and 'Split' in str(error))
        else:check('oversize_input_rejected',False)
        check('worker_recovers_after_bad_input',bool(provider.translate('Thank you.','Hindi',source_language='en').strip()) and provider.last_result['worker_pid']==pid)
    marker=session.folder/'token-boundary';marker.unlink(missing_ok=True);outcomes=[]
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
    check('cancel_acknowledged',not thread.is_alive() and outcomes==['cancelled'])
    provider.release();report['cancel_and_release_seconds']=round(time.monotonic()-started,3)
    check('owned_worker_exited',session.finished.is_set() and not job.processes)
    job.cleanup();check('cancel_workspace_removed',not job.workspace.exists());job=None
    check('desktop_remains_without_ai_packages',all(importlib.util.find_spec(name) is None for name in ['torch','transformers','sentencepiece']))
    report['semantic_quality_accepted']=False
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    if provider is not None:provider.release()
    if job is not None:job.cleanup()
    (root/f'docs/validation/2026-10-16-m2m100-routing-{label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''


def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'real'
    assert label.replace('-','').isalnum()
    with tempfile.TemporaryDirectory(prefix='m2m100-routing-',dir=ROOT/'temp') as scratch:
        with (ROOT/f'docs/validation/2026-10-16-m2m100-routing-{label}.log').open('wb') as log:
            result=subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'),'-B','-X','utf8',
                '-c',CODE,str(ROOT),scratch,label],stdout=log,stderr=subprocess.STDOUT,timeout=480,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('M2M100 routing exit:',result.returncode)
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
