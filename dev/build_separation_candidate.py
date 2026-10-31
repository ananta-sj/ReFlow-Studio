"""Build the explicitly approved 32-package CPU separation candidate."""
import base64,csv,hashlib,json,shutil,stat,sys,zipfile,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from core.runtime_integrity import sha,safe_path
from build_translation_candidate import ArtifactsOnly
OUT=ROOT/'docs/validation';SOURCE=ROOT/'runtime_profiles/xtts-security-candidate'
PROFILE=ROOT/'runtime_profiles/separation-candidate';STAGE=ROOT/'temp/separation-candidate-2026-10-16-staging'
OWNER='reflow.separation.candidate.2026-10-16'

def main():
    from core.xtts_runtime import validate
    lock_path=OUT/'2026-10-16-separation-runtime-lock-review.json';plan=json.loads(lock_path.read_text())
    prepared=json.loads((OUT/'2026-10-16-separation-helpers-acceptance.json').read_text())
    assert prepared['passed'] and sha(lock_path)==prepared['lock_sha256']
    assert validate()['identity']==plan['source_runtime_identity'] and plan['package_count']==32
    assert not PROFILE.exists() and not STAGE.exists(),'Preserve earlier candidate/staging'
    safe_path(PROFILE.parent);safe_path(STAGE.parent)
    STAGE.mkdir();(STAGE/'.owner').write_text(OWNER)
    PROFILE.mkdir();(PROFILE/'.owner').write_text(OWNER)
    report=dict(completed=False,models_downloaded=False,defaults_changed=False,source_runtime_modified=False,lock_sha256=sha(lock_path),archives=[])
    try:
        site=SOURCE/'Lib/site-packages';items={};outside=[];wheels=[]
        for row in plan['packages']:
            if row['source']=='copy-existing':
                meta=ROOT/row['source_metadata'];record=meta.parent/'RECORD'
                assert sha(meta)==row['metadata_sha256'] and sha(record)==row['record_sha256']
                for name,digest,size in csv.reader(record.read_text(encoding='utf-8').splitlines()):
                    rel=PurePosixPath(name)
                    if rel.is_absolute() or '..' in rel.parts or '\\' in name:outside.append(name);continue
                    if rel.suffix in {'.pyc','.pyo'}:continue
                    assert not digest or digest.startswith('sha256=')
                    if name in items:assert items[name]==(digest,size)
                    items[name]=(digest,size)
            else:
                if row['source']=='approved-built-wheel':path=ROOT/row['local_wheel']
                else:
                    parsed=urlsplit(row['url']);assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org'
                    with urllib.request.build_opener(ArtifactsOnly()).open(row['url'],timeout=45) as response:data=response.read(row['archive_bytes']+1)
                    assert len(data)==row['archive_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
                    path=STAGE/row['filename'];path.write_bytes(data)
                    report['archives'].append(dict(name=row['name'],bytes=len(data),sha256=row['sha256']))
                assert sha(path)==row['sha256'];wheels.append((row,path))
        for row in plan['bootstrap']:
            assert sha(SOURCE/row['name'])==row['sha256'];shutil.copy2(SOURCE/row['name'],PROFILE/row['name'])
            assert sha(PROFILE/row['name'])==row['sha256']
        destination=PROFILE/'Lib/site-packages';destination.mkdir(parents=True)
        checked=set()
        for name in items:
            path=site/name
            if path.parent not in checked:safe_path(path.parent);checked.add(path.parent)
            assert not path.is_symlink() and not getattr(path.lstat(),'st_file_attributes',0)&0x400
        def copy(item):
            name,(digest,size)=item;target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(site/name,target)
            data=target.read_bytes()
            if digest:assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
            if size:assert len(data)==int(size)
            return len(data)
        with ThreadPoolExecutor(max_workers=4) as pool:copied=sum(pool.map(copy,items.items()))
        wheel_files=0
        for row,path in wheels:
            with zipfile.ZipFile(path) as archive:
                record=next(n for n in archive.namelist() if n.endswith('/RECORD'))
                for name,digest,size in csv.reader(archive.read(record).decode().splitlines()):
                    if digest:
                        data=archive.read(name);assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=') and len(data)==int(size)
                for member in archive.infolist():
                    rel=PurePosixPath(member.filename)
                    assert not rel.is_absolute() and '..' not in rel.parts and '\\' not in member.filename and ':' not in member.filename
                    assert not stat.S_ISLNK(member.external_attr>>16)
                    if any(part.endswith('.data') for part in rel.parts):outside.append(member.filename);continue
                    target=destination/member.filename
                    if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(member));wheel_files+=1
                meta=archive.read(next(n for n in archive.namelist() if n.endswith('/METADATA')))
                assert hashlib.sha256(meta).hexdigest()==row['metadata_sha256']
        profile=dict(profile='separation-candidate',python='3.13.16',device='cpu',status='built-pending-tests',production_default=False,release_eligible=False,
            lock_sha256=sha(lock_path),bootstrap_sha256={row['name']:row['sha256'] for row in plan['bootstrap']})
        (PROFILE/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
        report.update(completed=True,copied_packages=22,installed_wheels=10,total_packages=32,copied_payload_files=len(items),copied_payload_bytes=copied,
            wheel_payload_files=wheel_files,skipped_outside_entrypoints=outside,downloaded_bytes=sum(row['bytes'] for row in report['archives']))
    except BaseException as error:report['error']=repr(error);raise
    finally:
        (OUT/'2026-10-16-separation-candidate-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
