"""Independent metadata/resolver consistency and point-in-time advisory check."""
from datetime import datetime,timezone
import json,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from core.runtime_integrity import sha
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name,parse_wheel_filename
from inspect_desktop_dependency_projection import ENV,TAGS

def main():
    out=ROOT/'docs/validation';prefix='2026-10-16-visual-runtime'
    plan_path=out/(prefix+'-proposal.json');plan=json.loads(plan_path.read_text())
    receipt=json.loads((out/(prefix+'-resolution-receipt.json')).read_text());assert receipt['resolution_verified'] and receipt['proposal_sha256']==sha(plan_path)
    resolved={canonicalize_name(row['metadata']['name']):row for row in json.loads((out/(prefix+'-resolution-report.json')).read_text())['install']}
    original={row['name']:row for row in json.loads((out/'2026-10-13-xtts-security-cpu-lock-review.json').read_text())['packages']}
    selected={row['name']:row for row in plan['packages']};assert selected.keys()==resolved.keys();edges=0
    for name,row in selected.items():
        actual=resolved[name];assert actual['metadata']['version']==row['version']
        if row['source']=='copy-existing':
            path=ROOT/row['source_metadata'];assert sha(path)==row['metadata_sha256'] and sha(path.parent/'RECORD')==row['record_sha256']
            assert original[name]['version']==row['version'];expected=original[name]['sha256']
        else:
            assert sha(ROOT/row['metadata_file'])==row['metadata_sha256'];expected=row['sha256']
            assert parse_wheel_filename(row['filename'])[3]&set(TAGS)
        assert actual['download_info']['archive_info']['hashes']['sha256']==expected,name
        for raw in actual['metadata'].get('requires_dist',[]):
            req=Requirement(raw);assert not req.url
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|set(row['requested_extras'])):continue
            dep=canonicalize_name(req.name);assert dep in selected and selected[dep]['version'] in req.specifier;edges+=1
    advisory=dict(source='https://api.osv.dev/v1/querybatch',checked_at=datetime.now(timezone.utc).isoformat(),complete=False,security_certification=False)
    queries=[dict(package=dict(name=name,ecosystem='PyPI'),version=row['version'].split('+')[0]) for name,row in selected.items()]
    try:
        request=urllib.request.Request(advisory['source'],data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=45) as response:payload=response.read(5_000_001)
        assert len(payload)<=5_000_000
        results=json.loads(payload)['results'];assert len(results)==len(queries) and all(not row.get('next_page_token') for row in results)
        matches=[dict(package=q['package']['name'],version=q['version'],vulns=row['vulns']) for q,row in zip(queries,results) if row.get('vulns')]
        advisory.update(complete=True,packages=len(queries),matches=matches,match_count=sum(len(row['vulns']) for row in matches))
    except Exception as error:advisory['error']=repr(error)
    (out/(prefix+'-advisories.json')).write_text(json.dumps(advisory,indent=2),encoding='utf-8')
    report=dict(passed=True,proposal_sha256=sha(plan_path),package_count=len(selected),active_dependency_edges=edges,
        resolver_and_archive_hashes_match=True,existing_metadata_records_preserved=True,
        advisory_complete=advisory['complete'],advisory_matches=advisory.get('match_count'),
        runtime_created=False,packages_installed=False,models_downloaded=False,release_ready=False)
    (out/(prefix+'-independent-review.json')).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
