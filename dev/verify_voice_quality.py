"""Retain real raw/mastered XTTS clips for listening; never certify naturalness."""
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def describe(path):
    from core.audio_utils import load_playable_audio
    clip = load_playable_audio(str(path))
    samples = clip.get_array_of_samples()
    full_scale = int(clip.max_possible_amplitude)
    return {'duration_ms': len(clip), 'bytes': path.stat().st_size,
            'peak_dbfs': clip.max_dBFS if clip.max else None,
            'rms_dbfs': clip.dBFS if clip.rms else None,
            'full_scale_samples': sum(abs(sample) >= full_scale - 1 for sample in samples)}


def main():
    from core.audio_utils import AudioEngineer
    from core.model_assets import RECOVERY_SOURCES, ensure_assets
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': 'xtts', 'offline': True, 'device': 'cpu',
              'revision': RECOVERY_SOURCES['xtts']['revision'], 'execution_completed': False,
              'human_quality_accepted': False, 'cases': []}
    destination = ROOT / 'docs/validation' / ('2026-10-04-voice-quality-' + uuid.uuid4().hex[:8])
    try:
        with bind_job(job):
            ensure_assets('xtts')
            folder = job.workspace / 'review'
            folder.mkdir()
            reference = folder / 'reference.wav'
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '6', '-vn', '-ac', '1', '-ar', '24000', str(reference)], check=True, timeout=60)
            report['reference_source'] = 'Sample/2.mp4, seconds 2 through 8'
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            for language, text in [('en', 'Good morning. This is a short test.'),
                                   ('hi', 'सुप्रभात। यह एक छोटा परीक्षण है।')]:
                before = time.monotonic()
                raw, mastered = folder / f'{language}-raw.wav', folder / f'{language}-mastered.wav'
                engine.generate_audio(text, str(raw), language=language, reference_audio=str(reference))
                shutil.copy2(raw, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                report['cases'].append({'language': language, 'text': text,
                    'raw': describe(raw), 'mastered': describe(mastered),
                    'elapsed_seconds': round(time.monotonic() - before, 3)})
            # Publish the complete owned review directory once; never overwrite.
            job.publish(folder, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / 'docs/validation/2026-10-04-voice-quality.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
