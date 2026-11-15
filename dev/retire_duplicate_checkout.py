"""Archive and verify the clean old checkout before retiring its exact directory."""
import hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'Github'/'ReFlow-Studio'

def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args]).decode().strip()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    expected='0756bff115d28e0b26ba70f0a6387b1763a56ed9'
    if OLD.resolve()!=ROOT.parent.resolve()/'Github'/'ReFlow-Studio' or OLD.is_symlink():
        raise ValueError('Unexpected duplicate directory')
    if git(OLD,'status','--porcelain','--untracked-files=all') or git(OLD,'rev-parse','HEAD')!=expected:
        raise ValueError('Old checkout changed; compare again before retiring it')
    if git(ROOT,'rev-parse','refs/remotes/github-local/main')!=expected:
        raise ValueError('Published history must already be preserved in the native checkout')
    target=ROOT/'docs/diagnostics/checkout-consolidation';target.mkdir(parents=True,exist_ok=True)
    archive=target/'old-github-checkout.zip'
    files={}
    for path in OLD.rglob('*'):
        if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError('Refusing a linked checkout')
        if path.is_file():files[path.relative_to(OLD).as_posix()]=sha(path)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):bundle.write(OLD/name,name)
    with zipfile.ZipFile(archive) as bundle:
        for name,digest in files.items():
            if hashlib.sha256(bundle.read(name)).hexdigest()!=digest:raise ValueError('Backup readback failed')
    current={p.relative_to(OLD).as_posix():sha(p) for p in OLD.rglob('*') if p.is_file()}
    if current!=files:raise ValueError('Duplicate changed while backing up; no removal performed')
    receipt=dict(old_checkout=str(OLD),canonical_checkout=str(ROOT),head=expected,
        files=len(files),original_bytes=sum((OLD/name).stat().st_size for name in files),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),backup_readback_verified=True)
    (target/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    # Explicit, verified absolute directory within the user-named GitHub folder.
    shutil.rmtree(OLD)
    (OLD.parent/'USE_NATIVE_CHECKOUT.txt').write_text('ReFlow Studio now uses one working checkout:\n'+str(ROOT)+'\n\nAdd that existing repository in GitHub Desktop.\nBranch: codex/episode-readiness\nRemote: https://github.com/ananta-sj/ReFlow-Studio.git\nThe old clean checkout is backed up under the native docs/diagnostics/checkout-consolidation folder.\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
