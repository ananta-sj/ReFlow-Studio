"""Resumable pinned download with verified ranges and no signed URL logging."""
import hashlib
import json
import os
from pathlib import Path
import time
import requests
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')
from huggingface_hub import HfApi, get_token


def main():
    receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-download-weights.json'
    prior_receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-http-progress.json'
    source = json.loads((ROOT / 'docs/validation/2026-10-08-indictrans2-download-source.json').read_text(encoding='utf-8'))
    assert source['complete']
    destination = ROOT / 'models/translation/indictrans2-evaluation'
    partial = destination / 'model.safetensors.http-ranged.partial'
    final = destination / 'model.safetensors'
    assert not final.exists(), 'Preserve existing completed model'
    report = {**source, 'complete':False, 'weights_requested':True, 'transfer_backend':'fresh-http-ranges',
              'verified_range_bytes':0, 'download_workers':4, 'downloading':'model.safetensors'}
    started = time.monotonic()
    def save():
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        prior_receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')
        receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        info = HfApi().model_info(source['repository'], revision=source['revision'], files_metadata=True)
        asset = next(item for item in info.siblings if item.rfilename == 'model.safetensors')
        lfs = asset.lfs
        remote_hash = lfs.get('sha256') if isinstance(lfs, dict) else lfs.sha256
        report['expected_weight_bytes'] = asset.size
        report['expected_weight_sha256'] = remote_hash
        verified = 0
        if partial.exists() and prior_receipt.exists():
            previous = json.loads(prior_receipt.read_text(encoding='utf-8'))
            assert previous.get('expected_weight_sha256') == remote_hash
            verified = int(previous.get('verified_range_bytes', 0))
            assert 0 <= verified <= partial.stat().st_size <= asset.size
        report['verified_range_bytes'] = verified
        save()
        url = 'https://huggingface.co/'+source['repository']+'/resolve/'+source['revision']+'/model.safetensors'
        redirect = requests.get(url, params={'download':'true', 'fresh':str(time.time_ns())},
            headers={'Authorization':'Bearer '+get_token(), 'Cache-Control':'no-cache'},
            allow_redirects=False, timeout=(10,30))
        assert redirect.status_code in (302,307), 'Fresh model redirect unavailable'
        location = redirect.headers.get('Location')
        assert location and location.startswith('https://'), 'Model redirect is not HTTPS'
        def fetch_range(bounds):
            begin, end = bounds
            with requests.get(location, headers={'Range':f'bytes={begin}-{end}'},
                              timeout=(10,30)) as response:
                assert response.status_code == 206, 'Range transfer did not return HTTP 206'
                assert response.headers.get('Content-Range') == f'bytes {begin}-{end}/{asset.size}', 'Range mismatch'
                assert len(response.content) == end-begin+1, 'Incomplete range body'
                return response.content
        with partial.open('r+b' if partial.exists() else 'w+b') as output, ThreadPoolExecutor(max_workers=4) as pool:
            output.truncate(verified)
            output.seek(verified)
            while verified < asset.size:
                bounds = [(begin, min(begin+64*1024*1024, asset.size)-1)
                          for begin in range(verified, min(verified+4*64*1024*1024, asset.size), 64*1024*1024)]
                for (begin, end), content in zip(bounds, pool.map(fetch_range, bounds)):
                    assert begin == verified
                    output.write(content)
                    output.flush()
                    verified = end+1
                    report['verified_range_bytes'] = verified
                    save()
                    print(json.dumps(dict(bytes=verified, total_bytes=asset.size)), flush=True)
        checksum = hashlib.sha256()
        with partial.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8*1024*1024), b''):
                checksum.update(chunk)
        assert partial.stat().st_size == asset.size and checksum.hexdigest() == remote_hash, 'Weight integrity failure'
        partial.replace(final)
        report['files'].append(dict(name='model.safetensors', bytes=asset.size,
                                   sha256=checksum.hexdigest(), remote_sha256_matches=True))
        report['complete'] = True
        report.pop('downloading', None)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        # Do not print exceptions containing signed download URLs.
    finally:
        save()
        print(json.dumps(dict(complete=report['complete'], error_type=report.get('error_type'), receipt=str(receipt))), flush=True)
    if not report['complete']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
