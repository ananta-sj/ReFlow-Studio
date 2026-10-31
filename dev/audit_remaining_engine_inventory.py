"""Local inventory only; do not load custom checkpoints or alter profiles."""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core.runtime_integrity import sha

def main():
    registry=json.loads((ROOT/'models.json').read_text(encoding='utf-8'));voices=[row for row in registry['entries'] if row.get('stage_type')=='voice']
    checkpoints={path.resolve() for path in (ROOT/'models/rvc').rglob('*.pth') if path.is_file()}
    for row in voices:
        path=Path(row.get('local_path') or '')
        if row.get('status')=='installed' and path.is_file() and path.suffix.lower()=='.pth':checkpoints.add(path.resolve())
    packages={};duplicates={};malformed=[]
    names={'rvc-python','fairseq','gfpgan','basicsr','facexlib','torchvision','torch','numpy','omegaconf','hydra-core'}
    for dist in metadata.distributions(path=[str(ROOT/'build/windows-portable/Lib/site-packages')]):
        raw=dist.metadata.get('Name')
        if not raw:malformed.append(str(dist._path.relative_to(ROOT)));continue
        name=raw.lower().replace('_','-')
        if name not in names:continue
        row=dict(version=dist.version,requires_python=dist.metadata.get('Requires-Python'),requires_dist=dist.requires or [],metadata_sha256=sha(Path(dist._path)/'METADATA'))
        if name in packages:duplicates.setdefault(name,[packages[name]]).append(row)
        else:packages[name]=row
    assets={}
    from core.model_assets import ASSETS
    for feature in ['gfpgan','wav2lip','musetalk']:
        assets[feature]=[]
        for relative,url,size in ASSETS[feature]:
            path=ROOT/relative
            assets[feature].append(dict(path=relative,exists=path.is_file(),bytes=path.stat().st_size if path.is_file() else None,expected_bytes=size,size_matches=path.is_file() and (size is None or path.stat().st_size==size)))
    result=dict(local_inventory_complete=True,models_loaded=False,models_downloaded=False,packages_installed=False,
        registered_voice_entries=len(voices),installed_registered_voice_entries=sum(row.get('status')=='installed' for row in voices),
        rvc_checkpoint_candidates=[dict(path=str(path),bytes=path.stat().st_size) for path in sorted(checkpoints)],
        actual_rvc_conversion_testable_with_discovered_checkpoints=bool(checkpoints),
        searched_scope=['models/rvc/**/*.pth','installed voice entries explicitly registered in models.json'],
        packages=packages,duplicate_metadata=duplicates,malformed_metadata_paths=malformed,assets=assets,
        asset_hashes_not_verified_by_size_inventory=True,release_ready=False)
    (ROOT/'docs/validation/2026-10-16-remaining-engines-inventory.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
