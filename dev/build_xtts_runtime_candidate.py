"""Build the authorized offline XTTS candidate without touching working runtimes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
PROFILE=ROOT/'runtime_profiles/xtts-candidate'
STAGING=ROOT/'temp/xtts-candidate-2026-10-13-staging'
RECEIPT=OUT/'2026-10-13-xtts-candidate-install.json'
OWNER='reflow.xtts.candidate.2026-10-13'
PREFIX='xtts-candidate'

class SourcesOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        assert urlsplit(newurl).scheme=='https' and urlsplit(newurl).hostname in {
            'www.python.org','files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def hash_file(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
    return digest.hexdigest()

def fetch(row):
    target=STAGING/row['filename']
    if target.exists():
        assert hash_file(target)==row['sha256']
        return dict(filename=row['filename'],bytes=target.stat().st_size,sha256=row['sha256'],reused=True)
    url=row['url']; parsed=urlsplit(url)
    if parsed.scheme=='file':
        source=Path(urllib.request.url2pathname(parsed.path))
        assert source.resolve().is_relative_to((OUT/'2026-10-13-docopt-helper').resolve())
        shutil.copy2(source,target)
    else:
        assert parsed.scheme=='https' and parsed.hostname in {'www.python.org','files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
        # The primary CPU host serves the same published artifacts and permits download.
        url=url.replace('https://download-r2.pytorch.org/','https://download.pytorch.org/')
        pending=target.with_suffix(target.suffix+'.partial')
        opener=urllib.request.build_opener(SourcesOnly())
        try:
            with opener.open(url,timeout=45) as response,pending.open('wb') as stream:
                transferred=0
                while True:
                    block=response.read(1048576)
                    if not block:break
                    transferred+=len(block)
                    assert transferred<=row.get('bytes',30000000)
                    stream.write(block)
            assert hash_file(pending)==row['sha256']
            pending.replace(target)
        finally:
            if pending.exists():pending.unlink()
    assert hash_file(target)==row['sha256']
    if row.get('bytes'):assert target.stat().st_size==row['bytes']
    return dict(filename=row['filename'],bytes=target.stat().st_size,sha256=row['sha256'],source=row['url'])

def safe_members(archive,target):
    total=0
    assert target.resolve().is_relative_to(PROFILE.resolve())
    for entry in archive.infolist():
        # The fresh owned extraction target contains no user-controlled links.
        # Lexical checks avoid thousands of redundant filesystem resolutions.
        name=PurePosixPath(entry.filename)
        assert not name.is_absolute() and '..' not in name.parts
        assert '\\' not in entry.filename and ':' not in entry.filename
        assert not stat.S_ISLNK(entry.external_attr>>16)
        total+=entry.file_size
        assert total<3000000000
    return total

def main():
    global PROFILE,STAGING,RECEIPT,OWNER,PREFIX
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['download','install','clean-staging'])
    parser.add_argument('--resume-owned-incomplete',action='store_true')
    parser.add_argument('--variant',choices=['baseline','security'],default='baseline')
    args=parser.parse_args()
    security=args.variant=='security'
    if security:
        PREFIX='xtts-security-candidate'
        PROFILE=ROOT/'runtime_profiles'/PREFIX
        STAGING=ROOT/'temp'/f'{PREFIX}-2026-10-13-staging'
        RECEIPT=OUT/f'2026-10-13-{PREFIX}-install.json'
        OWNER='reflow.xtts.security-candidate.2026-10-13'
    if args.phase=='clean-staging':
        assert STAGING.resolve().is_relative_to((ROOT/'temp').resolve())
        assert (STAGING/'.owner').read_text()==OWNER
        assert not any(p.is_symlink() or (p.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) for p in STAGING.rglob('*'))
        size=sum(p.stat().st_size for p in STAGING.rglob('*') if p.is_file())
        shutil.rmtree(STAGING)
        (OUT/f'2026-10-13-{PREFIX}-staging-cleanup.json').write_text(json.dumps(dict(removed=True,bytes=size,owned_path=str(STAGING)),indent=2),encoding='utf-8')
        print('Owned staging removed:',size,flush=True)
        return
    plan=json.loads((OUT/'2026-10-13-runtime-repair-plan.json').read_text(encoding='utf-8'))
    lock=json.loads((OUT/('2026-10-13-xtts-security-cpu-lock-review.json' if security else '2026-10-13-xtts-candidate-lock-review.json')).read_text(encoding='utf-8'))
    sizes=json.loads((OUT/('2026-10-13-xtts-security-cpu-download-budget.json' if security else '2026-10-13-xtts-download-budget.json')).read_text(encoding='utf-8'))
    assert lock['metadata_closure_valid'] and sizes['complete']
    size_map={r['name']:r['bytes'] for r in sizes['packages']}
    if args.phase=='download':
        assert not PROFILE.exists(), 'Preserve an existing candidate'
        if not STAGING.exists():
            STAGING.mkdir(parents=True)
            (STAGING/'.owner').write_text(OWNER)
        assert (STAGING/'.owner').read_text()==OWNER
        assert shutil.disk_usage(ROOT).free>3000000000
        python=plan['python']
        rows=[] if security else [dict(filename='python-3.13.16-embed-amd64.zip',url=python['artifact_url'],sha256=python['sha256'])]
        rows += [{**row,'bytes':size_map[row['name']]} for row in lock['packages']]
        receipts=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(fetch,row) for row in rows]
            for future in futures:
                result=future.result();receipts.append(result)
                print('Verified',result['filename'],result['bytes'],flush=True)
        (OUT/f'2026-10-13-{PREFIX}-downloads.json').write_text(json.dumps(dict(
            authorized_scope='User approved separate replacement runtime and tests: exact 99-package review' if security else 'User go ahead after exact 85-package lock review; isolated candidate only',
            profile=str(PROFILE),model_downloaded=False,artifacts=receipts,total_bytes=sum(r['bytes'] for r in receipts)),indent=2),encoding='utf-8')
        return
    if PROFILE.exists():
        assert args.resume_owned_incomplete and (PROFILE/'.owner').read_text()==OWNER
        previous=json.loads(RECEIPT.read_text(encoding='utf-8'))
        assert not previous['completed']
        import time
        shutil.copy2(RECEIPT,OUT/f'2026-10-13-{PREFIX}-install-retry-{time.time_ns()}.json')
    else:
        assert not args.resume_owned_incomplete
        PROFILE.mkdir(parents=True)
        (PROFILE/'.owner').write_text(OWNER)
    assert (STAGING/'.owner').read_text()==OWNER
    downloads=json.loads((OUT/f'2026-10-13-{PREFIX}-downloads.json').read_text(encoding='utf-8'))
    for row in downloads['artifacts']:assert hash_file(STAGING/row['filename'])==row['sha256']
    receipt=dict(candidate_only=True,defaults_changed=False,model_downloaded=False,
                 install_authorized=True,completed=False,python='3.13.16',packages=len(lock['packages']))
    try:
        if security:
            source=ROOT/'runtime_profiles/xtts-candidate'
            assert (source/'.owner').read_text()=='reflow.xtts.candidate.2026-10-13'
            bootstrap=[]
            for item in source.iterdir():
                if item.is_file() and (item.suffix.lower() in {'.dll','.pyd'} or item.name in {'python.exe','pythonw.exe','python313.zip','LICENSE.txt'}):
                    assert not item.is_symlink()
                    digest=hash_file(item);shutil.copy2(item,PROFILE/item.name)
                    assert hash_file(PROFILE/item.name)==digest
                    bootstrap.append(dict(filename=item.name,sha256=digest,bytes=item.stat().st_size))
            assert {'python.exe','python313.zip','python313.dll'} <= {r['filename'] for r in bootstrap}
            receipt['reused_bootstrap']=bootstrap
        else:
            with zipfile.ZipFile(STAGING/'python-3.13.16-embed-amd64.zip') as archive:
                safe_members(archive,PROFILE)
                archive.extractall(PROFILE)
        (PROFILE/'python313._pth').write_text('python313.zip\n.\nLib/site-packages\nimport site\n',encoding='utf-8')
        destination=PROFILE/'Lib/site-packages'
        if destination.exists():assert not any(destination.iterdir()), 'Resume only before package installation started'
        destination.mkdir(parents=True,exist_ok=True)
        notices=OUT/f'2026-10-13-{PREFIX}-notices'
        notices.mkdir(exist_ok=True)
        lines=[]; inventory=[];expanded=0
        for row in lock['packages']:
            wheel=STAGING/row['filename']
            with zipfile.ZipFile(wheel) as archive:
                expanded+=safe_members(archive,destination)
                selected=[entry for entry in archive.infolist() if not entry.is_dir() and ('/licenses/' in entry.filename.lower() or
                    '.dist-info/' in entry.filename.lower() and any(x in entry.filename.rsplit('/',1)[-1].lower() for x in ('license','copying','notice')))]
                for entry in selected:
                    target=notices/row['name']/entry.filename
                    assert target.resolve().is_relative_to(notices.resolve())
                    for ancestor in target.parents:
                        if ancestor==notices:break
                        if ancestor.is_file():
                            assert ancestor.resolve().is_relative_to(notices.resolve())
                            assert args.resume_owned_incomplete and ancestor.read_bytes()==b''
                            ancestor.unlink()
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(archive.read(entry))
                inventory.append(dict(package=row['name'],version=row['version'],sha256=row['sha256'],
                    declared_license=row.get('license_expression') or row.get('license'),notice_files=[e.filename for e in selected]))
            lines.append(f"{row['name']} @ {wheel.as_uri()} --hash=sha256:{row['sha256']}")
        (notices/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
        local_lock=STAGING/'install.lock.txt'
        local_lock.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        env={**os.environ,'TEMP':str(STAGING),'TMP':str(STAGING),'PIP_NO_INDEX':'1','PYTHONDONTWRITEBYTECODE':'1'}
        command=[sys.executable,'-B','-X','utf8','-m','pip','--isolated','install',
            '--no-index','--no-deps','--no-cache-dir','--no-compile','--ignore-installed',
            '--only-binary=:all:','--python-version','3.13','--platform','win_amd64','--implementation','cp','--abi','cp313',
            '--require-hashes','--disable-pip-version-check','--target',str(destination),'-r',str(local_lock),
            '--report',str(OUT/f'2026-10-13-{PREFIX}-pip-install-report.json')]
        with (OUT/f'2026-10-13-{PREFIX}-install.log').open('wb') as log:
            result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert result.returncode==0,'See retained candidate install log'
        # Cross-target pip scripts contain the host's interpreter; the worker uses imports only.
        # Remove only these freshly generated, owned launchers rather than shipping wrong paths.
        scripts=destination/'bin'
        if scripts.exists():
            assert scripts.resolve().is_relative_to(PROFILE.resolve())
            assert not scripts.is_symlink()
            shutil.rmtree(scripts)
        receipt.update(completed=True,expanded_wheel_bytes=expanded,
            runtime_bytes=sum(p.stat().st_size for p in PROFILE.rglob('*') if p.is_file()),
            advisory_matches_present=not security,release_eligible=False,cross_target_cli_launchers_removed=True)
        (PROFILE/'profile.json').write_text(json.dumps(dict(profile=PREFIX,status='candidate-unverified',
            python='3.13.16',device='cpu',production_default=False,release_eligible=False),indent=2),encoding='utf-8')
    except Exception as error:
        receipt['error']=str(error)
        raise
    finally:
        RECEIPT.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)

if __name__=='__main__':main()
