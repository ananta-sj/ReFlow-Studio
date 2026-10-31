"""Explicit real-engine acceptance on a short, local sample; weights stay local."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['HF_HOME'] = str(ROOT / 'models' / 'whisper' / 'cache')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg' / 'bin') + os.pathsep + os.environ.get('PATH', '')

from core.render_context import RenderContext, bind_job, run_process
from core.providers.stt.whisper_local import WhisperLocalProvider
from core.transcription import require_media_bounds
import wave


def main():
    sample_number = sys.argv[1] if len(sys.argv) > 1 else '1'
    if sample_number not in ('1', '2', '3'):
        raise ValueError('Choose an existing sample: 1, 2 or 3')
    sample = ROOT / 'Sample' / f'{sample_number}.mp4'
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': 'faster-whisper', 'model': 'tiny', 'device': 'cpu',
              'sample': str(sample), 'sample_sha256': hashlib.sha256(sample.read_bytes()).hexdigest(),
              'acceptance': False}
    try:
        with bind_job(job):
            audio = job.workspace / 'reference.wav'
            run_process([str(ROOT / 'ffmpeg/bin/ffmpeg.exe'), '-v', 'error', '-y', '-i', str(sample),
                         '-t', '8', '-vn', '-ac', '1', '-ar', '16000', str(audio)], check=True, timeout=60)
            result = WhisperLocalProvider(model_size='tiny').transcribe(str(audio))
            report.update({'segments': list(result), 'language': result.language,
                           'language_probability': result.language_probability})
            with wave.open(str(audio), 'rb') as stream:
                duration = stream.getnframes() / stream.getframerate()
            require_media_bounds(result, duration)
            if not result or not any(segment['text'].strip() for segment in result):
                raise RuntimeError('Sample produced no speech segments')
            report['acceptance'] = True
            report['transcription_accuracy_verified'] = False
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / f'docs/validation/2026-10-04-whisper-sample-{sample_number}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
