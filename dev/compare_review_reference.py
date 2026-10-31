"""Same-text/seed XTTS reference comparison; diagnostics only, no default changes."""
import hashlib
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
    from core.cue_review import ReviewStore, digest
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler

    store = ReviewStore(ROOT / 'docs/validation/2026-10-04-cue-review-runtime')
    manifest = store.load('738849605df04434ae1ea4c4e99e1527')
    cue = manifest['cues'][1]
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-reference-comparison-' + uuid.uuid4().hex[:8])
    receipt = ROOT / 'docs/validation/2026-10-04-reference-comparison.json'
    report = dict(execution_completed=False, human_quality_accepted=False,
                  reference_human_verified=False, production_defaults_changed=False,
                  device='cpu', offline=True, seed=1234, temperature=.75,
                  split_sentences=True, tempo=1.342, text=cue['text'],
                  window_seconds=cue['available_seconds'], cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'comparison'
            work.mkdir()
            for filename in ('reference.wav', 'vocals.wav'):
                source = store.asset(manifest, filename)
                if digest(source) != manifest['assets'][filename]:
                    raise RuntimeError('Retained source hash changed')
            shutil.copy2(store.asset(manifest, 'reference.wav'), work / 'full-reference.wav')
            source = load_speech_audio(store.asset(manifest, 'vocals.wav'))
            first = manifest['cues'][0]
            source[round(first['start']*1000):round(first['end']*1000)].export(
                work / 'short-source.wav', format='wav').close()
            AudioEngineer().clean_reference_audio(str(work / 'short-source.wav'), str(work / 'short-reference.wav'))
            report['references'] = {name: dict(seconds=len(load_speech_audio(work / name))/1000,
                                              sha256=digest(work / name))
                                    for name in ('full-reference.wav', 'short-reference.wav')}
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            print('Model loaded: ' + str(report['model_load_seconds']), flush=True)
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name, reference in [('full', 'full-reference.wav'), ('short', 'short-reference.wav'),
                                    ('short-repeat', 'short-reference.wav')]:
                job.check()
                random.seed(report['seed'])
                np.random.seed(report['seed'])
                torch.manual_seed(report['seed'])
                raw = work / (name + '-raw.wav')
                mastered = work / (name + '-mastered.wav')
                listening = work / (name + '.wav')
                before = time.monotonic()
                engine.generate_audio(report['text'], str(raw), language='hi', reference_audio=str(work / reference))
                synthesis = time.monotonic()-before
                shutil.copy2(raw, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                adjusted = pipeline.speed_change(load_speech_audio(mastered), report['tempo'])
                adjusted.export(listening, format='wav').close()
                final = load_speech_audio(listening)
                row = dict(name=name, reference=reference, raw_seconds=len(load_speech_audio(raw))/1000,
                           final_seconds=len(final)/1000, fits=len(final)<=round(cue['available_seconds']*1000),
                           raw_sha256=digest(raw), pcm_sha256=hashlib.sha256(final.raw_data).hexdigest(),
                           synthesis_seconds=round(synthesis, 3), total_seconds=round(time.monotonic()-before, 3))
                report['cases'].append(row)
                print(json.dumps(row), flush=True)
            report['short_repeat_pcm_identical'] = report['cases'][1]['pcm_sha256'] == report['cases'][2]['pcm_sha256']
            job.publish(work, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
