"""Bind the approved built/tested packages to the M2M100 worker sources."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.runtime_integrity import sha
    from core.m2m100_runtime import SOURCES,validate
    out=ROOT/'docs/validation'
    build=json.loads((out/'2026-10-16-translation-candidate-build.json').read_text())
    native=json.loads((out/'2026-10-16-translation-candidate-native.json').read_text())
    assert build['completed'] and native['passed']
    recipe=dict(schema='reflow.m2m100-runtime.v1',source_sha256={name:sha(ROOT/name) for name in SOURCES})
    path=ROOT/'runtime_profiles/translation-candidate/routing-recipe.json'
    if path.exists() and json.loads(path.read_text())!=recipe:raise RuntimeError('Preserve earlier routing recipe; review changes before rebinding')
    path.write_text(json.dumps(recipe,indent=2),encoding='utf-8')
    print(json.dumps(validate(),indent=2))


if __name__=='__main__':main()
