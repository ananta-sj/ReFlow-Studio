"""Real offline engines through the normal run entry; no substituted text/audio."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(PYTHONIOENCODING='utf-8', REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=['known', 'full-known', 'independent'])
    args = parser.parse_args()
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job, run_process
    source = ROOT / ('Sample/3.mp4' if args.case == 'independent' else 'Sample/2.mp4')
    offset, seconds = {'known': (115.6, 4), 'full-known': (0, 122.5), 'independent': (0, 8)}[args.case]
    folder = ROOT / 'docs/validation' / ('2026-10-09-pipeline-foundation-' + args.case + '-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    persistent = {name: digest(ROOT/name) for name in ('models.json', 'settings.json')}
    report = dict(case=args.case, completed=False, source=str(source), source_sha256=digest(source),
        offset_seconds=offset, excerpt_seconds=seconds, no_transcript_or_translation_fixtures=True,
        reused_takes=False, saved_engine_selections=True, background_separation_tested=False,
        automatic_quality_supervisor=False, human_quality_accepted=False, events=[])
    job = RenderContext(ROOT/'temp')
    started = time.monotonic()
    error = None
    try:
        with bind_job(job):
            excerpt = folder/'source-excerpt.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(offset), '-i', str(source),
                '-t', str(seconds), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac', str(excerpt)],
                check=True, timeout=180)
            pipe = ReflowPipeline()
            pipe.output_dir = str(folder)
            for stage, preset in [('stt', 'whisper_turbo'), ('translation', 'indictrans2'), ('tts', 'indicf5')]:
                if (pipe.registry.get_active(stage) or {}).get('request_preset') != preset:
                    raise ValueError('Saved engine selection changed: ' + stage)
            try:
                for percent, status, output in pipe.run('video_dub', str(excerpt),
                    dict(target_lang='hi', source_language='auto', cast_list=['CLONED_USER'],
                         compute_device='cpu', keep_background=False, parallel_workers=1)):
                    report['events'].append(dict(percent=percent, status=status))
                    print(percent, status, flush=True)
                    if output:
                        report['output'] = output
            finally:
                report['manifest_path'] = getattr(pipe, 'last_manifest_path', None)
            output = report.get('output')
            if not output:
                raise RuntimeError('No published output')
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', output, '-f', 'null', '-'],
                        capture_output=True, check=True, timeout=180)
            media = json.loads(run_process(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', output],
                                         capture_output=True, check=True, timeout=60).stdout)
            if not {'audio', 'video', 'subtitle'} <= {stream['codec_type'] for stream in media['streams']}:
                raise RuntimeError('Output is missing required streams')
            manifest = json.loads(Path(report['manifest_path']).read_text(encoding='utf-8'))
            if manifest['status'] != 'completed' or manifest['output']['sha256'] != digest(output):
                raise RuntimeError('Run completion/output evidence disagrees')
            cues = []
            for artifact in manifest['cue_artifacts']:
                if artifact['sha256'] != digest(artifact['path']):
                    raise RuntimeError('Cue artifact identity disagrees')
                if artifact['phase'] == 'speech-input':
                    cues = json.loads(Path(artifact['path']).read_text(encoding='utf-8'))['segments']
            if not cues or any(not cue.get('cue_id') or not cue.get('source_text')
                               or not cue.get('translated_text') for cue in cues):
                raise RuntimeError('Missing cue/source/translation provenance')
            stages = {operation['stage'] for operation in manifest['operations'] if operation['status'] == 'completed'}
            if not {'source', 'stt', 'translation', 'speech', 'timing', 'media'} <= stages:
                raise RuntimeError('Missing real stage observations')
            report.update(completed=True, full_decode_pass=True, source_text_preserved=True,
                translated_text_preserved=True, cue_artifact_hashes_verified=True,
                output_sha256=digest(output), duration_seconds=float(media['format']['duration']),
                observed_stages=sorted(stages), cue_count=len(cues))
    except Exception as exc:
        error = exc
        report.update(error_type=type(exc).__name__, error=str(exc))
        print(type(exc).__name__, str(exc), flush=True)
    finally:
        try:
            job.cleanup()
        finally:
            report.update(workspace_removed=not job.workspace.exists(),
                workers_released=not getattr(job, '_indicf5_sessions', {}),
                elapsed_seconds=round(time.monotonic()-started, 3),
                source_unchanged=digest(source)==report['source_sha256'],
                persistent_state_unchanged=all(digest(ROOT/name)==value for name, value in persistent.items()))
            path = report.get('manifest_path')
            if path:
                saved = json.loads(Path(path).read_text(encoding='utf-8'))
                report['manifest_status'] = saved['status']
                report['failed_operations'] = [dict(stage=item['stage'], error=item.get('error'))
                    for item in saved['operations'] if item['status'] == 'failed']
            receipt = folder.with_suffix('.json')
            receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(receipt, flush=True)
    if error is not None:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
