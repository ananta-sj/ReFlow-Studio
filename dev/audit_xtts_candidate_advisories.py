"""Read public OSV advisory matches for the exact candidate; install nothing."""
import json
from pathlib import Path
import urllib.request
import datetime
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prefix',default='xtts-candidate');args=parser.parse_args()
    assert args.prefix.replace('-','').isalnum()
    lock=json.loads((OUT/f'2026-10-13-{args.prefix}-lock-review.json').read_text(encoding='utf-8'))
    queries=[dict(package=dict(name=row['name'],ecosystem='PyPI'),version=row['version'].split('+')[0]) for row in lock['packages']]
    request=urllib.request.Request('https://api.osv.dev/v1/querybatch',
        data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json'},method='POST')
    receipt=dict(source='https://api.osv.dev/v1/querybatch',packages=len(queries),
                 checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),complete=False,
                 scan_is_not_security_certification=True)
    try:
        with urllib.request.urlopen(request,timeout=45) as response:
            data=json.loads(response.read(5000000))
        assert len(data['results'])==len(queries)
        matches=[dict(package=q['package']['name'],version=q['version'],vulns=r['vulns'])
                 for q,r in zip(queries,data['results']) if r.get('vulns')]
        receipt.update(complete=True,matches=matches,match_count=sum(len(r['vulns']) for r in matches))
    except Exception as error:
        receipt['error']=str(error)
    (OUT/f'2026-10-13-{args.prefix}-advisories.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
    return not receipt['complete']

if __name__=='__main__':raise SystemExit(main())
