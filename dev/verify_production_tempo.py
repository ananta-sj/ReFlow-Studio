"""Verify production tempo returns exact PCM from the user-approved controls."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import load_speech_audio
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-hindi-tempo.json').read_text(encoding='utf-8'))
    source = Path(prior['review_directory'])
    if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Diagnostic source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-production-tempo-' + uuid.uuid4().hex[:8])
    report = dict(acceptance=False, new_inference=False, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'tempo'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name in ('sujata', 'abhishek'):
                input_audio = load_speech_audio(source / (name + '-input.wav'))
                expected = load_speech_audio(source / (name + '.wav'))
                actual = pipeline.speed_change(input_audio, prior['tempo'])
                matched = (actual.raw_data == expected.raw_data and actual.frame_rate == expected.frame_rate
                           and actual.channels == expected.channels and actual.sample_width == expected.sample_width)
                report['cases'].append(dict(name=name, seconds=len(actual)/1000, pcm_identical=matched))
                if not matched:
                    raise RuntimeError('Production tempo differs from the approved control: ' + name)
                actual.export(work / (name + '.wav'), format='wav').close()
            job.publish(work, destination)
            report.update(acceptance=True, directory=str(destination))
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-production-tempo.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
