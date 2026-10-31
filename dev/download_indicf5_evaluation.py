"""Download approved pinned evaluation assets; does not execute model code."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'ba85abedf18dc479a447eaa0eccbd76ab78a47d5'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
if (ROOT / 'models/indicf5/evaluation/auth/token').is_file():
    os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')


def main():
    from huggingface_hub import HfApi, hf_hub_download
    destination = ROOT / 'models/indicf5/evaluation/assets'
    destination.mkdir(parents=True, exist_ok=True)
    report = dict(repository='ai4bharat/IndicF5', revision=REVISION,
                  model_code_executed=False, complete=False, files=[])
    started = time.monotonic()
    try:
        info = HfApi().model_info(report['repository'], revision=REVISION, files_metadata=True)
        expected = {item.rfilename: item for item in info.siblings}
        for name in ('config.json', 'model.py', 'checkpoints/vocab.txt', 'model.safetensors',
                     'prompts/PAN_F_HAPPY_00001.wav', 'README.md'):
            path = Path(hf_hub_download(report['repository'], filename=name, revision=REVISION,
                                       local_dir=str(destination)))
            checksum = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    checksum.update(chunk)
            row = dict(name=name, bytes=path.stat().st_size, sha256=checksum.hexdigest())
            if row['bytes'] != expected[name].size:
                raise ValueError('Downloaded file size differs from pinned metadata')
            lfs = expected[name].lfs
            expected_hash = (lfs.get('sha256') if isinstance(lfs, dict) else getattr(lfs, 'sha256', None)) if lfs else None
            if expected_hash:
                row['remote_sha256_matches'] = row['sha256'] == expected_hash
                if not row['remote_sha256_matches']:
                    raise ValueError('Downloaded file checksum differs from pinned metadata')
            report['files'].append(row)
            print(json.dumps(row), flush=True)
        report['complete'] = True
    except Exception as exc:
        response = getattr(exc, 'response', None)
        report.update(error_type=type(exc).__name__, http_status=getattr(response, 'status_code', None))
        raise
    finally:
        report.update(directory=str(destination), elapsed_seconds=round(time.monotonic()-started, 3))
        receipt = ROOT / 'docs/validation' / ('2026-10-06-indicf5-download-' + uuid.uuid4().hex[:8] + '.json')
        receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
