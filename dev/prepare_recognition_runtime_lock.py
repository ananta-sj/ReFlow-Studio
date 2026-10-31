"""Metadata-only proposal for the existing faster-whisper CPU worker."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dev'))
import prepare_desktop_runtime_lock as resolver


def main():
    metadata = json.loads((ROOT / 'docs/validation/2026-10-15-recognition-root-metadata.json').read_text())
    assert metadata['info']['version'] == '1.2.1'
    resolver.ROOTS.clear()
    resolver.ROOTS.update({'faster-whisper': '1.2.1'})
    resolver.PREFIX = '2026-10-15-recognition-candidate'
    sys.argv = [sys.argv[0], '--label', 'metadata-only']
    return resolver.main()


if __name__ == '__main__':
    raise SystemExit(main())
