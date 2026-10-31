"""Collect notices, verify installed SentencePiece, remove only owned staging."""
import base64
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.runtime_integrity import sha,safe_path


def main():
    profile=ROOT/'runtime_profiles/translation-candidate'
    assert (profile/'.owner').read_text()=='reflow.translation.candidate.2026-10-16'
    site=profile/'Lib/site-packages';out=ROOT/'docs/validation'
    plan=json.loads((out/'2026-10-16-m2m100-runtime-proposal.json').read_text())
    from email.parser import Parser
    metadata={}
    for path in site.glob('*.dist-info/METADATA'):
        headers=Parser().parsestr(path.read_text(encoding='utf-8'))
        metadata[headers['Name'].lower().replace('_','-').replace('.','-')]=path
    notices=out/'2026-10-16-translation-candidate-notices';inventory=[];sp_checked=0
    for row in plan['packages']:
        path=metadata[row['name']]
        assert sha(path)==row['metadata_sha256']
        if row['name']!='sentencepiece':assert sha(path.parent/'RECORD')==row['record_sha256']
        files=[]
        for name,checksum,size in csv.reader((path.parent/'RECORD').read_text(encoding='utf-8').splitlines()):
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts:continue
            if row['name']=='sentencepiece' and checksum:
                payload=(site/name).read_bytes()
                actual=base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=')
                assert checksum=='sha256='+actual and len(payload)==int(size),name
                sp_checked+=1
            if any(word in relative.name.lower() for word in ('license','licence','notice','copying')):
                source=safe_path(site/name)
                target=notices/row['name']/name
                assert target.resolve().is_relative_to(notices.resolve())
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                files.append(name)
        inventory.append(dict(name=row['name'],version=row['version'],notice_files=files))
    notices.mkdir(exist_ok=True)
    (notices/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    staging=(ROOT/'temp/translation-candidate-2026-10-16-staging').resolve()
    assert staging.is_relative_to((ROOT/'temp').resolve())
    if staging.exists():
        assert safe_path(staging)==staging and (staging/'.owner').read_text()=='reflow.translation.candidate.2026-10-16'
        expected={'.owner','sentencepiece-0.2.2-cp313-cp313-win_amd64.whl'}
        assert {path.name for path in staging.iterdir()}==expected
        size=0
        for path in staging.iterdir():
            safe_path(path);assert path.is_file()
            size+=path.stat().st_size
        for name in expected:(staging/name).unlink()
        staging.rmdir()
    else:
        previous=json.loads((out/'2026-10-16-translation-candidate-closeout.json').read_text())
        assert previous['owned_staging_removed']
        size=previous['staging_bytes_removed']
    report=dict(passed=True,package_metadata_verified=41,sentencepiece_payload_files_verified=sp_checked,
                original_copied_records_verified=40,notice_packages_with_files=sum(bool(row['notice_files']) for row in inventory),
                notice_packages_without_files=[row['name'] for row in inventory if not row['notice_files']],
                owned_staging_removed=True,staging_bytes_removed=size,models_removed=False,
                release_ready=False,distribution_rights_cleared=False)
    (out/'2026-10-16-translation-candidate-closeout.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
