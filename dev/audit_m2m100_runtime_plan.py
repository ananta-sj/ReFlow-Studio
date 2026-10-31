"""Public advisory and independent metadata checks; no runtime installation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name,parse_wheel_filename
from packaging.specifiers import SpecifierSet
from inspect_desktop_dependency_projection import ENV,TAGS


def main():
    from core.xtts_runtime import validate
    from core.runtime_integrity import sha
    out=ROOT/'docs/validation';prefix='2026-10-16-m2m100-runtime'
    plan_path=out/(prefix+'-proposal.json');plan=json.loads(plan_path.read_text())
    assert plan['metadata_only'] and not plan['packages_installed'] and not plan['package_archives_downloaded']
    assert validate()['identity']==plan['source_runtime_identity']
    selected={row['name']:row for row in plan['packages']}
    assert len(selected)==plan['package_count']==41
    site=ROOT/'runtime_profiles/xtts-security-candidate/Lib/site-packages'
    from email.parser import Parser
    metadata={}
    for path in site.glob('*.dist-info/METADATA'):
        header=Parser().parsestr(path.read_text(encoding='utf-8'))
        metadata[canonicalize_name(header['Name'])]=(path,header)
    for name,row in selected.items():
        if name=='sentencepiece':
            assert parse_wheel_filename(row['filename'])[3]&set(TAGS)
            assert row['filename']=='sentencepiece-0.2.2-cp313-cp313-win_amd64.whl'
            assert sha(out/(prefix+'-sentencepiece-wheel.metadata'))==row['metadata_sha256']
            assert urlsplit(row['url']).hostname=='files.pythonhosted.org'
        else:
            path,header=metadata[name]
            assert sha(path)==row['metadata_sha256'] and sha(path.parent/'RECORD')==row['record_sha256']
            assert header['Version']==row['version']
            assert not header.get('Requires-Python') or '3.13.16' in SpecifierSet(header['Requires-Python'])
        for value in row['requires_dist']:
            req=Requirement(value)
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=e)) for e in {''}|set(row.get('requested_extras',[]))):continue
            dependency=canonicalize_name(req.name)
            assert dependency in selected and selected[dependency]['version'] in req.specifier
    queries=[dict(package=dict(name=row['name'],ecosystem='PyPI'),version=row['version'].split('+')[0]) for row in plan['packages']]
    report=dict(source='https://api.osv.dev/v1/querybatch',checked_at=datetime.now(timezone.utc).isoformat(),
                packages=len(queries),complete=False,security_certification=False,packages_installed=False)
    try:
        request=urllib.request.Request(report['source'],data=json.dumps(dict(queries=queries)).encode(),
            headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=45) as response:payload=response.read(5_000_001)
        assert len(payload)<=5_000_000
        data=json.loads(payload);assert len(data['results'])==len(queries)
        assert all(isinstance(row,dict) and not row.get('next_page_token') for row in data['results']), 'Incomplete paginated advisory response'
        matches=[dict(package=query['package']['name'],version=query['version'],vulns=result['vulns'])
                 for query,result in zip(queries,data['results']) if result.get('vulns')]
        report.update(complete=True,matches=matches,match_count=sum(len(row['vulns']) for row in matches))
    except Exception as error:
        report['error']=repr(error)
    (out/(prefix+'-advisories.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    states=json.loads((out/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in states.items())
    assert not (ROOT/'runtime_profiles/translation-candidate').exists()
    assert not (ROOT/'temp/ollama-eval-c_lslq8w').exists()
    result=dict(metadata_checks_passed=True,proposal_sha256=sha(plan_path),
                installed_metadata_and_record_hashes_unchanged=True,source_runtime_identity_preserved=True,
                protected_state_preserved=True,runtime_created=False,archive_downloaded=False,
                advisory_lookup_complete=report['complete'],advisory_matches=report.get('match_count'),
                approval_required=True,ready_to_install=False)
    (out/(prefix+'-independent-review.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return not report['complete']


if __name__=='__main__':raise SystemExit(main())
