"""Separate mastering coloration from sampling variation; no production changes."""
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
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.loudness import normalize_voice_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler
    previous = json.loads((ROOT / 'docs/validation/2026-10-04-speech-diagnosis.json').read_text(encoding='utf-8'))
    source_dir = Path(previous['review_directory'])
    if not source_dir.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Diagnostic source must be inside validation storage')
    original = previous['cases'][0]
    raw_source = source_dir / 'hindi-1234-raw.wav'
    reference = source_dir / 'reference.wav'
    if digest(raw_source) != original['raw_sha256'] or digest(reference) != previous['reference_sha256']:
        raise ValueError('Saved diagnostic source changed')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-delivery-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, human_quality_accepted=False, production_defaults_changed=False,
                  seed=1234, text=original['text'], tempo=1.342, offline=True, device='cpu',
                  baseline_raw_sha256=original['raw_sha256'], reference_sha256=previous['reference_sha256'], cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'delivery'
            work.mkdir()
            shutil.copy2(reference, work / 'reference.wav')
            shutil.copy2(raw_source, work / 'baseline-raw.wav')
            shutil.copy2(source_dir / 'hindi-1234.wav', work / 'baseline.wav')
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            plain = work / 'no-eq-compression-mastered.wav'
            shutil.copy2(raw_source, plain)
            normalization = normalize_voice_loudness(plain)
            clip = pipeline.speed_change(load_speech_audio(plain), report['tempo'])
            clip.export(work / 'no-eq-compression.wav', format='wav').close()
            report['cases'].append(dict(name='no-eq-compression', temperature=.75,
                new_synthesis=False, eq=False, compression=False, normalization=normalization,
                final_seconds=len(clip)/1000))
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            random.seed(report['seed'])
            np.random.seed(report['seed'])
            torch.manual_seed(report['seed'])
            raw = work / 'temperature-090-raw.wav'
            before = time.monotonic()
            engine.tts.tts_to_file(text=report['text'], file_path=str(raw), speaker_wav=str(work / 'reference.wav'),
                language='hi', split_sentences=True, temperature=.90, speed=1.0, **generation_kwargs())
            synthesis = time.monotonic()-before
            load_speech_audio(raw)
            mastered = work / 'temperature-090-mastered.wav'
            shutil.copy2(raw, mastered)
            AudioEngineer().master_voice_segment(str(mastered))
            clip = pipeline.speed_change(load_speech_audio(mastered), report['tempo'])
            clip.export(work / 'temperature-090.wav', format='wav').close()
            row = dict(name='temperature-090', temperature=.90, new_synthesis=True,
                       eq=True, compression=True, raw_seconds=len(load_speech_audio(raw))/1000,
                       final_seconds=len(load_speech_audio(work / 'temperature-090.wav'))/1000,
                       synthesis_seconds=round(synthesis, 3), raw_sha256=digest(raw))
            report['cases'].append(row)
            print(json.dumps(row), flush=True)
            job.publish(work, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        (ROOT / 'docs/validation/2026-10-04-hindi-delivery.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
