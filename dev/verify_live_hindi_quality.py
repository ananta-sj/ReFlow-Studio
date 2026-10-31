"""Fresh production XTTS adapter and segment execution against an approved take."""
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
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.pipeline import ReflowPipeline
    from core.providers import resolve as providers
    from core.render_context import RenderContext, bind_job
    from dev.verify_workflows import FixtureRegistry
    raw_receipt = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').read_text(encoding='utf-8'))
    processed = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-processed.json').read_text(encoding='utf-8'))
    case = next(row for row in processed['cases'] if row['voice'] == 'sujata' and row['label'] == 'question')
    raw_case = next(row for row in raw_receipt['cases'] if row['voice'] == 'sujata' and row['label'] == 'question')
    raw_dir, final_dir = Path(raw_receipt['directory']).resolve(), Path(processed['directory']).resolve()
    for path in (raw_dir, final_dir):
        if not path.is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Source outside validation storage')
    reference = raw_dir / 'sujata-reference.wav'
    if digest(reference) != raw_case['reference_sha256']:
        raise ValueError('Approved reference changed')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-live-hindi-' + uuid.uuid4().hex[:8])
    report = dict(acceptance=False, new_inference=True, full_video_test=False, reference_preparation_repeated=False)
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            pipeline.registry = FixtureRegistry()
            tts = providers.resolve_tts(pipeline.registry, 'cpu')
            original = tts.synthesize
            def capture(*args, **kwargs):
                result = original(*args, **kwargs)
                shutil.copy2(args[1], work / 'fresh-raw.wav')
                return result
            tts.synthesize = capture
            cue = dict(start=0, end=case['seconds']+.2, text=case['text'])
            actual = pipeline._dub_segment(0, cue, ['CLONED_USER'], 'hi', tts, {},
                str(reference), str(reference), 'cpu', AudioEngineer())
            expected = load_speech_audio(final_dir / case['file'])
            raw_match = digest(work / 'fresh-raw.wav') == raw_case['raw_sha256']
            pcm_match = (actual.raw_data == expected.raw_data and actual.frame_rate == expected.frame_rate
                         and actual.channels == expected.channels and actual.sample_width == expected.sample_width)
            report.update(raw_sha_matches_approved=raw_match, processed_pcm_matches_approved=pcm_match,
                          seconds=len(actual)/1000)
            actual.export(work / 'fresh-final.wav', format='wav').close()
            job.publish(work, destination)
            report.update(acceptance=raw_match and pcm_match, directory=str(destination))
            if not report['acceptance']:
                raise RuntimeError('Fresh production speech differs from approved deterministic control')
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-live-hindi.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
