"""Actual segment path must reproduce four accepted Hindi processing controls."""
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from dev.verify_workflows import FixtureRegistry
    raw_receipt = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').read_text(encoding='utf-8'))
    final_receipt = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-processed.json').read_text(encoding='utf-8'))
    if not raw_receipt.get('human_quality_accepted') or not final_receipt.get('human_quality_accepted'):
        raise ValueError('Processing controls require human approval')
    raw_dir, final_dir = Path(raw_receipt['directory']).resolve(), Path(final_receipt['directory']).resolve()
    for path in (raw_dir, final_dir):
        if not path.is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-production-hindi-' + uuid.uuid4().hex[:8])
    report = dict(acceptance=False, new_inference=False, full_video_test=False, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            pipeline.registry = FixtureRegistry()
            for case in final_receipt['cases']:
                raw_case = next(row for row in raw_receipt['cases']
                               if row['voice'] == case['voice'] and row['label'] == case['label'])
                raw = raw_dir / (case['voice'] + '-' + case['label'] + '-raw.wav')
                expected_path = final_dir / case['file']
                if digest(raw) != raw_case['raw_sha256'] or digest(expected_path) != case['sha256']:
                    raise ValueError('Accepted source changed')
                class RetainedSpeech:
                    def synthesize(self, text, output_path, language, reference_audio):
                        if text != case['text'] or language != 'hi':
                            raise ValueError('Unexpected production request')
                        shutil.copy2(raw, output_path)
                        return output_path
                reference = str(raw_dir / (case['voice'] + '-reference.wav'))
                cue = dict(start=0, end=case['seconds']+.2, text=case['text'])
                actual = pipeline._dub_segment(0, cue, ['CLONED_USER'], 'hi', RetainedSpeech(), {},
                    reference, reference, 'cpu', AudioEngineer())
                expected = load_speech_audio(expected_path)
                matched = (actual.raw_data == expected.raw_data and actual.frame_rate == expected.frame_rate
                           and actual.channels == expected.channels and actual.sample_width == expected.sample_width)
                report['cases'].append(dict(voice=case['voice'], label=case['label'], seconds=len(actual)/1000,
                                            pcm_identical=matched))
                if not matched:
                    raise RuntimeError('Production processing differs from approved control')
                actual.export(work / case['file'], format='wav').close()
            job.publish(work, destination)
            report.update(acceptance=True, directory=str(destination))
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-production-hindi.json').write_text(
            json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
