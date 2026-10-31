"""Actual pipeline with real IndicF5 runtime; approved STT/translation fixtures."""
import json
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE'):
    os.environ[key] = '1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--background', action='store_true', help='Exercise real CPU separation and background mixing')
    parser.add_argument('--indictrans2-receipt', type=Path, help='Use evaluated IndicTrans2 text for a full-video review render')
    parser.add_argument('--source-receipt', type=Path, help='Completed full-video source receipt paired with IndicTrans2 output')
    args = parser.parse_args()
    from core.pipeline import ReflowPipeline
    from core.providers import resolve as providers
    from core.providers.tts.indicf5_local import digest
    from core.render_context import RenderContext, bind_job, run_process
    from core.transcription import TranscriptionResult
    from dev.verify_workflows import FixtureRegistry
    if bool(args.indictrans2_receipt) != bool(args.source_receipt):
        raise ValueError('Supply both IndicTrans2 and source receipts')
    if args.indictrans2_receipt:
        for path in (args.indictrans2_receipt, args.source_receipt):
            if not path.resolve().is_relative_to(ROOT / 'docs/validation'):
                raise ValueError('Review receipts must be workspace validation files')
        prior = json.loads(args.source_receipt.read_text(encoding='utf-8'))
        evaluated = json.loads(args.indictrans2_receipt.read_text(encoding='utf-8'))
        if not prior['completed'] or not prior['full_video'] or not evaluated['completed']:
            raise ValueError('Full-video recognition or translation is incomplete')
        if evaluated['source_sha256'] != prior['source_sha256'] or Path(evaluated['source_receipt']).resolve() != args.source_receipt.resolve():
            raise ValueError('Translation does not belong to this source receipt')
        if len(evaluated['cases']) != len(prior['source_cues']):
            raise ValueError('Translated cue count differs')
        for original, translated in zip(prior['source_cues'], evaluated['cases']):
            if original['text'] != translated['source'] or (original['start'],original['end']) != (translated['start'],translated['end']):
                raise ValueError('Translation source wording or timing differs')
        translations = {row['source']:row['translation'] for row in evaluated['cases']}
        seconds = prior['source_excerpt_seconds']
    else:
        draft_path = ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-draft.json'
        draft = json.loads(draft_path.read_text(encoding='utf-8'))
        acceptance = json.loads((ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-acceptance.json').read_text(encoding='utf-8'))
        if not acceptance['human_translation_accepted'] or digest(draft_path) != acceptance['draft_sha256']:
            raise ValueError('Approved video draft changed')
        prior = json.loads((ROOT / 'docs/validation' / draft['source_receipt']).read_text(encoding='utf-8'))
        translations = {s['text']: t['text'] for s, t in zip(prior['source_cues'], draft['cues'])}
        seconds = 52
    source = Path(prior['source'])
    if digest(source) != prior['source_sha256']:
        raise ValueError('Original source changed')
    from core.providers.tts.indicf5_local import require_supported_text, load_reference_profile, estimate_native_duration_seconds
    profile = load_reference_profile(ROOT / 'models/indicf5/references/abhishek/profile.json')
    for index, cue in enumerate(prior['source_cues']):
        text = translations[cue['text']]
        require_supported_text(text, ROOT / 'models/indicf5/evaluation/assets/checkpoints/vocab.txt',
                               profile['reference_text'])
        next_start = prior['source_cues'][index+1]['start'] if index+1 < len(prior['source_cues']) else cue['end']
        available = max(cue['end']-cue['start'], next_start-cue['start'])
        predicted = estimate_native_duration_seconds(text, profile)
        if predicted > available + .001:
            raise ValueError(f'Cue {index+1} cannot fit at native delivery: {predicted:.3f}s predicted, {available:.3f}s available')
    class ReviewedTranslation:
        def translate(self, text, *args, **kwargs):
            return translations[text]
    job = RenderContext(ROOT / 'temp')
    translation_origin = evaluated.get('translation_origin', 'raw_indictrans2') if args.indictrans2_receipt else 'accepted_editorial'
    edited_draft = bool(args.indictrans2_receipt) and translation_origin != 'raw_indictrans2'
    label = ('2026-10-08-spoken-hindi-full-video-' if edited_draft else
             '2026-10-08-indictrans2-full-video-' if args.indictrans2_receipt else '2026-10-06-indicf5-app-video-')
    destination = ROOT / 'docs/validation' / (label+uuid.uuid4().hex[:8])
    report = dict(completed=False, automatic_pipeline_pass=False, human_quality_accepted=False,
        production_pipeline_tested=True, live_indicf5_provider=True, live_stt_tested=False,
        automatic_translation_tested=False, approved_text_fixture_used=not bool(args.indictrans2_receipt),
        evaluated_indictrans2_text_used=bool(args.indictrans2_receipt) and not edited_draft,
        editorial_text_fixture_used=edited_draft, translation_origin=translation_origin,
        source_duration_seconds=seconds,
        source_cue_count=len(prior['source_cues']),
        source_receipt=str(args.source_receipt) if args.source_receipt else draft['source_receipt'],
        translation_receipt=str(args.indictrans2_receipt) if args.indictrans2_receipt else str(draft_path),
        background_preservation_tested=False, background_route_enabled=args.background,
        separation_quality_verified=False, registry_settings_changed=False,
        source_sha256=prior['source_sha256'], events=[], cues=[], directory=str(destination))
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            clip = work / 'source.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(source), '-t', str(seconds),
                '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264', '-preset', 'veryfast',
                '-crf', '18', '-threads', '2', '-c:a', 'aac', str(clip)], check=True, timeout=180)
            subject = ReflowPipeline()
            subject.registry = FixtureRegistry()
            tts = subject.registry.get_active('tts')
            tts.update(local_path=str(ROOT / 'models/indicf5/evaluation/assets'), request_preset='indicf5',
                       meta={'reference_profile':str(ROOT / 'models/indicf5/references/abhishek/profile.json'),
                             'speech_device':'cuda:0'})
            subject.output_dir = str(work / 'outputs')
            Path(subject.output_dir).mkdir()
            subject._transcribe_source = lambda *a, **kw: TranscriptionResult(
                [dict(row) for row in prior['source_cues']], language='en', language_probability=1.0)
            subject._resolve_translation_and_filter = lambda settings: (ReviewedTranslation(), '', None, '')
            original_resolver = providers.resolve_tts
            instances = []
            def resolve(*args, **kwargs):
                provider = original_resolver(*args, **kwargs)
                instances.append(provider)
                return provider
            original_cue = subject._dub_segment
            def record_cue(index, segment, *args, **kwargs):
                audio = original_cue(index, segment, *args, **kwargs)
                if audio is not None:
                    name = f'cue-{index+1:02d}.wav'
                    audio.export(work / name, format='wav').close()
                    report['cues'].append(dict(index=index, text=segment['text'], seconds=len(audio)/1000,
                                              file=name, result=instances[0].last_result))
                return audio
            subject._dub_segment = record_cue
            output = None
            with patch.object(providers, 'resolve_tts', side_effect=resolve):
                for progress, message, result in subject.run('video_dub', str(clip), dict(
                    target_lang='hi', source_language='en', cast_list=['CLONED_USER'],
                    user_voice_path=str(ROOT / 'models/indicf5/references/abhishek/reference.wav'),
                    compute_device='cpu', keep_background=args.background, include_subtitles=True,
                    burn_subtitles=False, export_stems=args.background, parallel_workers=1,
                    lip_sync_active=False, enhance_active=False, content_filter_active=False)):
                    report['events'].append(dict(progress=progress, message=message))
                    print(str(progress)+': '+message, flush=True)
                    if result:
                        output = Path(result)
            if output is None or not output.is_file() or len(report['cues']) != len(prior['source_cues']):
                raise ValueError('App pipeline did not produce all cues and final video')
            if getattr(job, '_indicf5_sessions', {}):
                raise ValueError('App pipeline did not release isolated GPU speech before completion')
            workers = {row['result']['worker_pid'] for row in report['cues']}
            if len(workers) != 1:
                raise ValueError('App pipeline did not reuse one speech worker')
            result = run_process(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)],
                                 capture_output=True, text=True, check=True, timeout=60)
            info = json.loads(result.stdout)
            if not {'video','audio','subtitle'}.issubset({s['codec_type'] for s in info['streams']}):
                raise ValueError('App video lacks required streams')
            if abs(float(info['format']['duration'])-seconds) > .15:
                raise ValueError('App video timeline changed')
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-map', '0:v:0',
                         '-map', '0:a:0', '-f', 'null', os.devnull], check=True, timeout=180)
            for name in ('master_audio.wav', 'temp_subs.srt'):
                existing = Path(subject.temp_dir) / name
                if existing.exists():
                    shutil.copy2(existing, work / name)
            if digest(source) != prior['source_sha256']:
                raise ValueError('Original source changed')
            if args.background:
                from core.audio_utils import load_playable_audio
                stems = {}
                for role in ('background', 'vocals', 'dubbed'):
                    stem = output.with_name(output.stem + '_stem_' + role + '.wav')
                    audio = load_playable_audio(stem)
                    if abs(len(audio)-seconds*1000) > 150:
                        raise ValueError('Exported '+role+' stem has a different timeline')
                    stems[role] = dict(file=str(stem.relative_to(work)), milliseconds=len(audio), rms=audio.rms,
                                       sha256=digest(stem))
                report.update(background_preservation_tested=True, stems=stems,
                    note='Real separation/mixing/stem publication completed. This source was not selected as a music/ambience reference; leakage and preservation still need listening review.')
            report.update(completed=True, automatic_pipeline_pass=True, model_worker_reused=True,
                gpu_worker_released=True, source_unchanged=True, full_decode_pass=True,
                output=str(output.relative_to(work)), output_sha256=digest(output), streams=info['streams'])
            (work / 'app-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            job.publish(work, destination)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'completed':report['completed'],'receipt':str(destination.with_suffix('.json')),'error':report.get('error')}), flush=True)


if __name__ == '__main__':
    main()
