"""Controlled offline XTTS listening candidates; never certify naturalness."""
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    import numpy as np
    import torch
    from core.audio_utils import load_speech_audio
    from core.generation_control import generation_kwargs
    from core.loudness import normalize_voice_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler

    reference = ROOT / 'docs/validation/2026-10-04-voice-quality-b6905bf2/reference.wav'
    load_speech_audio(reference)
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-naturalness-' + uuid.uuid4().hex[:8])
    started = time.monotonic()
    report = dict(engine='xtts', offline=True, device='cpu', seed=1234,
                  text='सुप्रभात। यह एक छोटा परीक्षण है।', language='hi',
                  reference=str(reference), revision=RECOVERY_SOURCES['xtts']['revision'],
                  execution_completed=False, human_naturalness_accepted=False, cases=[])
    try:
        with bind_job(job):
            folder = job.workspace / 'review'
            folder.mkdir()
            shutil.copy2(reference, folder / 'reference.wav')
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            for name, temperature, split in [('baseline', .75, True),
                                              ('lower-temperature', .45, True),
                                              ('unsplit', .75, False)]:
                job.check()
                random.seed(report['seed'])
                np.random.seed(report['seed'])
                torch.manual_seed(report['seed'])
                before = time.monotonic()
                raw, listening = folder / (name + '-raw.wav'), folder / (name + '.wav')
                engine.tts.tts_to_file(text=report['text'], file_path=str(raw),
                    speaker_wav=str(reference), language='hi', split_sentences=split,
                    temperature=temperature, speed=1.0, **generation_kwargs())
                raw_clip = load_speech_audio(raw)
                shutil.copy2(raw, listening)
                normalization = normalize_voice_loudness(listening)
                clip = load_speech_audio(listening)
                if abs(len(clip) - len(raw_clip)) > 20:
                    raise RuntimeError('Listening normalization changed the speech timeline')
                row = dict(name=name, temperature=temperature, split_sentences=split,
                           synthesis_speed=1.0, tempo_adjustment=False, eq=False,
                           compression=False, duration_ms=len(clip), normalization=normalization,
                           elapsed_seconds=round(time.monotonic() - before, 3))
                report['cases'].append(row)
                print(json.dumps(row), flush=True)
            job.publish(folder, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),
                      elapsed_seconds=round(time.monotonic() - started, 3))
        (ROOT / 'docs/validation/2026-10-04-naturalness-comparison.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
