"""Reproducible metadata-only compatibility wheel; upstream code/licences retained."""
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


OLD = 'cached_path-1.8.10.dist-info/'
NEW = 'cached_path-1.8.10+reflow.1.dist-info/'


def build_wheel(source, output, expected_sha256):
    source, output = Path(source), Path(output)
    if source.stat().st_size > 1024*1024:
        raise RuntimeError('Upstream cache wheel exceeds reviewed size budget')
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RuntimeError('Upstream cache wheel identity differs from review')
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        if sum(row.file_size for row in bundle.infolist()) > 16*1024*1024:
            raise RuntimeError('Unexpected cache wheel expansion')
        names = bundle.namelist()
        if len(names) != len(set(names)) or any(name.endswith(('RECORD.jws', 'RECORD.p7s')) for name in names):
            raise RuntimeError('Unexpected duplicate or signed wheel records')
        if any(Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name for name in names):
            raise RuntimeError('Unsafe upstream wheel member')
        files = {name: bundle.read(name) for name in names if not name.endswith('/')}
    metadata = files[OLD+'METADATA'].decode('utf-8')
    for pattern, replacement in (
        (r'^Version: 1\.8\.10$', 'Version: 1.8.10+reflow.1'),
        (r'^Requires-Dist: filelock[^\n]*$', 'Requires-Dist: filelock>=4.2.12,<5'),
        (r'^Requires-Dist: huggingface-hub[^\n]*$', 'Requires-Dist: huggingface-hub>=1.32.0,<3'),
    ):
        metadata, count = re.subn(pattern, replacement, metadata, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError('Reviewed cache metadata layout changed')
    files[OLD+'METADATA'] = metadata.encode('utf-8')
    files = {name.replace(OLD, NEW): data for name, data in files.items() if name != OLD+'RECORD'}
    records = io.StringIO(newline='')
    writer = csv.writer(records, lineterminator='\n')
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow([name, 'sha256='+digest, len(data)])
    writer.writerow([NEW+'RECORD', '', ''])
    files[NEW+'RECORD'] = records.getvalue().encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.create_system = 0
            info.external_attr = 0o644 << 16
            bundle.writestr(info, data)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Downloaded reviewed upstream wheel')
    parser.add_argument('--output', type=Path, default=root/'build/optional-wheels')
    args = parser.parse_args()
    recipe = json.loads((root/'packaging/optional/cached-path-compat.json').read_text(encoding='utf-8'))
    output = args.output/recipe['filename']
    digest = build_wheel(args.source, output, recipe['upstream_sha256'])
    if digest != recipe['sha256']:
        raise RuntimeError('Compatibility wheel differs from the reviewed identity; do not install it')
    print(output)


if __name__ == '__main__':
    main()
