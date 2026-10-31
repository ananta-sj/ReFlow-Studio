"""Same accepted source takes and loudness/tempo stages, native decoder labeling."""
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
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.loudness import normalize_voice_loudness, measure_loudness
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    native = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    tempo = json.loads((ROOT / 'docs/validation/2026-10-04-hindi-tempo.json').read_text(encoding='utf-8'))
    raw_dir, old_dir = Path(native['review_directory']), Path(tempo['review_directory'])
    for source in (raw_dir, old_dir):
        if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-native-playback-' + uuid.uuid4().hex[:8])
    report = dict(new_inference=False, human_quality_accepted=False, tempo=1.342, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name in ('sujata', 'abhishek'):
                source = raw_dir / (name + '-raw.wav')
                raw = load_speech_audio(source)
                if raw.frame_rate != 22050:
                    raise ValueError('Expected known mislabeled raw waveform')
                corrected = raw._spawn(raw.raw_data, overrides={'frame_rate': 24000})
                prepared = work / (name + '-native-input.wav')
                corrected.export(prepared, format='wav').close()
                normalization = normalize_voice_loudness(prepared)
                clip = pipeline.speed_change(load_speech_audio(prepared), 1.342)
                output = work / (name + '-native.wav')
                clip.export(output, format='wav').close()
                shutil.copy2(old_dir / (name + '.wav'), work / (name + '-approved-earlier.wav'))
                report['cases'].append(dict(name=name, raw_sha256=digest(source),
                    native_seconds=len(clip)/1000, earlier_seconds=len(load_speech_audio(old_dir / (name+'.wav')))/1000,
                    decoder_pcm_unchanged=corrected.raw_data == raw.raw_data,
                    normalization=normalization, native_loudness=measure_loudness(output),
                    earlier_loudness=measure_loudness(old_dir / (name+'.wav'))))
            job.publish(work, destination)
            report['directory'] = str(destination)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-native-playback.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
