"""Inspect levels and audition existing speech without EQ/compression; no inference."""
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.loudness import measure_loudness, normalize_voice_loudness
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    import numpy as np
    prior_path = ROOT / 'docs/validation/2026-10-04-native-hindi.json'
    prior = json.loads(prior_path.read_text(encoding='utf-8'))
    source = Path(prior['review_directory'])
    if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside diagnostic storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-noise-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, human_quality_accepted=False,
                  production_defaults_changed=False, new_inference=False, tempo=prior['tempo'], cases=[])
    started = time.monotonic()

    def inspect(path):
        clip = load_speech_audio(path)
        samples = np.asarray(clip.get_array_of_samples(), dtype=np.int64)
        bound = int(clip.max_possible_amplitude)
        return dict(seconds=len(clip)/1000, sample_width=clip.sample_width,
                    sample_peak_dbfs=clip.max_dBFS,
                    full_scale_samples=int(np.sum((samples == -bound) | (samples == bound-1))),
                    near_full_scale_samples=int(np.sum(np.abs(samples) >= bound*.999)),
                    loudness=measure_loudness(path))

    try:
        with bind_job(job):
            work = job.workspace / 'noise'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for previous in prior['cases']:
                name = previous['name']
                raw = source / (name + '-raw.wav')
                if digest(raw) != previous['raw_sha256']:
                    raise ValueError('Saved raw speech changed')
                row = dict(name=name, original={stage: inspect(source / (name + suffix))
                    for stage, suffix in [('raw', '-raw.wav'), ('mastered', '-mastered.wav'), ('paced', '.wav')]})
                shutil.copy2(source / (name + '.wav'), work / (name + '-baseline.wav'))
                normalized = work / (name + '-loudness-only.wav')
                shutil.copy2(raw, normalized)
                row['normalization'] = normalize_voice_loudness(normalized)
                clip = pipeline.speed_change(load_speech_audio(normalized), report['tempo'])
                output = work / (name + '.wav')
                clip.export(output, format='wav').close()
                row['without_eq_compression'] = inspect(output)
                if abs(len(clip)/1000-previous['final_seconds']) > .02:
                    raise RuntimeError('Noise comparison changed speech timing')
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
        (ROOT / 'docs/validation/2026-10-04-hindi-noise.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
