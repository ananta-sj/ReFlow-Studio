"""Actual offline review preparation and isolated cue generation; no human approval implied."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
from dev.verify_workflows import FixtureRegistry
from core import cue_review
from core.pipeline import ReflowPipeline
from core.settings import Settings
from core.render_context import RenderContext, bind_job


def main():
    report = dict(acceptance=False, offline=True, device='cpu', human_quality_accepted=False,
                  fixture='Complete Sample/2.mp4, keep_background=False explicitly for review',
                  final_output_generated=False)
    started = time.monotonic()
    output_root = ROOT / 'docs/validation/2026-10-04-cue-review-runtime'
    store = cue_review.ReviewStore(output_root)
    settings = Settings()
    progress = lambda percent, message: print(f'{percent}: {message}', flush=True)
    job = RenderContext(ROOT / 'temp')
    try:
        with bind_job(job):
            pipeline = ReflowPipeline()
            pipeline.registry = FixtureRegistry()
            pipeline.output_dir = str(output_root)
            path = cue_review.prepare(store, pipeline,
                str(ROOT / 'Sample/2.mp4'),
                dict(target_lang='hi', source_language='en', cast_list=['CLONED_USER'],
                     keep_background=False, compute_device='cpu'), settings, progress)
            identifier = Path(path).parent.name
            report['review_id'] = identifier
        job.cleanup()
        for index in range(min(2, len(store.load(identifier)['cues']))):
            job = RenderContext(ROOT / 'temp')
            with bind_job(job):
                pipeline = ReflowPipeline()
                pipeline.registry = FixtureRegistry()
                pipeline.output_dir = str(output_root)
                cue_review.operate(store, pipeline, identifier, store.load(identifier)['revision'],
                                   'generate', index, settings, progress)
                if not store.audio(identifier, index).startswith('data:audio/wav;base64,'):
                    raise RuntimeError('Generated preview is not playable audio')
            job.cleanup()
        manifest = store.load(identifier)
        report['review'] = store.public(identifier)
        report['manifest'] = str(store.folder(identifier) / 'review.json')
        report['generated_audio'] = [str(store.asset(manifest, cue['candidate']['file']))
                                     for cue in manifest['cues'] if cue['candidate']]
        report['acceptance'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (ROOT / 'docs/validation/2026-10-04-cue-review-runtime.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
