"""Processing-stage listening gate on four exact human-approved greedy takes."""
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
    from pydub import AudioSegment
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.loudness import measure_loudness, normalize_voice_loudness
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job, run_process
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').read_text(encoding='utf-8'))
    if not prior.get('human_quality_accepted'):
        raise ValueError('Raw coverage has not passed human review')
    source = Path(prior['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-greedy-processed-' + uuid.uuid4().hex[:8])
    report = dict(new_inference=False, production_changed=False, human_quality_accepted=False,
                  mechanical_checks_pass=False, tempo=1.342, eq=False, compression=False, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for voice in ('sujata', 'abhishek'):
                montage = None
                for case in [item for item in prior['cases'] if item['voice'] == voice]:
                    stem = voice + '-' + case['label']
                    raw_path = source / (stem + '-raw.wav')
                    if digest(raw_path) != case['raw_sha256']:
                        raise ValueError('Accepted synthesis changed')
                    raw = load_speech_audio(raw_path)
                    prepared = work / (stem + '-normalized.wav')
                    shutil.copy2(raw_path, prepared)
                    normalization = normalize_voice_loudness(prepared)
                    output = work / (stem + '.wav')
                    pipeline.speed_change(load_speech_audio(prepared), 1.342).export(output, format='wav').close()
                    final = load_speech_audio(output)
                    if abs(len(final)-len(raw)/1.342) > 100:
                        raise RuntimeError('Tempo timing check failed')
                    level = measure_loudness(output)
                    if level['input_tp'] > -1.2:
                        raise RuntimeError('Processed true peak exceeds tolerance')
                    for path in (prepared, output):
                        run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                                    check=True, timeout=60)
                    report['cases'].append(dict(voice=voice, label=case['label'], text=case['text'],
                        accepted_raw_sha256=digest(raw_path), file=output.name, sha256=digest(output),
                        raw_seconds=len(raw)/1000, seconds=len(final)/1000,
                        normalization=normalization, loudness=level))
                    gap = AudioSegment.silent(duration=900, frame_rate=24000).set_channels(1).set_sample_width(2)
                    montage = final if montage is None else montage + gap + final
                review = work / (voice + '-review.wav')
                montage.export(review, format='wav').close()
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(review), '-f', 'null', os.devnull],
                            check=True, timeout=60)
            report['mechanical_checks_pass'] = True
            job.publish(work, destination)
            report['directory'] = str(destination)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-greedy-processed.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
