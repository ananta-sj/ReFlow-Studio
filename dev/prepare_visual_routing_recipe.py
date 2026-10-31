"""Bind the approved candidate to its current reviewed worker sources."""
import argparse,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.visual_runtime import SOURCES,validate
from core.runtime_integrity import sha
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    build=json.loads((ROOT/'docs/validation/2026-10-16-visual-candidate-build.json').read_text());assert build['completed']
    target=ROOT/'runtime_profiles/visual-candidate/routing-recipe.json'
    recipe=dict(schema='reflow.visual-runtime.v1',source_sha256={name:sha(ROOT/name) for name in SOURCES})
    if target.exists() and json.loads(target.read_text())!=recipe:
        assert args.refresh,'Source drift: explicitly revalidate before rebinding'
        prior=ROOT/('docs/validation/2026-10-16-visual-recipe-before-'+sha(target)[:12]+'.json')
        if not prior.exists():prior.write_bytes(target.read_bytes())
    target.write_text(json.dumps(recipe,indent=2),encoding='utf-8')
    print(json.dumps(validate(),indent=2))
if __name__=='__main__':main()
