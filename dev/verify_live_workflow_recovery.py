"""Installed offline engines: cancel real speech, restart with verified checkpoints.

No replacement transcript, translation or waveform. Optional stages not enabled
here (lip sync, enhancement, filtering) are outside this acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(PYTHONIOENCODING='utf-8', REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1',
                 TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='2')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offset', type=float, default=115.6)
    parser.add_argument('--seconds', type=float, default=6.9)
    args = parser.parse_args()
    if not (0 <= args.offset and 1 <= args.seconds <= 30 and args.offset + args.seconds <= 122.53):
        parser.error('Use a 1–30 second excerpt inside Sample/2.mp4')
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, RenderCancelled, bind_job, run_process
    from core.audio_separator import DEMUCS_SHA256
    checkpoint = ROOT / 'models/uvr/955717e8-8726e21a.th'
    if not checkpoint.is_file() or sha(checkpoint) != DEMUCS_SHA256:
        raise RuntimeError('Installed Demucs checkpoint is missing/changed; no download permitted')
    source = ROOT / 'Sample/2.mp4'
    state_names = ('models.json', 'settings.json', 'graph.json', 'hardware_profile.json', 'ui_preferences.json')
    baseline = {name: sha(ROOT / name) for name in state_names}
    folder = ROOT / 'docs/validation' / ('2026-10-12-live-workflow-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    receipt = folder.with_suffix('.json')
    report = dict(passed=False, source=str(source), source_sha256=sha(source),
                  offset_seconds=args.offset, excerpt_seconds=args.seconds, output_folder=str(folder),
                  offline=True, installed_engines_only=True, substitutions=False,
                  background_preservation_enabled=True, native_crash_test=False,
                  bridge_queue_recovery_test=False, human_quality_accepted=False, passes=[])

    def save():
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    save()
    prep = RenderContext(ROOT / 'temp')
    try:
        with bind_job(prep):
            clip = folder / 'source-excerpt.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(args.offset), '-i', str(source),
                         '-t', str(args.seconds), '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264',
                         '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac', str(clip)], check=True, timeout=120)
    finally:
        prep.cleanup()
    params = dict(target_lang='hi', source_language='en', cast_list=['CLONED_USER'],
                  compute_device='cpu', keep_background=True, parallel_workers=1,
                  include_subtitles=True, export_stems=True)
    report['params'] = params
    for phase in ('cancel', 'restart'):
        job = RenderContext(ROOT / 'temp')
        started = time.monotonic()
        item = dict(phase=phase, events=[], speech_generating_observed=False)
        report['passes'].append(item)
        done = threading.Event()

        def monitor():
            while not done.wait(.05):
                if phase == 'cancel':
                    for log in job.workspace.glob('f5-session-*/worker.log'):
                        try:
                            value = log.read_text(encoding='utf-8', errors='replace')
                        except OSError:
                            continue
                        if '"stage": "generating"' in value and '"engine": "indicf5"' in value:
                            item['speech_generating_observed'] = True
                            item['cancel_requested_at'] = time.monotonic()
                            with job.lock:
                                item['owned_pids_at_cancel'] = [process.pid for process in job.processes]
                            job.request_stop()
                            return
                if time.monotonic() - started > 900:
                    item['watchdog_timeout'] = True
                    job.request_stop()
                    return

        watcher = threading.Thread(target=monitor, daemon=True)
        watcher.start()
        pipe = None
        try:
            with bind_job(job):
                pipe = ReflowPipeline()
                pipe.output_dir = str(folder)
                for stage, preset in [('stt', 'whisper_turbo'), ('translation', 'indictrans2'), ('tts', 'indicf5')]:
                    if (pipe.registry.get_active(stage) or {}).get('request_preset') != preset:
                        raise RuntimeError('Saved installed engine changed: ' + stage)
                for percent, status, output in pipe.run('video_dub', str(clip), params):
                    item['events'].append(dict(percent=percent, status=status))
                    print(phase, percent, status, flush=True)
                    if output:
                        item['output'] = output
        except Exception as error:
            item.update(error=str(error), error_type=type(error).__name__, cancelled=isinstance(error, RenderCancelled))
            print(phase, type(error).__name__, str(error), flush=True)
        finally:
            done.set()
            watcher.join(2)
            try:
                job.cleanup()
            except Exception as error:
                item['cleanup_error'] = str(error)
            item.update(elapsed_seconds=round(time.monotonic() - started, 3),
                        workspace_removed=not job.workspace.exists(),
                        owned_processes_released=not job.processes,
                        retained_speech_sessions=len(getattr(job, '_indicf5_sessions', {})),
                        speech_sessions_released=all(session.finished.is_set() and not session.thread.is_alive()
                            for session in getattr(job, '_indicf5_sessions', {}).values()))
            if 'cancel_requested_at' in item:
                item['cancel_through_cleanup_seconds'] = round(time.monotonic() - item.pop('cancel_requested_at'), 3)
            item['manifest_path'] = getattr(pipe, 'last_manifest_path', None)
            if item['manifest_path']:
                manifest = read(item['manifest_path'])
                item.update(manifest_status=manifest['status'], checkpoints=manifest['checkpoints'],
                            completed_stages=sorted({op['stage'] for op in manifest['operations'] if op['status'] == 'completed'}))
            save()
        if phase == 'cancel' and not (item.get('cancelled') and item['speech_generating_observed']):
            report['blocked_before_real_speech_cancellation'] = True
            break
        if phase == 'restart' and item.get('output'):
            validation = RenderContext(ROOT / 'temp')
            with bind_job(validation):
                try:
                    output = item['output']
                    run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', output, '-f', 'null', '-'],
                                capture_output=True, check=True, timeout=120)
                    media = json.loads(run_process(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                        '-of', 'json', output], capture_output=True, check=True, timeout=60).stdout)
                    item.update(full_decode_pass=True, output_sha256=sha(output), duration_seconds=float(media['format']['duration']),
                        stream_types=[row['codec_type'] for row in media['streams']],
                        stems=[dict(path=str(path), sha256=sha(path))
                            for path in Path(output).parent.glob(Path(output).stem + '_stem_*.wav')])
                finally:
                    validation.cleanup()
    report.update(persistent_state_unchanged=baseline == {name: sha(ROOT / name) for name in state_names},
                  source_unchanged=sha(source) == report['source_sha256'])
    if len(report['passes']) == 2:
        first, second = report['passes']
        report['passed'] = (first.get('cancelled') and first['speech_generating_observed']
            and first.get('manifest_status') == 'cancelled' and second.get('manifest_status') == 'completed'
            and second.get('full_decode_pass') and abs(second['duration_seconds'] - args.seconds) < .2
            and {'video', 'audio', 'subtitle'} <= set(second['stream_types']) and len(second['stems']) == 4
            and {'stt', 'translation'} <= {event['stage'] for event in second['checkpoints'] if event['status'] == 'hit'}
            and all(p['workspace_removed'] and p['owned_processes_released'] and p['speech_sessions_released'] for p in report['passes'])
            and report['persistent_state_unchanged'] and report['source_unchanged'])
    save()
    print('REPORT', receipt, 'passed=', report['passed'], flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
