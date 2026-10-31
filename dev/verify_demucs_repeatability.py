"""Two actual installed CPU separations; identical PCM is required for reuse."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(REFLOW_OFFLINE='1', OMP_NUM_THREADS='2', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from core.audio_separator import AudioSeparator, DEMUCS_SHA256
    from core.render_context import RenderContext, bind_job, run_process
    weights = ROOT / 'models/uvr/955717e8-8726e21a.th'
    if not weights.is_file() or sha(weights) != DEMUCS_SHA256:
        raise RuntimeError('Installed weights missing/changed; no download allowed')
    job = RenderContext(ROOT / 'temp')
    report = dict(passed=False, device='cpu', seed=0, shifts=1, runs=[], live_separation=True)
    started = time.monotonic()
    try:
        with bind_job(job):
            source = job.workspace / 'source.wav'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', '115.6',
                '-i', str(ROOT / 'Sample/2.mp4'), '-t', '6.9', '-vn', '-ac', '2', '-ar', '44100', str(source)], check=True, timeout=60)
            for index in (1, 2):
                before = time.monotonic()
                paths = AudioSeparator('cpu').separate(str(source))
                report['runs'].append(dict(index=index, hashes=[sha(path) for path in paths],
                    bytes=[Path(path).stat().st_size for path in paths], elapsed_seconds=round(time.monotonic()-before,3)))
            report['passed'] = report['runs'][0]['hashes'] == report['runs'][1]['hashes']
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started,3),
            worker_sha256=sha(ROOT / 'core/run_demucs.py'))
        receipt = ROOT / 'docs/validation' / ('2026-10-12-demucs-repeatability-' + uuid.uuid4().hex[:8] + '.json')
        receipt.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(receipt, report, flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
