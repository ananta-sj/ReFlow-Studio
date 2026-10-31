"""Pin existing ASR files against the previously captured upstream metadata."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT/'docs/validation/2026-10-04-f5-asr-source.json').read_text())
model = ROOT/'models/f5/reference-asr'
rows = []
for asset in sorted(model.iterdir()):
    if not asset.is_file():
        continue
    upstream = next(row for row in source['siblings'] if row['rfilename'] == asset.name)
    assert asset.stat().st_size == upstream['size'], asset.name
    sha256 = hashlib.sha256()
    blob = hashlib.sha1(b'blob '+str(asset.stat().st_size).encode()+b'\0')
    with asset.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            sha256.update(block)
            blob.update(block)
    if 'lfs' in upstream:
        assert sha256.hexdigest() == upstream['lfs']['sha256'], asset.name
    else:
        assert blob.hexdigest() == upstream['blobId'], asset.name
    rows.append(dict(name=asset.name, bytes=asset.stat().st_size, sha256=sha256.hexdigest()))
manifest = dict(model_id=source['id'], revision=source['sha'], files=rows)
(ROOT/'core/whisper_turbo_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(completed=True, revision=source['sha'], verified_existing_files=len(rows))))
