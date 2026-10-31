"""Bind the already evaluated engine/runtime to an explicit routing recipe.

Does not install packages, switch settings or claim automatic Hindi accuracy.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    from core.recognition_runtime import SOURCES, PROFILE, LOCK, validate
    from core.xtts_runtime import sha
    accepted = json.loads((ROOT/'docs/validation/2026-10-15-recognition-language-acceptance.json').read_text())
    previous = json.loads((ROOT/'docs/validation/2026-10-15-recognition-candidate-acceptance.json').read_text())
    assert accepted['passed'] and accepted['cpu_hindi_hint_passed']
    # These inference/decoding sources are unchanged since real worker tests.
    for name in SOURCES:
        evidence = previous if name == 'core/recognition_compat.py' else accepted
        assert sha(ROOT/name) == evidence['source_sha256'][name], name
    folder = ROOT/'runtime_profiles'/PROFILE
    data = dict(schema='reflow.recognition-runtime.v1', python='3.13.16', device='cpu',
                bootstrap_sha256={name: sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')},
                source_sha256={name: sha(ROOT/name) for name in SOURCES}, lock_sha256=sha(ROOT/LOCK))
    path = folder/'routing-recipe.json'
    if path.exists() and json.loads(path.read_text()) != data:
        raise RuntimeError('A different recognition recipe already exists; review before replacing it')
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(validate(), indent=2))


if __name__ == '__main__':
    main()
