"""Build only the approved copied-package translation candidate and one wheel."""
import base64
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import urllib.request
from urllib.parse import urlsplit
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.runtime_integrity import sha, safe_path

OUT=ROOT/'docs/validation'
PROFILE=ROOT/'runtime_profiles/translation-candidate'
SOURCE=ROOT/'runtime_profiles/xtts-security-candidate'
STAGING=ROOT/'temp/translation-candidate-2026-10-16-staging'
OWNER='reflow.translation.candidate.2026-10-16'


class ArtifactsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,url):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname!='files.pythonhosted.org':
            raise RuntimeError('Unapproved artifact redirect')
        return super().redirect_request(request,fp,code,msg,headers,url)


def main():
    from core.xtts_runtime import validate
    from email.parser import Parser
    plan_path=OUT/'2026-10-16-m2m100-runtime-proposal.json'
    plan=json.loads(plan_path.read_text())
    reviewed=json.loads((OUT/'2026-10-16-m2m100-runtime-independent-review.json').read_text())
    assert reviewed['metadata_checks_passed'] and reviewed['proposal_sha256']==sha(plan_path)
    assert validate()['identity']==plan['source_runtime_identity']
    assert plan['package_count']==41 and plan['reused_package_count']==40 and plan['new_package_count']==1
    assert not PROFILE.exists(), 'Preserve any existing candidate; no automatic replacement'
    assert not STAGING.exists(), 'Preserve any earlier staging'
    site=SOURCE/'Lib/site-packages'
    metadata={}
    for path in site.glob('*.dist-info/METADATA'):
        headers=Parser().parsestr(path.read_text(encoding='utf-8'))
        name=headers['Name'].lower().replace('_','-').replace('.','-')
        metadata[name]=path
    items={};outside=[]
    for row in plan['packages']:
        if row['name']=='sentencepiece':continue
        path=metadata[row['name']];record=path.parent/'RECORD'
        assert sha(path)==row['metadata_sha256'] and sha(record)==row['record_sha256']
        for name,checksum,size in csv.reader(record.read_text(encoding='utf-8').splitlines()):
            relative=PurePosixPath(name)
            if '\\' in name or relative.is_absolute() or '..' in relative.parts:
                outside.append(name);continue
            if relative.suffix in ('.pyc','.pyo'):continue
            if checksum and not checksum.startswith('sha256='):raise RuntimeError('Unsupported RECORD digest: '+name)
            if name in items and items[name]!=(checksum,size):raise RuntimeError('Conflicting package file: '+name)
            items[name]=(checksum,size)
    # Check each source directory once; validate individual entries without
    # repeatedly restatting every ancestor for all 13,000+ package files.
    checked=set()
    for name in items:
        parent=(site/name).parent
        if parent not in checked:
            safe_path(parent);checked.add(parent)
        info=(site/name).lstat()
        assert not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400
    wheel=next(row for row in plan['packages'] if row['name']=='sentencepiece')
    assert wheel['version']=='0.2.2' and wheel['filename']=='sentencepiece-0.2.2-cp313-cp313-win_amd64.whl'
    parsed=urlsplit(wheel['url'])
    assert parsed.scheme=='https' and parsed.hostname=='files.pythonhosted.org'
    STAGING.mkdir();(STAGING/'.owner').write_text(OWNER)
    archive_path=STAGING/wheel['filename']
    opener=urllib.request.build_opener(ArtifactsOnly())
    with opener.open(wheel['url'],timeout=45) as response:
        assert urlsplit(response.url).hostname=='files.pythonhosted.org'
        payload=response.read(wheel['archive_bytes']+1)
    assert len(payload)==wheel['archive_bytes'] and hashlib.sha256(payload).hexdigest()==wheel['sha256']
    archive_path.write_bytes(payload)
    PROFILE.mkdir();(PROFILE/'.owner').write_text(OWNER)
    report=dict(completed=False,authorization='User approved separate runtime and tests',
                defaults_changed=False,models_downloaded=False,source_runtime_modified=False,
                proposal_sha256=sha(plan_path),new_archive_bytes=len(payload),new_archive_sha256=sha(archive_path))
    try:
        for row in plan['bootstrap']:
            source=SOURCE/row['name']
            assert sha(source)==row['sha256']
            shutil.copy2(source,PROFILE/row['name'])
            assert sha(PROFILE/row['name'])==row['sha256']
        destination=PROFILE/'Lib/site-packages';destination.mkdir(parents=True)
        def copy(item):
            name,(checksum,size)=item
            source=site/name;target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            value=hashlib.sha256(target.read_bytes()).digest()
            if checksum:
                assert checksum=='sha256='+base64.urlsafe_b64encode(value).decode().rstrip('='),name
            if size:assert target.stat().st_size==int(size),name
            return target.stat().st_size
        copied=0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for offset in range(0,len(items),64):
                copied+=sum(pool.map(copy,list(items.items())[offset:offset+64]))
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                relative=PurePosixPath(member.filename)
                assert not relative.is_absolute() and '..' not in relative.parts and '\\' not in member.filename
                assert not stat.S_ISLNK(member.external_attr>>16) and '.data' not in relative.parts
                target=destination/member.filename
                assert target.resolve().is_relative_to(destination.resolve())
                if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                assert not target.exists(),'Wheel collides with copied file: '+member.filename
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(member))
            meta=archive.read('sentencepiece-0.2.2.dist-info/METADATA')
            assert hashlib.sha256(meta).hexdigest()==wheel['metadata_sha256']
        profile=dict(profile='translation-candidate',status='built-pending-tests',python='3.13.16',device='cpu',
                     production_default=False,release_eligible=False,proposal_sha256=sha(plan_path),
                     bootstrap_sha256={row['name']:row['sha256'] for row in plan['bootstrap']},
                     packages={row['name']:row['version'] for row in plan['packages']})
        (PROFILE/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
        report.update(completed=True,copied_packages=40,total_packages=41,copied_payload_files=len(items),
                      copied_payload_bytes=copied,skipped_outside_entrypoints=outside,
                      bootstrap_bytes=plan['bootstrap_bytes'])
    except BaseException as error:
        report['error']=repr(error)
        raise
    finally:
        (OUT/'2026-10-16-translation-candidate-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
