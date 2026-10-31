"""Live automatic pipeline on an explicit source excerpt; no speech/text fixtures."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONIOENCODING='utf-8',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--offset',type=float,default=115.6)
    parser.add_argument('--seconds',type=float,default=4.0)
    parser.add_argument('--source-language',default='auto',choices=['auto','en'])
    parser.add_argument('--use-saved-engines',action='store_true',help='Use the real app selection, without an in-memory registry')
    args=parser.parse_args()
    if not (0<=args.offset<=118 and 1<=args.seconds<=120 and args.offset+args.seconds<=122.53):
        parser.error('Excerpt must be within the known source video')
    from core.pipeline import ReflowPipeline
    from core.providers import resolve
    from core.providers.tts.indicf5_local import load_reference_profile
    from core.cue_review import digest
    from core.render_context import RenderContext,bind_job,run_process
    from dev.verify_workflows import FixtureRegistry
    source=ROOT/'Sample/2.mp4'
    folder=ROOT/'docs/validation'/('2026-10-09-automatic-hindi-video-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    report=dict(completed=False,source=str(source),source_sha256=digest(source),
        source_offset_seconds=args.offset,excerpt_seconds=args.seconds,source_language_setting=args.source_language,
        new_independent_source=False,no_transcript_or_translation_fixtures=True,
        prior_takes_reused=False,editorial_timing_used=False,background_separation_tested=False,
        persistent_registry_changed=False,temporary_engine_selection=not args.use_saved_engines,
        saved_app_engines_used=args.use_saved_engines,human_quality_accepted=False,events=[],takes=[])
    pipe=ReflowPipeline()
    profile=ROOT/'models/indicf5/references/abhishek/profile.json'
    if args.use_saved_engines:
        for stage,preset in [('stt','whisper_turbo'),('translation','indictrans2'),('tts','indicf5')]:
            entry=pipe.registry.get_active(stage)
            if not entry or entry.get('request_preset')!=preset:
                raise ValueError('Saved '+stage+' selection is not the expected installed engine')
        profile=Path(pipe.registry.get_active('tts')['meta']['reference_profile'])
        report['registry_sha256_before']=digest(ROOT/'models.json')
    else:
        pipe.registry=FixtureRegistry()
        pipe.registry.get_active('stt').update(local_path=str(ROOT/'models/f5/reference-asr'),request_preset='whisper_turbo')
        pipe.registry.get_active('translation').update(local_path=str(ROOT/'models/translation/indictrans2-evaluation'),request_preset='indictrans2')
        pipe.registry.get_active('tts').update(local_path=str(ROOT/'models/indicf5/evaluation/assets'),request_preset='indicf5',
            meta={'reference_profile':str(profile),'speech_device':'cuda:0'})
    pipe.output_dir=str(folder)
    original_source=pipe._transcribe_source
    def record_source(*call_args,**kwargs):
        provider=call_args[0]
        try:
            value=original_source(*call_args,**kwargs)
            report['transcription']=value.to_payload()
            return value
        finally:
            report['recognition_result']=getattr(provider,'last_result',None)
            report['recognition_worker_released']=getattr(provider,'worker_released',False)
    pipe._transcribe_source=record_source
    original_resolve=pipe._resolve_translation_and_filter
    def record_translation(settings):
        provider,instructions,filter_provider,filter_instructions=original_resolve(settings)
        translate,release=provider.translate,provider.release
        def record(*call_args,**kwargs):
            value=translate(*call_args,**kwargs)
            report.setdefault('translations',[]).append(dict(source=call_args[0],text=value,result=provider.last_result))
            return value
        def close():
            session=provider.session
            release()
            report['translation_worker_released']=bool(session and session.finished.is_set())
        provider.translate,provider.release=record,close
        return provider,instructions,filter_provider,filter_instructions
    pipe._resolve_translation_and_filter=record_translation
    original_tts=resolve.resolve_tts
    def record_tts(*call_args,**kwargs):
        provider=original_tts(*call_args,**kwargs)
        synthesize=provider.synthesize
        def record(text,output_path,*speech_args,**speech_kwargs):
            result=synthesize(text,output_path,*speech_args,**speech_kwargs)
            saved=folder/f"live-take-{len(report['takes'])+1}.wav"
            shutil.copy2(output_path,saved)
            report['takes'].append(dict(text=text,file=str(saved),sha256=digest(saved),result=provider.last_result))
            return result
        provider.synthesize=record
        return provider
    # Instrumentation only: each call still resolves and executes the real provider.
    resolve.resolve_tts=record_tts
    job=RenderContext(ROOT/'temp')
    started=time.monotonic()
    try:
        with bind_job(job):
            excerpt=folder/'source-excerpt.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss',str(args.offset),'-i',str(source),
                '-t',str(args.seconds),'-c:v','libx264','-preset','veryfast','-crf','18','-c:a','aac',str(excerpt)],check=True,timeout=180)
            report['input_path']=str(excerpt)
            params=dict(target_lang='hi',source_language=args.source_language,cast_list=['CLONED_USER'],
                compute_device='cpu',
                keep_background=False,include_subtitles=True,burn_subtitles=False,parallel_workers=1)
            if not args.use_saved_engines:
                params['user_voice_path']=load_reference_profile(profile)['reference_audio']
            report['reference_supplied_by_driver']='user_voice_path' in params
            output=None
            for percent,message,result in pipe.run('video_dub',str(excerpt),params):
                report['events'].append(dict(progress=percent,message=message))
                print(percent,message,flush=True)
                if result: output=result
            if not output or not Path(output).is_file():
                raise RuntimeError('Automatic pipeline did not publish a complete video')
            run_process(['ffmpeg','-v','error','-nostdin','-i',output,'-f','null','-'],capture_output=True,check=True,timeout=180)
            media=json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',output],capture_output=True,check=True).stdout)
            assert {'video','audio','subtitle'} <= {row['codec_type'] for row in media['streams']}
            subtitle=next(row for row in media['streams'] if row['codec_type']=='subtitle')
            assert subtitle['tags']['language']=='hin'
            assert abs(float(media['format']['duration'])-pipe.get_duration(str(excerpt)))<.15
            assert digest(source)==report['source_sha256']
            if args.use_saved_engines:
                assert digest(ROOT/'models.json')==report['registry_sha256_before']
                report['registry_unchanged_during_render']=True
            report.update(completed=True,output=output,output_sha256=digest(output),full_decode_pass=True,
                subtitle_language='hin',duration_seconds=float(media['format']['duration']),source_unchanged=True,
                speech_worker_released=not getattr(job,'_indicf5_sessions',{}))
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        resolve.resolve_tts=original_tts
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),elapsed_seconds=round(time.monotonic()-started,3))
        receipt=folder.with_suffix('.json')
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(receipt,flush=True)

if __name__=='__main__': main()
