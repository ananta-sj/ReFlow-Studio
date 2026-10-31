"""Actual short English video with isolated separation, recognition and XTTS."""
from pathlib import Path
import subprocess,tempfile,os
ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import json,sys,os,types,time,importlib.util
from pathlib import Path
root,scratch=map(Path,sys.argv[1:]);sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    REFLOW_WORKER_PYTHON='invalid-global-override',PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
from core.settings import Settings
from core.pipeline_contracts import RegistrySnapshot
from core.render_context import RenderContext,bind_job,run_process
from core.separation_runtime import validate
from pipeline import ReflowPipeline
report=dict(passed=False,human_quality_accepted=False,translation_tested=False,source_language='en',target_language='source',events=[],checks={})
def check(name,value):
    report['checks'][name]=bool(value);print(name,bool(value),flush=True)
    if not value:raise AssertionError(name)
folder=root/'docs/validation/2026-10-16-separation-video';folder.mkdir(exist_ok=True)
job=RenderContext(root/'temp');started=time.monotonic()
try:
    store=Settings();store.update(dict(separation_runtime='isolated',recognition_runtime='isolated',xtts_runtime='isolated'))
    check('saved_separation_choice_reloaded',Settings().get('separation_runtime')=='isolated')
    check('clean_desktop_parent',all(importlib.util.find_spec(name) is None for name in ['torch','demucs','transformers']))
    source=folder/'source.mp4'
    with bind_job(job):
        run_process([str(root/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-i',str(root/'Sample/2.mp4'),'-t','6','-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','veryfast','-c:a','aac',str(source)],check=True,timeout=120)
        weights=json.loads((root/'core/recovery_sources.json').read_text())['xtts']['folder']
        stt=dict(id='stt',stage_type='stt',kind='local_file',status='installed',display_name='Existing converted Whisper',local_path=str(root/'models/whisper/ct2-turbo-candidate-compat/model'))
        tts=dict(id='tts',stage_type='tts',kind='local_file',status='installed',display_name='Existing XTTS',local_path=str(root/weights))
        subject=ReflowPipeline.__new__(ReflowPipeline);subject.registry=RegistrySnapshot(dict(entries=[stt,tts],active={'stt':'stt','tts':'tts'}));subject.root_dir=str(root);subject.output_dir=str(folder);subject.temp_dir=str(job.workspace)
        params=dict(target_lang='source',source_language='en',cast_list=['CLONED_USER'],compute_device='cpu',keep_background=True,
            user_voice_path=str(root/'docs/validation/2026-10-14-desktop-candidate-speech.wav'),include_subtitles=True,export_stems=True,parallel_workers=1)
        output=None
        for percent,message,result in subject.run('video_dub',str(source),params):
            report['events'].append(dict(percent=percent,message=message));print(percent,message,flush=True)
            if result:output=result
        check('complete_video_published',bool(output) and Path(output).is_file())
        media=json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',output],check=True,capture_output=True,text=True,timeout=60).stdout)
        check('video_audio_subtitle_streams',{'video','audio','subtitle'}<={row['codec_type'] for row in media['streams']})
        check('source_timeline_preserved',abs(float(media['format']['duration'])-6)<.15)
        run_process(['ffmpeg','-v','error','-nostdin','-i',output,'-f','null','-'],check=True,capture_output=True,timeout=120)
        check('complete_decode',True)
        manifest=json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'));route=validate()
        separation=[row for row in manifest['operations'] if row['stage']=='separate']
        check('actual_separation_runtime_in_manifest',len(separation)==1 and separation[0]['engine']['runtime_identity']==route['identity'] and separation[0]['engine']['worker_interpreter']==route['executable'])
        check('manifest_completed',manifest['status']=='completed')
        check('all_stage_workers_released',not job.processes)
        report.update(output=output,manifest=subject.last_manifest_path,duration_seconds=float(media['format']['duration']),passed=True)
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc());raise
finally:
    job.cleanup();report.update(workspace_removed=not job.workspace.exists(),seconds=round(time.monotonic()-started,3))
    (root/'docs/validation/2026-10-16-separation-video.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
'''
def main():
    with tempfile.TemporaryDirectory(prefix='separation-video-state-',dir=ROOT/'temp') as scratch:
        return subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'),'-B','-X','utf8','-c',CODE,str(ROOT),scratch],env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=600).returncode
if __name__=='__main__':raise SystemExit(main())
