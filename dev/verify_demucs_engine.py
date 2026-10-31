"""Explicit short CPU separation acceptance using a preserved local sample."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
from core.render_context import RenderContext, bind_job, run_process
from core.audio_separator import AudioSeparator
from core.audio_utils import load_playable_audio


def main():
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': 'demucs', 'model': 'htdemucs', 'device': 'cpu', 'acceptance': False}
    try:
        with bind_job(job):
            audio = job.workspace / 'reference.wav'
            run_process([str(ROOT / 'ffmpeg/bin/ffmpeg.exe'), '-v', 'error', '-y',
                         '-i', str(ROOT / 'Sample/2.mp4'), '-t', '3', '-vn', '-ac', '2',
                         '-ar', '44100', str(audio)], check=True, timeout=60)
            vocals, background = AudioSeparator('cpu').separate(str(audio))
            report['stems'] = [{'name': Path(path).name, 'duration_ms': len(load_playable_audio(path)),
                                'bytes': Path(path).stat().st_size} for path in (vocals, background)]
            if any(abs(stem['duration_ms'] - 3000) > 50 for stem in report['stems']):
                raise RuntimeError('Separated stem duration differs from source')
            report['acceptance'] = True
            report['separation_quality_verified'] = False
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / 'docs/validation/2026-10-04-demucs-engine.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report))


if __name__ == '__main__':
    main()
