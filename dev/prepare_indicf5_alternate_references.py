"""Preserve alternate original phrases for human transcript review; no synthesis."""
import hashlib
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import numpy as np
    import soundfile as sf
    source = ROOT / 'docs/validation/2026-10-06-indicf5-user-references-984652c4'
    cases = [
        ('sujata', 10.82, None, 'fdf7d130dfea7059383fe2488fabe3caecda0349947ffad863ed8405f9fc296a',
         'पौधे के जिस हिस्से में क्लोरोफिल पाया जाता है, वो हरा होता है।'),
        ('abhishek', 6.0, 13.65, '47ca77956eb23607f1b2de4d7785d0308d761d2267eb5863e8e912272ac3ce17',
         'इस खिलाड़ी के बारे में मैं आपको बस इतना बता दूँ कि यह वो खिलाड़ी है जिसने इंटरनेशनल क्रिकेट में अपनी एंट्री का ऐलान ऑस्ट्रेलिया के अगेंस्ट ज़ोरदार प्रदर्शन से किया।')]
    destination = ROOT / 'docs/validation' / ('2026-10-06-indicf5-alternate-references-' + uuid.uuid4().hex[:8])
    destination.mkdir()
    report = dict(completed=False, human_transcripts_verified=False, used_for_synthesis=False,
                  production_changed=False, directory=str(destination), references=[])
    for name, start, end, expected, transcript in cases:
        path = source / (name + '-full-reference.wav')
        if digest(path) != expected:
            raise ValueError('Original decoded reference changed')
        samples, rate = sf.read(path, dtype='int16')
        if rate != 24000 or samples.ndim != 1:
            raise ValueError('Expected original mono 24 kHz reference')
        first = round(start * rate)
        last = len(samples) if end is None else round(end * rate)
        excerpt = samples[first:last]
        output = destination / (name + '-alternate-reference.wav')
        sf.write(output, excerpt, rate, subtype='PCM_16')
        restored, restored_rate = sf.read(output, dtype='int16')
        if restored_rate != rate or not np.array_equal(restored, excerpt):
            raise ValueError('Excerpt samples changed')
        report['references'].append(dict(voice=name, source=str(path), source_sha256=expected,
            file=str(output), sha256=digest(output), start_sample=first, end_sample=last,
            seconds=len(excerpt)/rate, transcript_draft=transcript,
            transcript_status='unverified ASR-derived wording; human exact-word confirmation required',
            sample_exact_slice=True, gain_changed=False, tempo_changed=False))
    report['completed'] = True
    receipt = destination.with_suffix('.json')
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(receipt))


if __name__ == '__main__':
    main()
