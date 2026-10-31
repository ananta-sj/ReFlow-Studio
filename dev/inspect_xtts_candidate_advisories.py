"""Retain exact public advisory records and summarize affected surfaces."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.request

OUT=Path(__file__).resolve().parents[1]/'docs/validation'

def fetch(identifier):
    with urllib.request.urlopen('https://api.osv.dev/v1/vulns/'+identifier,timeout=30) as response:
        return json.loads(response.read(3000000))

def main():
    scan=json.loads((OUT/'2026-10-13-xtts-candidate-advisories.json').read_text(encoding='utf-8'))
    identifiers=sorted({v['id'] for row in scan['matches'] for v in row['vulns']})
    with ThreadPoolExecutor(max_workers=5) as pool:
        records=list(pool.map(fetch,identifiers))
    (OUT/'2026-10-13-xtts-candidate-advisory-details.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    for record in records:
        print(record['id'],record.get('summary'),[(p.get('package',{}).get('name'),p.get('ranges')) for p in record.get('affected',[])])

if __name__=='__main__':main()
