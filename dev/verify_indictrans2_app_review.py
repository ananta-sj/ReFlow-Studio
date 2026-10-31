"""Fresh video through real app ASR, selected MT, review and live Hindi TTS."""
import hashlib
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(PYTHONIOENCODING='utf-8', REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH','')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='Sample/1.mp4')
    parser.add_argument('--seconds', type=float, help='Limit the test input without substituting transcript or translation')
    parser.add_argument('--strong-recognition',action='store_true')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--label-date',default='2026-10-08')
    args = parser.parse_args()
    date.fromisoformat(args.label_date)
    from core import cue_review
    from core.pipeline import ReflowPipeline
    from core.providers import resolve
    from core.render_context import RenderContext, bind_job, run_process
    from dev.verify_workflows import FixtureRegistry
    from settings import Settings
    source = (ROOT / args.source).resolve()
    if not source.is_relative_to(ROOT / 'Sample'):
        raise ValueError('Use an existing Sample video')
    label = args.label_date+('-strong-whisper-app-review-' if args.strong_recognition else '-indictrans2-app-review-')+uuid.uuid4().hex[:8]
    folder = ROOT / 'docs/validation' / label
    folder.mkdir()
    receipt = folder.with_suffix('.json')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    report = dict(completed=False, live_asr=False, live_translation=False, live_tts=False,
        translation_or_transcription_fixtures_used=False, persistent_registry_changed=False,
        background_separation_tested=False, human_quality_accepted=False,
        source=str(source), source_sha256=source_hash, directory=str(folder), cues=[])
    settings = Settings()
    pipe = ReflowPipeline()
    pipe.registry = FixtureRegistry()  # isolated selection only; all providers are real.
    if args.strong_recognition:
        pipe.registry.get_active('stt').update(local_path=str(ROOT/'models/f5/reference-asr'),request_preset='whisper_turbo')
    pipe.registry.get_active('translation').update(local_path=str(ROOT / 'models/translation/indictrans2-evaluation'),request_preset='indictrans2')
    profile = ROOT / 'models/indicf5/references/abhishek/profile.json'
    pipe.registry.get_active('tts').update(local_path=str(ROOT / 'models/indicf5/evaluation/assets'),request_preset='indicf5',
        meta={'reference_profile':str(profile),'speech_device':'cuda:0'})
    transcribe_source = pipe._transcribe_source
    def record_source(*args, **kwargs):
        provider = args[0]
        try:
            result = transcribe_source(*args, **kwargs)
            report.update(live_asr=True, transcription=result.to_payload())
            return result
        finally:
            if getattr(provider,'engine_id',None) == 'whisper_turbo':
                report.update(live_asr=provider.last_result is not None,
                    recognition_result=provider.last_result,
                    recognition_worker_released_before_translation=provider.worker_released)
    pipe._transcribe_source = record_source
    resolve_translation = pipe._resolve_translation_and_filter
    def record_translation(settings):
        provider, instructions, filter_provider, filter_instructions = resolve_translation(settings)
        translate = provider.translate
        release = provider.release
        def record(*args, **kwargs):
            value = translate(*args, **kwargs)
            report['live_translation'] = True
            report.setdefault('translations', []).append(dict(source=args[0], text=value, result=provider.last_result))
            return value
        def close():
            session = provider.session
            release()
            report['translation_worker_released_before_tts'] = bool(session and session.finished.is_set())
        provider.translate = record
        provider.release = close
        return provider, instructions, filter_provider, filter_instructions
    pipe._resolve_translation_and_filter = record_translation
    pipe.output_dir = str(folder)
    store = cue_review.ReviewStore(folder)
    params = dict(cast_list=['CLONED_USER'], target_lang='hi', source_language='auto',
                  compute_device='cpu',keep_background=False,review_video=True,
                  user_voice_path=str(ROOT / 'models/indicf5/references/abhishek/reference-24k.wav'))
    # Resolve the hash-bound actual prepared reference filename.
    from core.providers.tts.indicf5_local import load_reference_profile
    params['user_voice_path'] = load_reference_profile(profile)['reference_audio']
    events = []
    def progress(percent, message):
        events.append(dict(progress=percent,message=message))
        print(f'{percent}: {message}',flush=True)
    jobs = []
    start = time.monotonic()
    try:
        job = RenderContext(ROOT/'temp')
        jobs.append(job)
        with bind_job(job):
            input_path = source
            if args.seconds:
                if not 1 <= args.seconds <= 120:
                    raise ValueError('Excerpt must be 1–120 seconds')
                input_path = folder / 'source-excerpt.mp4'
                run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-t',str(args.seconds),
                    '-c:v','copy','-c:a','aac',str(input_path)],check=True,timeout=120)
                report.update(excerpt_seconds=args.seconds,input_path=str(input_path))
            prepared = cue_review.prepare(store, pipe, str(input_path), params, settings, progress)
        job.cleanup()
        identifier = Path(prepared).parent.name
        manifest = store.load(identifier)
        report.update(review_id=identifier, source_language=manifest['source_language'],
                      cue_count=len(manifest['cues']))
        for index in range(0 if args.prepare_only else len(manifest['cues'])):
            job = RenderContext(ROOT/'temp')
            jobs.append(job)
            with bind_job(job):
                current = store.load(identifier)
                cue_review.operate(store,pipe,identifier,current['revision'],'generate',index,settings,progress)
            job.cleanup()
            current = store.load(identifier)
            cue = current['cues'][index]
            report['live_tts'] = True
            report['cues'].append({**cue,'audio':str(store.asset(current,cue['candidate']['file']))})
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        report['completed'] = True
        report['source_unchanged'] = True
        report['all_candidates_fit'] = bool(report['cues']) and all(cue['candidate']['fits'] for cue in report['cues'])
        report['preparation_only'] = args.prepare_only
        report['review_manifest'] = str(store.folder(identifier)/'review.json')
        report['note'] = 'Real app review preparation/generation; no human text/take acceptance or final video render is implied.'
    except Exception as exc:
        report.update(error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        for job in jobs:
            job.cleanup()
        report.update(workspaces_removed=all(not job.workspace.exists() for job in jobs),
                      elapsed_seconds=round(time.monotonic()-start,3),events=events)
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(str(receipt),flush=True)


if __name__ == '__main__':
    main()
