"""Long-passage listening gate for the preferred short-cue sampling candidate."""
import json
import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--sentence-boundaries', action='store_true')
    args = parser.parse_args()
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-long-hindi-voice.json').read_text(encoding='utf-8'))
    text = prior['cases'][0]['text']
    reference = Path(prior['reference'])
    baseline = Path(prior['review_directory']) / 'quality-preferred-pace.wav'
    if args.sentence_boundaries:
        previous = json.loads((ROOT / 'docs/validation/2026-10-04-long-hindi-delivery.json').read_text(encoding='utf-8'))
        baseline = Path(previous['review_directory']) / 'candidate.wav'
    engine_text = text.replace('।', '.') if args.sentence_boundaries else text
    label = 'hindi-boundaries' if args.sentence_boundaries else 'long-hindi-delivery'
    for source in (reference, baseline):
        if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Diagnostic source outside validation storage')
        load_speech_audio(source)
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-' + label + '-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, human_quality_accepted=False, production_defaults_changed=False,
                  offline=True, device='cpu', text=text, seed=1234, temperature=.90,
                  tempo=1.342, reference_sha256=digest(reference), baseline_sha256=digest(baseline))
    report.update(engine_text=engine_text, sentence_boundary_normalization=args.sentence_boundaries)
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'long-delivery'
            work.mkdir()
            shutil.copy2(reference, work / 'reference.wav')
            shutil.copy2(baseline, work / 'baseline.wav')
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            report['engine_sentences'] = engine.tts.synthesizer.split_into_sentences(engine_text)
            if args.sentence_boundaries and len(report['engine_sentences']) != 2:
                raise RuntimeError('Boundary control must produce two sentences')
            print('Engine sentences: ' + json.dumps(report['engine_sentences'], ensure_ascii=False), flush=True)
            random.seed(report['seed'])
            np.random.seed(report['seed'])
            torch.manual_seed(report['seed'])
            raw = work / 'candidate-raw.wav'
            before = time.monotonic()
            engine.tts.tts_to_file(text=engine_text, file_path=str(raw), speaker_wav=str(work / 'reference.wav'),
                language='hi', split_sentences=True, temperature=.90, speed=1.0, **generation_kwargs())
            report['synthesis_seconds'] = round(time.monotonic()-before, 3)
            mastered = work / 'candidate-mastered.wav'
            shutil.copy2(raw, mastered)
            AudioEngineer().master_voice_segment(str(mastered))
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            clip = pipeline.speed_change(load_speech_audio(mastered), report['tempo'])
            clip.export(work / 'candidate.wav', format='wav').close()
            report.update(raw_seconds=len(load_speech_audio(raw))/1000,
                          final_seconds=len(load_speech_audio(work / 'candidate.wav'))/1000,
                          baseline_seconds=len(load_speech_audio(baseline))/1000, raw_sha256=digest(raw))
            job.publish(work, destination)
            report.update(execution_completed=True, review_directory=str(destination))
            print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        (ROOT / ('docs/validation/2026-10-04-' + label + '.json')).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
