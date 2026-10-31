"""Retain user rejection and prepare matched-level raw negation controls."""
import json
import math
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.loudness import measure_loudness
    from core.render_context import RenderContext, bind_job, run_process
    receipt_path = ROOT / 'docs/validation/2026-10-04-hindi-coverage.json'
    prior = json.loads(receipt_path.read_text(encoding='utf-8'))
    prior.update(human_quality_accepted=False, batch_listening_rejected=True,
        user_feedback='both voices have some distortion and stutters',
        rejection_scope='Both presented three-sentence review montages; individual raw stages not yet auditioned')
    receipt_path.write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding='utf-8')
    source = Path(prior['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-raw-controls-' + uuid.uuid4().hex[:8])
    report = dict(new_inference=False, production_changed=False, raw_quality_verified=False,
                  tempo_processing=False, normalization=False, eq=False, compression=False, cases=[])
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            for name in ('sujata', 'abhishek'):
                case = next(row for row in prior['cases'] if row['voice'] == name and row['label'] == 'negation')
                raw = source / case['raw_file']
                if digest(raw) != case['raw_sha256']:
                    raise ValueError('Retained raw waveform changed')
                audio = load_speech_audio(raw)
                if audio.frame_rate != 24000 or audio.channels != 1:
                    raise ValueError('Expected native mono decoder waveform')
                level = measure_loudness(raw)
                if not all(math.isfinite(level[key]) for key in ('input_i', 'input_tp')):
                    raise RuntimeError('Cannot measure raw control')
                gain = min(-18.0-level['input_i'], -1.55-level['input_tp'])
                output = work / (name + '-raw.wav')
                audio.apply_gain(gain).export(output, format='wav').close()
                result = load_speech_audio(output)
                measured = measure_loudness(output)
                if len(result) != len(audio) or result.frame_rate != audio.frame_rate or measured['input_tp'] > -1.2:
                    raise RuntimeError('Control timeline/format/peak check failed')
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                report['cases'].append(dict(voice=name, text=case['text'], source_sha256=digest(raw),
                    file=output.name, seconds=len(result)/1000, comparison_gain_db=gain,
                    loudness=measured, sha256=digest(output)))
            job.publish(work, destination)
            report['directory'] = str(destination)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        (ROOT / 'docs/validation/2026-10-04-hindi-raw-controls.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
