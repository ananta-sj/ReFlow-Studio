"""Resume approved official Torch wheel with bounded, verified byte ranges."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs/validation/2026-10-06-indicf5-gpu-range-download.json'
PART = ROOT / 'temp/indicf5-gpu-wheels/torch-2.9.1+cu128-cp310-cp310-win_amd64.whl.part'
FINAL = PART.with_suffix('')
STEP = 32 * 1024 * 1024


def main():
    probe = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-range-probe.json').read_text())
    snapshot = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-prefix-snapshot.json').read_text())
    match = re.fullmatch(r'bytes 0-31/(\d+)', probe['content_range'])
    if probe['status'] != 206 or not match or probe['zip_magic'] != '504b0304':
        raise ValueError('Official range capability not established')
    url = probe['url']
    if url != 'https://download-r2.pytorch.org/whl/cu128/torch-2.9.1%2Bcu128-cp310-cp310-win_amd64.whl':
        raise ValueError('Unexpected download source')
    expected = probe['sha256']
    total = int(match[1])
    if FINAL.exists():
        raise FileExistsError('Preserve existing completed wheel')
    if MANIFEST.exists():
        report = json.loads(MANIFEST.read_text())
        if report['sha256'] != expected or report['bytes'] != total or report['url'] != url:
            raise ValueError('Resume manifest differs from official asset')
    else:
        prefix = snapshot['seed_prefix_bytes']
        if Path(snapshot['partial_file']).resolve() != PART.resolve() or PART.stat().st_size != prefix:
            raise ValueError('Preserved prefix size/path changed')
        report = dict(url=url, sha256=expected, bytes=total, seed_prefix_bytes=prefix,
                      completed_ranges=[], complete=False, workers=8, attempts=0)
    if not 0 <= report['seed_prefix_bytes'] < total:
        raise ValueError('Invalid resume prefix')
    lock = threading.Lock()
    def save():
        pending = MANIFEST.with_suffix('.pending')
        pending.write_text(json.dumps(report, indent=2))
        os.replace(pending, MANIFEST)
    save()
    with PART.open('r+b') as handle:
        handle.truncate(total)
    ranges = [(start, min(start+STEP, total)-1) for start in range(report['seed_prefix_bytes'], total, STEP)]
    done = {tuple(row) for row in report['completed_ranges']}
    if any(row not in ranges for row in done):
        raise ValueError('Resume ranges do not match planned nonoverlapping ranges')
    local = threading.local()
    def transfer(bounds):
        start, end = bounds
        if not hasattr(local, 'session'):
            local.session = requests.Session()
        for attempt in range(3):
            try:
                with local.session.get(url, headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'},
                                       stream=True, timeout=(15, 45)) as response:
                    if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
                        raise ValueError('Server returned an unexpected byte range')
                    written = 0
                    with PART.open('r+b') as handle:
                        handle.seek(start)
                        for block in response.iter_content(1024*1024):
                            if written+len(block) > end-start+1:
                                raise ValueError('Range body exceeds bounds')
                            handle.write(block)
                            written += len(block)
                        if written != end-start+1:
                            raise ValueError('Range body incomplete')
                        handle.flush()
                        os.fsync(handle.fileno())
                with lock:
                    report['completed_ranges'].append(list(bounds))
                    save()
                    received = report['seed_prefix_bytes']+sum(b-a+1 for a,b in report['completed_ranges'])
                    print(json.dumps({'verified_range_bytes_received': received, 'total_bytes': total}), flush=True)
                return
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1)
    started = time.monotonic()
    report['attempts'] += 1
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(transfer, bounds) for bounds in ranges if bounds not in done]
            for future in as_completed(futures):
                future.result()
        complete = {tuple(row) for row in report['completed_ranges']}
        if complete != set(ranges):
            raise ValueError('Completed byte ranges do not cover remaining wheel')
        digest = hashlib.sha256()
        with PART.open('rb') as handle:
            for block in iter(lambda: handle.read(8*1024*1024), b''):
                digest.update(block)
        report['actual_sha256'] = digest.hexdigest()
        if report['actual_sha256'] != expected:
            raise ValueError('Full wheel checksum differs from official index')
        os.replace(PART, FINAL)
        report.update(complete=True, full_checksum_pass=True, final_file=str(FINAL))
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report['last_attempt_seconds'] = round(time.monotonic()-started, 3)
        save()
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
