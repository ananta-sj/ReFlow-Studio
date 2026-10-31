"""Refresh stage/worker cleanup files after the owned first assembly completes."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.stage_checkpoints import safe_path
TARGET=safe_path(ROOT/'dist/portable-xtts-trial-2026-10-13')
FILES=['core/providers/base.py','core/providers/tts/xtts_local.py','core/pipeline.py','core/cue_review.py','core/feature_session.py']
def main():
    if not TARGET.is_relative_to(ROOT):raise RuntimeError('Unsafe QA target')
    manifest_path=safe_path(TARGET/'portable-manifest.json')
    manifest=json.loads(manifest_path.read_text())
    if manifest.get('release_ready') is not False or manifest.get('optional_profiles')!=['xtts-security-candidate']:
        raise RuntimeError('Expected the owned XTTS trial manifest')
    rows={row['path']:row for row in manifest['files']}
    if len(rows)!=len(manifest['files']) or any(name not in rows for name in FILES):
        raise RuntimeError('Incomplete QA inventory')
    updates=[]
    for name in FILES:
        source=safe_path(ROOT/name);target=safe_path(TARGET/name)
        shutil.copy2(source,target)
        expected=hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise RuntimeError('QA copy hash mismatch')
        rows[name]['bytes']=source.stat().st_size
        updates.append(dict(path=name,sha256=expected))
    groups={}
    for row in manifest['files']:groups[row['component']]=groups.get(row['component'],0)+row['bytes']
    manifest['bytes_by_component']=groups
    manifest['post_assembly_stage_cleanup_refresh']=True
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (ROOT/'docs/validation/2026-10-13-xtts-portable-trial-manifest.json').write_text(json.dumps({**manifest,'output':str(TARGET)},indent=2),encoding='utf-8')
    receipt=dict(passed=True,target=str(TARGET),updated=updates)
    (ROOT/'docs/validation/2026-10-13-xtts-portable-trial-refresh.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
