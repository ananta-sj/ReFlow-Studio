"""Record/check original XTTS assets and app state around candidate evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):value.update(block)
    return value.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['before','after']);args=parser.parse_args()
    path=OUT/'2026-10-13-xtts-candidate-preservation-before.json'
    state=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text(encoding='utf-8'))['state']
    assets={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'models/xtts/default').iterdir() if p.is_file()}
    state_checks={name:digest(ROOT/name)==row['current'].lower() for name,row in state.items()}
    receipt=dict(assets=assets,state=state_checks,passed=all(state_checks.values()))
    if args.phase=='before':
        assert not path.exists(),'Preserve the existing before receipt'
    else:
        before=json.loads(path.read_text(encoding='utf-8'))
        receipt['assets_unchanged']=assets==before['assets']
        receipt['passed'] &= receipt['assets_unchanged']
        tested=json.loads((OUT/'2026-10-12-windows-release-backend-complete.json').read_text(encoding='utf-8'))
        maps=[v for v in tested.values() if isinstance(v,dict) and v and all(isinstance(d,str) and len(d)==64 for d in v.values())]
        changed=[]
        for mapping in maps:
            for name,value in mapping.items():
                source=Path(name) if Path(name).is_absolute() else ROOT/name
                if not source.is_file() or digest(source)!=value.lower():changed.append(name)
        receipt['changed_production_sources']=changed
        receipt['production_sources_unchanged']=bool(maps) and not changed
        receipt['ollama_trial_absent']=not (ROOT/'temp/ollama-eval-c_lslq8w').exists()
        receipt['passed'] &= receipt['production_sources_unchanged'] and receipt['ollama_trial_absent']
        path=OUT/'2026-10-13-xtts-candidate-preservation-after.json'
    path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2));return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
