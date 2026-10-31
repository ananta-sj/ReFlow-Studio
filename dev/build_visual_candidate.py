"""Build the explicitly approved 55-package CPU visual candidate."""
import base64,csv,hashlib,json,shutil,stat,sys,zipfile,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from core.runtime_integrity import sha,safe_path
from build_translation_candidate import ArtifactsOnly
OUT=ROOT/'docs/validation';SOURCE=ROOT/'runtime_profiles/xtts-security-candidate'
PROFILE=ROOT/'runtime_profiles/visual-candidate';STAGE=ROOT/'temp/visual-candidate-2026-10-16-staging'
OWNER='reflow.visual.candidate.2026-10-16'

def main():
    from core.xtts_runtime import validate
    lock_path=OUT/'2026-10-16-visual-runtime-lock-review.json';plan=json.loads(lock_path.read_text())
    prepared=json.loads((OUT/'2026-10-16-visual-helpers-acceptance.json').read_text())
    assert prepared['passed'] and sha(lock_path)==prepared['lock_sha256']
    assert validate()['identity']==prepared['runtime_identities']['xtts'] and plan['package_count']==55
    if PROFILE.exists() or STAGE.exists():
        assert '--resume-owned' in sys.argv and safe_path(PROFILE).parent==ROOT/'runtime_profiles' and safe_path(STAGE).parent==ROOT/'temp'
        assert (PROFILE/'.owner').read_text()==OWNER and (STAGE/'.owner').read_text()==OWNER
    else:
        STAGE.mkdir();(STAGE/'.owner').write_text(OWNER)
        PROFILE.mkdir();(PROFILE/'.owner').write_text(OWNER)
    safe_path(PROFILE.parent);safe_path(STAGE.parent)
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
                    parsed=urlsplit(row['url']);assert parsed.scheme=='https' and parsed.hostname in {'files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
                    if (STAGE/row['filename']).exists():data=(STAGE/row['filename']).read_bytes()
                    else:
                        with urllib.request.build_opener(ArtifactsOnly()).open(row['url'],timeout=45) as response:data=response.read(row['archive_bytes']+1)
                    assert len(data)==row['archive_bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
                    path=STAGE/row['filename'];path.write_bytes(data)
                    report['archives'].append(dict(name=row['name'],bytes=len(data),sha256=row['sha256']))
                assert sha(path)==row['sha256'];wheels.append((row,path))
        for row in plan['bootstrap']:
            assert sha(SOURCE/row['name'])==row['sha256'];shutil.copy2(SOURCE/row['name'],PROFILE/row['name'])
            assert sha(PROFILE/row['name'])==row['sha256']
        destination=PROFILE/'Lib/site-packages';destination.mkdir(parents=True,exist_ok=True)
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
                        normalized=PurePosixPath(name.replace('\\','/'))
                        assert not normalized.is_absolute() and '..' not in normalized.parts and ':' not in name
                        data=archive.read(normalized.as_posix());assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=') and len(data)==int(size)
                for member in archive.infolist():
                    rel=PurePosixPath(member.filename)
                    assert not rel.is_absolute() and '..' not in rel.parts and '\\' not in member.filename and ':' not in member.filename
                    assert not stat.S_ISLNK(member.external_attr>>16)
                    if any(part.endswith('.data') for part in rel.parts):outside.append(member.filename);continue
                    target=destination/member.filename
                    if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    if target.exists():assert target.read_bytes()==archive.read(member)
                    else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(member))
                    wheel_files+=1
                meta=archive.read(next(n for n in archive.namelist() if n.endswith('/METADATA')))
                assert hashlib.sha256(meta).hexdigest()==row['metadata_sha256']
        profile=dict(profile='visual-candidate',python='3.13.16',device='cpu',status='built-pending-tests',production_default=False,release_eligible=False,
            lock_sha256=sha(lock_path),bootstrap_sha256={row['name']:row['sha256'] for row in plan['bootstrap']})
        (PROFILE/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
        report.update(completed=True,copied_packages=41,installed_wheels=14,total_packages=55,copied_payload_files=len(items),copied_payload_bytes=copied,
            wheel_payload_files=wheel_files,skipped_outside_entrypoints=outside,downloaded_bytes=sum(row['bytes'] for row in report['archives']))
    except BaseException as error:report['error']=repr(error);raise
    finally:
        (OUT/'2026-10-16-visual-candidate-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
