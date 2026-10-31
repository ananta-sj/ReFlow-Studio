"""Two ordinary offline renders: real inference, then verified stage reuse."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ.update(PYTHONIOENCODING='utf-8', REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT/'ffmpeg/bin') + os.pathsep + os.environ.get('PATH','')


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def main():
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    source=ROOT/'docs/validation/2026-10-09-pipeline-foundation-full-known-91f5371e/source-excerpt.mp4'
    folder=ROOT/'docs/validation'/('2026-10-09-stage-checkpoints-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    state={name:sha(ROOT/name) for name in ('models.json','settings.json')}
    report=dict(source=str(source),source_sha256=sha(source), no_fixture_text_or_reused_audio=True,
                output_folder=str(folder),passes=[])
    for number in (1,2):
        job=RenderContext(ROOT/'temp');started=time.monotonic()
        item=dict(pass_number=number)
        try:
            with bind_job(job):
                pipe=ReflowPipeline();pipe.output_dir=str(folder)
                for stage,preset in [('stt','whisper_turbo'),('translation','indictrans2'),('tts','indicf5')]:
                    if (pipe.registry.get_active(stage) or {}).get('request_preset') != preset:
                        raise RuntimeError('Expected existing selected engine: '+stage)
                try:
                    for percent,status,output in pipe.run('video_dub',str(source),dict(target_lang='hi',
                            source_language='auto',cast_list=['CLONED_USER'],compute_device='cpu',
                            keep_background=False,parallel_workers=1)):
                        print(number,percent,status,flush=True)
                        if output:item['output']=output
                except Exception as error:
                    item.update(error_type=type(error).__name__,error=str(error))
                item['manifest_path']=pipe.last_manifest_path
        finally:
            job.cleanup();item['workspace_removed']=not job.workspace.exists()
        item['elapsed_seconds']=time.monotonic()-started
        manifest=json.loads(Path(item['manifest_path']).read_text(encoding='utf-8'))
        item.update(status=manifest['status'],checkpoints=manifest['checkpoints'],
            inference_counts={stage:sum(op['stage']==stage for op in manifest['operations']) for stage in ('stt','translation','speech')})
        speech_input=next(a for a in manifest['cue_artifacts'] if a['phase']=='speech-input')
        item['speech_input']=json.loads(Path(speech_input['path']).read_text(encoding='utf-8'))
        item['cue_count']=len(item['speech_input']['segments'])
        report['passes'].append(item)
        print('PASS RECORD',number,item['elapsed_seconds'],item['inference_counts'],flush=True)
    first,second=report['passes']
    report.update(settings_unchanged=state=={name:sha(ROOT/name) for name in state},
        source_unchanged=report['source_sha256']==sha(source),
        identical_speech_input=first['speech_input']==second['speech_input'],
        second_reused_both={e['stage'] for e in second['checkpoints'] if e['status']=='hit'}=={'stt','translation'},
        no_second_stt_or_translation=second['inference_counts']['stt']==second['inference_counts']['translation']==0,
        both_blocked_before_speech=all(p['status']=='failed' and p['inference_counts']['speech']==0
            and 'available' in p.get('error','').lower() for p in report['passes']))
    report['passed']=all(report[field] for field in ('settings_unchanged','source_unchanged','identical_speech_input',
        'second_reused_both','no_second_stt_or_translation','both_blocked_before_speech'))
    report['passed'] &= first['inference_counts']['stt']==1 and first['inference_counts']['translation']==14
    path=folder.with_suffix('.json');path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPORT',path,'passed=',report['passed'],flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
