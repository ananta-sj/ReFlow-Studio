"""Create sample-exact A/B/C listening montages from completed GPU trials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import numpy as np
    import soundfile as sf
    from core.render_context import RenderContext, bind_job, run_process
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--baseline', type=Path, help='Long selected-settings receipt for A/B/C/D prosody comparison')
    args = parser.parse_args()
    prior_path = args.receipt.resolve()
    if ROOT / 'docs/validation' not in prior_path.parents:
        raise ValueError('Use a workspace validation receipt')
    prior = json.loads(prior_path.read_text(encoding='utf-8'))
    if not prior['completed'] or prior['device'] != 'cuda:0':
        raise ValueError('GPU voice trial batch incomplete')
    cases = {row['name']: row for row in prior['cases']}
    ordering = {'sujata': ['sujata', 'sujata-guidance', 'sujata-seed'],
                'abhishek': ['abhishek', 'abhishek-pace', 'abhishek-pace-seed']}
    source_directory = Path(prior['directory']).resolve()
    if ROOT / 'docs/validation' not in source_directory.parents:
        raise ValueError('Trial media directory outside validation root')
    labels = 'ABC'
    baseline = None
    if args.baseline:
        baseline_path = args.baseline.resolve()
        if ROOT / 'docs/validation' not in baseline_path.parents:
            raise ValueError('Baseline outside validation root')
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        if not baseline['completed'] or baseline['device'] != 'cuda:0':
            raise ValueError('Baseline incomplete')
        baseline_directory = Path(baseline['directory']).resolve()
        if ROOT / 'docs/validation' not in baseline_directory.parents:
            raise ValueError('Baseline media outside validation root')
        for row in baseline['cases']:
            cases[row['name']] = row
        labels = 'ABCD'
        ordering = {voice: [voice + suffix for suffix in ('-selected', '-steps64', '-guidance15', '-guidance25')]
                    for voice in ('sujata', 'abhishek')}
    tag = '2026-10-06-indicf5-gpu-comparison-' + uuid.uuid4().hex[:8]
    destination = ROOT / 'docs/validation' / tag
    job = RenderContext(ROOT / 'temp')
    report = dict(completed=False, human_quality_accepted=False, source_receipt=str(prior_path),
                  source_receipt_sha256=digest(prior_path), pause_seconds=0.65, voices=[])
    if baseline:
        report.update(baseline_receipt=str(baseline_path), baseline_receipt_sha256=digest(baseline_path))
    try:
        with bind_job(job):
            work = job.workspace / 'comparisons'
            work.mkdir()
            for voice, names in ordering.items():
                chunks, segments = [], []
                cursor = 0
                for index, name in enumerate(names):
                    row = cases[name]
                    origin = baseline_directory if baseline and name.endswith('-selected') else source_directory
                    path = origin / name / 'listening.wav'
                    if baseline and (row['text'] != baseline['cases'][0]['text'] or
                                     row['reference_sha256'] != cases[voice + '-selected']['reference_sha256']):
                        raise ValueError('Comparison must use identical text and reference per voice')
                    if digest(path) != row['listening_sha256']:
                        raise ValueError('Trial listening recording changed')
                    samples, rate = sf.read(path, dtype='int16')
                    if rate != 24000 or samples.ndim != 1:
                        raise ValueError('Expected mono native-rate PCM listening copy')
                    if index:
                        silence = np.zeros(round(.65*rate), dtype='int16')
                        chunks.append(silence)
                        cursor += len(silence)
                    segments.append(dict(label=labels[index], case=name, start_seconds=cursor/rate,
                        seconds=len(samples)/rate, original_sha256=row['listening_sha256'],
                        native_generation_speed=row['native_generation_speed'], cfg_strength=row['cfg_strength'],
                        seed=row['diagnostic_seed_before_synthesis'], nfe_step=row.get('nfe_step', 32)))
                    chunks.append(samples)
                    cursor += len(samples)
                montage = np.concatenate(chunks)
                output = work / (voice + '-' + labels + '.wav')
                sf.write(output, montage, 24000, subtype='PCM_16')
                restored, rate = sf.read(output, dtype='int16')
                if rate != 24000 or not np.array_equal(restored, montage):
                    raise ValueError('Montage changed source samples')
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                report['voices'].append(dict(voice=voice, file=output.name, seconds=len(montage)/rate,
                    sha256=digest(output), sample_exact_concatenation=True, full_decode_pass=True,
                    additional_gain_applied=False, segments=segments))
            job.publish(work, destination)
            report.update(completed=True, directory=str(destination))
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        receipt = ROOT / 'docs/validation' / (tag + '.json')
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'receipt': str(receipt), **report}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
