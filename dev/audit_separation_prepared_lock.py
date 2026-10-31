"""Independent dependency/artifact audit, public advisories and notice supplement."""
from datetime import datetime,timezone
from email.parser import Parser
import json
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name,parse_wheel_filename
from inspect_desktop_dependency_projection import ENV,TAGS
from core.runtime_integrity import sha


def main():
    folder=ROOT/'docs/validation';prefix='2026-10-16-separation-runtime'
    path=folder/(prefix+'-proposal.json');plan=json.loads(path.read_text())
    receipt=json.loads((folder/(prefix+'-resolution-receipt.json')).read_text())
    resolver=json.loads((folder/(prefix+'-resolution-report.json')).read_text(encoding='utf-8'))
    assert receipt['resolution_verified'] and receipt['proposal_sha256']==sha(path)
    selected={row['name']:row for row in plan['packages']}
    resolved={canonicalize_name(row['metadata']['name']):row for row in resolver['install']}
    assert set(selected)==set(resolved) and len(selected)==plan['package_count']
    original={row['name']:row for row in json.loads((folder/'2026-10-13-xtts-security-cpu-lock-review.json').read_text())['packages']}
    edge_count=0
    for name,row in selected.items():
        actual=resolved[name];assert actual['metadata']['version']==row['version']
        expected_hash=original[name]['sha256'] if row['source']=='copy-existing' else row['sha256']
        assert actual['download_info']['archive_info']['hashes']['sha256']==expected_hash,name
        if row['source']=='copy-existing':
            metadata_path=ROOT/row['source_metadata'];assert sha(metadata_path)==row['metadata_sha256']
            assert sha(metadata_path.parent/'RECORD')==row['record_sha256']
        else:assert sha(ROOT/row['metadata_file'])==row['metadata_sha256']
        for raw in actual['metadata'].get('requires_dist',[]):
            req=Requirement(raw);assert not req.url
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|set(row['requested_extras'])):continue
            dep=canonicalize_name(req.name);assert dep in selected and selected[dep]['version'] in req.specifier
            edge_count+=1
        if row['source']!='copy-existing':assert parse_wheel_filename(row['filename'])[3]&set(TAGS)
    advisories=dict(source='https://api.osv.dev/v1/querybatch',checked_at=datetime.now(timezone.utc).isoformat(),complete=False,security_certification=False)
    queries=[dict(package=dict(name=name,ecosystem='PyPI'),version=row['version'].split('+')[0]) for name,row in selected.items()]
    try:
        request=urllib.request.Request(advisories['source'],data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=45) as response:payload=response.read(5_000_001)
        assert len(payload)<=5_000_000
        results=json.loads(payload)['results'];assert len(results)==len(queries)
        assert all(not row.get('next_page_token') for row in results)
        matches=[dict(package=q['package']['name'],version=q['version'],vulns=row['vulns']) for q,row in zip(queries,results) if row.get('vulns')]
        advisories.update(complete=True,packages=len(queries),matches=matches,match_count=sum(len(row['vulns']) for row in matches))
    except Exception as error:advisories['error']=repr(error)
    (folder/(prefix+'-advisories.json')).write_text(json.dumps(advisories,indent=2),encoding='utf-8')
    url='https://raw.githubusercontent.com/antlr/antlr4/4.9.3/LICENSE.txt'
    with urllib.request.urlopen(url,timeout=25) as response:notice=response.read(50_001)
    assert len(notice)<=50_000 and b'Redistribution' in notice and b'The ANTLR Project' in notice
    target=folder/'2026-10-16-separation-helpers/antlr4-python3-runtime/LICENSE.upstream-4.9.3.txt';target.write_bytes(notice)
    supplement=dict(url=url,file=str(target.relative_to(ROOT)),sha256=sha(target),bytes=len(notice),
        origin='upstream release tag; missing from approved source archive and built wheel',wheel_modified=False,distribution_rights_cleared=False)
    (folder/'2026-10-16-separation-antlr-notice.json').write_text(json.dumps(supplement,indent=2),encoding='utf-8')
    audit=dict(passed=True,proposal_sha256=sha(path),package_count=len(selected),active_dependency_edges=edge_count,
        resolver_and_artifact_hashes_match=True,existing_metadata_and_records_preserved=True,
        advisory_complete=advisories['complete'],advisory_matches=advisories.get('match_count'),
        packages_installed=False,runtime_created=False,models_downloaded=False,release_ready=False,
        antlr_notice_supplement=supplement)
    (folder/(prefix+'-independent-review.json')).write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
