"""Remove only the named aborted transfer if every byte is zero."""
import json
from pathlib import Path
import time
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'models/translation/indictrans2-evaluation/.cache/huggingface/download/indictrans2-xet-aborted.tmp'
assert path.resolve().is_relative_to(ROOT / 'models/translation/indictrans2-evaluation')
started = time.monotonic()
parser = argparse.ArgumentParser()
parser.add_argument('--verified-replacement', action='store_true')
args = parser.parse_args()
report = dict(path=str(path), exists=path.is_file(), removed=False)
replacement_verified = False
if args.verified_replacement:
    replacement = ROOT / 'models/translation/indictrans2-evaluation/model.safetensors'
    checksum = hashlib.sha256()
    with replacement.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            checksum.update(chunk)
    replacement_verified = (replacement.stat().st_size == 4462265272 and
                            checksum.hexdigest() == '35d28fe035cd6ac026536b555558b07762425c8b930670219063e4fc3666c96d')
    assert replacement_verified, 'Preserve partial transfer if replacement integrity is unverified'
    report['replacement_size_and_sha256_verified'] = True
if path.is_file():
    report['bytes'] = path.stat().st_size
    all_zero = True
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            if chunk.strip(b'\0'):
                all_zero = False
                break
    report['entire_file_zero_filled'] = all_zero
    if all_zero or replacement_verified:
        path.unlink()
        report['removed'] = True
report['elapsed_seconds'] = round(time.monotonic()-started, 3)
receipt_name = ('2026-10-08-indictrans2-verified-replacement-cleanup.json' if args.verified_replacement else
                '2026-10-08-indictrans2-aborted-transfer-cleanup.json')
(ROOT / 'docs/validation' / receipt_name).write_text(
    json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
