"""Retain short reference excerpts with explicitly unverified text proposals."""
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
    prior_path = ROOT / 'docs/validation/2026-10-06-indicf5-user-references-984652c4.json'
    prior = json.loads(prior_path.read_text(encoding='utf-8'))
    if not prior['completed'] or not prior['original_files_unchanged']:
        raise ValueError('Reference preparation incomplete')
    proposals = {
        'sujata': (6.6, 'बच्चों, क्या आपको मालूम है कि पेड़ के पत्ते हरे लेकिन फूल रंगीन क्यों होते हैं?'),
        'abhishek': (5.73, 'इसके बाद हम एक ऐसे खिलाड़ी के बारे में बात करेंगे जिससे इस वर्ल्ड कप में भारतीय फैंस को काफी उम्मीदें रहेंगी।'),
    }
    job = RenderContext(ROOT / 'temp')
    tag = '2026-10-06-indicf5-reference-excerpts-' + uuid.uuid4().hex[:8]
    destination = ROOT / 'docs/validation' / tag
    report = dict(completed=False, human_transcripts_verified=False, voice_synthesis_tested=False,
                  production_changed=False, source_receipt=str(prior_path), references=[])
    try:
        with bind_job(job):
            work = job.workspace / 'excerpts'
            work.mkdir()
            for row in prior['references']:
                source = Path(prior['directory']) / row['reference_file']
                if digest(source) != row['reference_sha256']:
                    raise ValueError('Prepared full reference changed')
                if digest(Path(row['source'])) != row['source_sha256']:
                    raise ValueError('Original user source changed')
                seconds, text = proposals[row['name']]
                samples, rate = sf.read(source, dtype='int16')
                frames = round(seconds * rate)
                if rate != 24000 or samples.ndim != 1 or frames >= len(samples):
                    raise ValueError('Invalid excerpt bounds or input format')
                clip = work / (row['name'] + '-reference-excerpt.wav')
                sf.write(clip, samples[:frames], rate, subtype='PCM_16')
                decoded, decoded_rate = sf.read(clip, dtype='int16')
                if decoded_rate != rate or not np.array_equal(decoded, samples[:frames]):
                    raise ValueError('Excerpt samples changed')
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(clip), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                report['references'].append(dict(name=row['name'], reference_file=clip.name,
                    reference_sha256=digest(clip), start_seconds=0, end_seconds=seconds,
                    full_reference_sha256=row['reference_sha256'], original_source_sha256=row['source_sha256'],
                    original_asr_text=row['chunks'][0]['text'].strip(), proposed_reference_text=text,
                    transcript_status='unverified proposal; spelling/word corrections need listening confirmation',
                    sample_exact_excerpt=True, gain_adjusted=False, eq=False, tempo_adjusted=False,
                    full_decode_pass=True, human_transcript_verified=False))
            job.publish(work, destination)
            report.update(completed=True, directory=str(destination), original_files_unchanged=True)
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        receipt = ROOT / 'docs/validation' / (tag + '.json')
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'receipt': str(receipt), **report}, ensure_ascii=False))


if __name__ == '__main__':
    main()
