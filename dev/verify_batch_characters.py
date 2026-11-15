"""Render a short episode scene through the actual batch pipeline, without overrides."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH', '')
os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-scene', type=Path)
    parser.add_argument('--conversation-only', action='store_true')
    args = parser.parse_args()
    from core.render_context import RenderContext, bind_job, run_process
    from core.pipeline import ReflowPipeline
    from core.cuda_runtime import readiness
    if readiness()['status'] != 'ready':
        raise RuntimeError('Verified GPU route unavailable')
    source = Path(r'C:\Users\19shr\Downloads\New folder\[DarkWispers] Perrine HD 01 [C0163C61].mkv')
    destination = ROOT/'outputs'/('batch-character-scene-'+str(int(time.time())))
    destination.mkdir(parents=True, exist_ok=False)
    job = RenderContext(ROOT/'temp')
    report = dict(human_quality_accepted=False, automatic_character_matching_verified=False,
                  original_source=str(source), source_start=80, scene_seconds=300, events=[])
    report['dialogue_scope'] = [138, 180] if args.conversation_only else [0, 300]
    started = time.monotonic()
    try:
        with bind_job(job):
            scene = args.source_scene or destination/'source-scene.mkv'
            if not args.source_scene:
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', '80', '-i', str(source),
                    '-t', '300', '-map', '0:v:0', '-map', '0:a:0', '-map', '0:s:1', '-c:s', 'srt', '-vf', 'scale=640:-2',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'pcm_s16le',
                    str(scene)], check=True, timeout=180)
            class ConversationPreview(ReflowPipeline):
                def _prepare_batch_characters(self, audio_path, transcript, *values, **options):
                    super()._prepare_batch_characters(audio_path, transcript, *values, **options)
                    if args.conversation_only:
                        # Test scope only: detect the complete context first,
                        # then synthesize the requested conversation. No voice
                        # labels, references, text or matches are overridden.
                        transcript[:] = [cue for cue in transcript if cue['start'] >= 138 and cue['end'] <= 180]
                        if not transcript:
                            raise RuntimeError('No conversation cues selected')
            pipeline = ConversationPreview()
            for percent, message, output in pipeline.run('video_dub', str(scene), dict(
                    target_lang='hi', source_language='ja', cast_list=['CLONED_USER'],
                    compute_device='cuda:0', keep_background=True, include_subtitles=True,
                    export_stems=True, task_priority=0, parallel_workers=1)):
                print(percent, message, flush=True)
                report['events'].append(dict(percent=percent, message=message))
                if output:
                    report['output'] = output
            manifest = json.loads(Path(pipeline.last_manifest_path).read_text(encoding='utf-8'))
            report['manifest'] = pipeline.last_manifest_path
            from core.batch_review import publish
            publish(pipeline.last_manifest_path, report['output'])
            matching = [r for r in manifest['quality_reports'] if r['kind'] == 'batch-character-matching']
            if not matching:
                raise RuntimeError('Normal app path bypassed source character matching')
            evidence = json.loads(Path(matching[-1]['path']).read_text(encoding='utf-8'))
            report['speaker_count'] = len(evidence['speakers'])
            report['matched_cues'] = sum(c['status'] == 'matched' for c in evidence['cues'])
            report['review_cues'] = sum(c['status'] != 'matched' for c in evidence['cues'])
            report['review_required'] = manifest['review_required']
            scene_speakers = {c.get('speaker') for c in evidence['cues'] if c['start'] < 180 and c['end'] > 138 and c['status']=='matched'}
            report['mother_daughter_speakers'] = len(scene_speakers)
            report['automatic_character_matching_verified'] = len(evidence['speakers']) >= 3 and len(scene_speakers) == 2
            preview = destination/'mother-daughter-dub-preview.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', '138', '-i', report['output'],
                '-t', '42', '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', str(preview)],
                check=True, timeout=120)
            report['preview'] = str(preview)
            if not report['automatic_character_matching_verified']:
                raise RuntimeError('Scene did not establish two consistent character references; inspect report')
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 2)
        (destination/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        job.cleanup()


if __name__ == '__main__':
    main()
