"""Explicit one-second CPU acceptance of an installed visual engine."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['TORCH_HOME'] = str(ROOT / 'models/torch-cache')
from core.render_context import RenderContext, bind_job, run_process
import cv2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['wav2lip', 'gfpgan', 'musetalk'])
    args = parser.parse_args()
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': args.engine, 'device': 'cpu', 'acceptance': False,
              'visual_quality_verified': False}
    try:
        with bind_job(job):
            video, audio, output = [job.workspace / name for name in ('reference.mp4', 'reference.wav', 'output.mp4')]
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '1', '-vf', 'fps=5,scale=640:-2', '-an', '-c:v', 'libx264', str(video)],
                        check=True, timeout=60)
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '1', '-vn', '-ac', '1', '-ar', '16000', str(audio)], check=True, timeout=60)
            if args.engine == 'wav2lip':
                from core.providers.lipsync.wav2lip_local import Wav2LipLocalProvider
                Wav2LipLocalProvider(device='cpu').execute(str(video), str(audio), str(output))
            elif args.engine == 'gfpgan':
                from core.providers.enhancer.gfpgan_local import GFPGANLocalProvider
                GFPGANLocalProvider(device='cpu').enhance(str(video), str(output))
            else:
                from core.providers.lipsync.musetalk_local import MuseTalkLocalProvider
                MuseTalkLocalProvider(device='cpu').execute(str(video), str(audio), str(output))
            from pipeline import _validate_media
            _validate_media(str(output), {'video'})
            reader = cv2.VideoCapture(str(output))
            try:
                count, fps = int(reader.get(cv2.CAP_PROP_FRAME_COUNT)), reader.get(cv2.CAP_PROP_FPS)
                decoded = 0
                while reader.read()[0]:
                    decoded += 1
                if count != 5 or decoded != 5 or abs(count / fps - 1) > .05:
                    raise RuntimeError(f'Visual stage changed or truncated the source: {count}/{decoded} frames at {fps} fps')
                report.update({'frames': count, 'decoded_frames': decoded, 'fps': fps,
                               'bytes': output.stat().st_size, 'acceptance': True})
            finally:
                reader.release()
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / f'docs/validation/2026-10-04-{args.engine}-engine.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report))


if __name__ == '__main__':
    main()
