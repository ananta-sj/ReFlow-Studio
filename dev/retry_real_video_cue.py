"""Bounded offline cue retry; preserves overflowing takes without accepting them."""
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
os.environ['OMP_NUM_THREADS'] = '2'
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'


def main():
    from core.pipeline import ReflowPipeline
    from core.providers import resolve as providers
    from core.audio_utils import AudioEngineer
    from core.render_context import RenderContext, bind_job
    from dev.verify_workflows import FixtureRegistry
    baseline = json.loads((ROOT / 'docs/validation/2026-10-04-real-video-dub.json').read_text(encoding='utf-8'))
    source = Path(baseline['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Baseline outside validation storage')
    cue = baseline['translated_cues'][1]
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-cue-retry-' + uuid.uuid4().hex[:8])
    report = dict(baseline=str(source), source_words_confirmed=False, human_quality_accepted=False,
                  final_video_produced=False, production_defaults_changed=False,
                  text=cue['text'], available_seconds=2.6, offline=True, trials=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline()
            pipeline.registry = FixtureRegistry()
            tts = providers.resolve_tts(pipeline.registry, 'cpu')
            original = tts.synthesize
            trial = 0
            def capture(*args, **kwargs):
                result = original(*args, **kwargs)
                shutil.copy2(args[1], work / f'trial-{trial}-raw.wav')
                return result
            tts.synthesize = capture
            for trial in (1, 2):
                before = time.monotonic()
                clip = pipeline._dub_segment(1, cue, ['CLONED_USER'], 'hi', tts, {},
                    str(source / 'clean_reference.wav'), str(source / 'clean_reference.wav'),
                    'cpu', AudioEngineer(), next_start=9.24, allow_overflow=True)
                filename = f'trial-{trial}.wav'
                clip.export(work / filename, format='wav').close()
                fits = len(clip) <= 2600
                report['trials'].append(dict(trial=trial, file=filename, seconds=len(clip)/1000,
                    fits_without_truncation=fits, elapsed_seconds=round(time.monotonic()-before, 3)))
                print(json.dumps(report['trials'][-1]), flush=True)
                if fits:
                    break
            job.publish(work, destination)
            report['directory'] = str(destination)
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),
                      elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-cue-retry.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
