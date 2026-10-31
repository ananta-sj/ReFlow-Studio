"""Two real requests reuse one isolated F5 model and close at job cleanup."""
import json
import os
from pathlib import Path
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
from core.model_contract import local_contract
from core.feature_session import run_cached_f5
from core.render_context import RenderContext, bind_job
from core.audio_utils import load_playable_audio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--automatic-reference', action='store_true')
    args = parser.parse_args()
    job = RenderContext(ROOT / 'temp')
    report = {'acceptance': False, 'engine': 'f5-session', 'device': 'cpu',
              'reference_transcription_tested': args.automatic_reference, 'requests': [],
              'synthesis_quality_verified': False}
    started = time.monotonic()
    try:
        contract = local_contract('voice', str(ROOT / 'models/f5/acceptance_v1'), 'f5tts')
        reference = ROOT / 'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/examples/basic/basic_ref_en.wav'
        with bind_job(job):
            for index in range(2):
                request_started = time.monotonic()
                output = job.workspace / f'request-{index}.wav'
                result = run_cached_f5(contract, {'reference_audio': str(reference),
                    'reference_text': '' if args.automatic_reference else 'Some call me nature, others call me mother nature.',
                    'text': 'Good morning.', 'output_path': str(output)})
                clip = load_playable_audio(str(output))
                report['requests'].append({**result, 'duration_ms': len(clip), 'bytes': output.stat().st_size,
                    'elapsed_seconds': round(time.monotonic() - request_started, 3)})
        if report['requests'][0]['worker_pid'] != report['requests'][1]['worker_pid']:
            raise RuntimeError('F5 requests did not reuse the same process')
        sessions = list(job._f5_sessions.values())
        if args.automatic_reference:
            for session in sessions:
                session.close()
            diagnostics = '\n'.join(session.log.read_text(encoding='utf-8', errors='replace') for session in sessions)
            report['reference_transcription_calls'] = diagnostics.count('No reference text provided, transcribing reference audio...')
            if report['reference_transcription_calls'] != 1:
                raise RuntimeError('Repeated reference was not transcribed exactly once')
            (ROOT / 'docs/validation/2026-10-04-f5-automatic-session-worker.log').write_text(diagnostics, encoding='utf-8')
        job.cleanup()
        if job.processes or any(session.thread.is_alive() for session in sessions):
            raise RuntimeError('F5 speech session remained alive after cleanup')
        report.update(acceptance=True, worker_stopped=True, workspace_removed=not job.workspace.exists())
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        receipt = '2026-10-04-f5-automatic-session.json' if args.automatic_reference else '2026-10-04-f5-session.json'
        (ROOT / 'docs/validation' / receipt).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
