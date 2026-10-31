"""Bind NLLB's existing CPU runtime without installing or downloading."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    from core.xtts_runtime import validate as existing
    from core.nllb_runtime import SOURCES, MANIFEST, validate
    from core.runtime_integrity import sha
    receipt = json.loads((ROOT/'docs/validation/2026-10-16-nllb-existing-runtime-feasibility.json').read_text())
    route = existing()
    assert receipt['passed'] and receipt['runtime']['identity'] == route['identity']
    data = dict(schema='reflow.nllb-runtime.v1', package_runtime_identity=route['identity'],
                source_sha256={name: sha(ROOT/name) for name in SOURCES})
    path = ROOT/MANIFEST
    if path.exists() and json.loads(path.read_text()) != data:
        raise RuntimeError('A different NLLB recipe exists; review before replacing it')
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(validate(), indent=2))


if __name__ == '__main__':
    main()
