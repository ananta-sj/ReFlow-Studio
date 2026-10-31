"""Reproduce directory/file replacement locks using only disposable fixtures."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev.windows_lock_fixture import deny_delete


def main():
    if os.name != 'nt':
        raise RuntimeError('Windows reproduction requires Windows')
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / 'temp', prefix='publish-diagnostic-') as folder:
        base = Path(folder)
        for kind in ('directory', 'directory_child', 'pending_file', 'destination_file'):
            pending, destination = base / ('pending-' + kind), base / ('published-' + kind)
            if kind.startswith('directory'):
                pending.mkdir()
                (pending / 'review.json').write_text('new review', encoding='utf-8')
            else:
                pending.write_text('new result', encoding='utf-8')
                destination.write_text('old result', encoding='utf-8')
            row = {'kind': kind}
            locked = destination if kind == 'destination_file' else pending
            if kind == 'directory_child':
                locked = pending / 'review.json'
            with deny_delete(locked):
                try:
                    os.replace(pending, destination)
                    row['locked_replace'] = 'unexpected_success'
                except PermissionError as exc:
                    row.update(locked_replace='denied', winerror=exc.winerror,
                               pending_preserved=pending.exists(),
                               destination_preserved=not destination.exists() if kind.startswith('directory') else destination.read_text() == 'old result')
            os.replace(pending, destination)
            row['replace_after_release'] = 'passed'
            rows.append(row)
    report = dict(schema='reflow.windows-publication-reproduction.v1', observations=rows,
                  original_lock_holder_identified=False,
                  explanation='A controlled handle reproduces the error class; it does not identify the holder in the historical failure.')
    path = ROOT / 'docs/validation/2026-10-09-windows-publication-reproduction.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
