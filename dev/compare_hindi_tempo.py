"""Audition bundled Rubber Band versus retained atempo; no engine inference."""
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
    from core.loudness import measure_loudness
    from core.render_context import RenderContext, bind_job, run_process
    previous = json.loads((ROOT / 'docs/validation/2026-10-04-hindi-noise.json').read_text(encoding='utf-8'))
    source = Path(previous['review_directory'])
    if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-tempo-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, human_quality_accepted=False, production_defaults_changed=False,
                  new_inference=False, tempo=previous['tempo'], pitch=1.0,
                  filter=f'rubberband=tempo={previous["tempo"]}:pitch=1', cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'tempo'
            work.mkdir()
            for name in ('sujata', 'abhishek'):
                input_path = source / (name + '-loudness-only.wav')
                original = load_speech_audio(input_path)
                shutil.copy2(input_path, work / (name + '-input.wav'))
                shutil.copy2(source / (name + '.wav'), work / (name + '-atempo.wav'))
                output = work / (name + '.wav')
                before = time.monotonic()
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(input_path),
                    '-af', report['filter'], '-ar', str(original.frame_rate), '-ac', str(original.channels),
                    '-c:a', 'pcm_s16le', str(output)], check=True, timeout=120)
                clip = load_speech_audio(output)
                if abs(len(clip)-len(original)/report['tempo']) > 100:
                    raise RuntimeError('Alternate tempo failed duration validation')
                levels = measure_loudness(output)
                # Preserve samples/timing unless overshoot needs gain-only correction.
                correction = max(0, levels['input_tp']+1.5+.05) if levels['input_tp'] > -1.2 else 0
                if correction:
                    clip.apply_gain(-correction).export(output, format='wav').close()
                    levels = measure_loudness(output)
                row = dict(name=name, input_sha256=digest(input_path), input_seconds=len(original)/1000,
                           atempo_seconds=len(load_speech_audio(source / (name + '.wav')))/1000,
                           rubberband_seconds=len(load_speech_audio(output))/1000,
                           loudness=levels, gain_correction_db=correction,
                           elapsed_seconds=round(time.monotonic()-before, 3))
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
        (ROOT / 'docs/validation/2026-10-04-hindi-tempo.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
