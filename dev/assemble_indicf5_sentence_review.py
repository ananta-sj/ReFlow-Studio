"""Assemble hash-verified sentence recordings with exact PCM and silent gaps."""
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
    args = parser.parse_args()
    receipt = args.receipt.resolve()
    if ROOT / 'docs/validation' not in receipt.parents:
        raise ValueError('Receipt outside validation root')
    source = json.loads(receipt.read_text(encoding='utf-8'))
    directory = Path(source['directory']).resolve()
    if ROOT / 'docs/validation' not in directory.parents or not source['completed']:
        raise ValueError('Incomplete or out-of-workspace source')
    rows = source['cases']
    if ([row['name'] for row in rows] != ['abhishek-sentence-'+str(i) for i in range(1, 7)] or
            ' '.join(row['text'] for row in rows) != source['text']):
        raise ValueError('Sentence order or exact target wording mismatch')
    destination = ROOT / 'docs/validation' / ('2026-10-06-indicf5-segmented-listening-'+uuid.uuid4().hex[:8])
    report = dict(completed=False, human_quality_accepted=False, production_changed=False,
                  source_receipt=str(receipt), source_receipt_sha256=digest(receipt),
                  directory=str(destination), inserted_pause_seconds=0.2, segments=[])
    job = RenderContext(ROOT / 'temp')
    try:
        with bind_job(job):
            work = job.workspace / 'assembly'
            work.mkdir()
            parts, cursor = [], 0
            for i, row in enumerate(rows):
                path = directory / row['name'] / 'listening.wav'
                if digest(path) != row['listening_sha256']:
                    raise ValueError('Source recording changed')
                audio, rate = sf.read(path, dtype='int16')
                if rate != 24000 or audio.ndim != 1 or len(audio) != row['expected_target_frames']:
                    raise ValueError('Invalid source format or frame count')
                if i:
                    parts.append(np.zeros(4800, dtype='int16'))
                    cursor += 4800
                report['segments'].append(dict(case=row['name'], text=row['text'],
                    start_seconds=cursor/rate, seconds=len(audio)/rate, source_sha256=row['listening_sha256']))
                parts.append(audio)
                cursor += len(audio)
            joined = np.concatenate(parts)
            output = work / 'abhishek-segmented.wav'
            sf.write(output, joined, 24000, subtype='PCM_16')
            restored, rate = sf.read(output, dtype='int16')
            if rate != 24000 or not np.array_equal(restored, joined):
                raise ValueError('Assembly altered source samples')
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-f', 'null', os.devnull],
                        check=True, timeout=60)
            job.publish(work, destination)
            report.update(completed=True, seconds=len(joined)/24000, frames=len(joined),
                          sha256=digest(destination/output.name), full_decode_pass=True,
                          sample_exact_concatenation=True, additional_gain_applied=False,
                          crossfade_applied=False, tempo_changed=False)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
