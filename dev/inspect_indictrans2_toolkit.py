"""Pin upstream pure-Python toolkit history for Windows feasibility review."""
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    session = requests.Session()
    session.headers['Accept'] = 'application/vnd.github+json'
    base = 'https://api.github.com/repos/VarunGumma/IndicTransToolkit'
    response = session.get(base+'/commits', params={'path':'IndicTransToolkit/processor.py', 'per_page':3}, timeout=(10,30))
    response.raise_for_status()
    commits = response.json()
    directory = ROOT / 'dev/vendor/indictrans2-toolkit-review'
    directory.mkdir(parents=True, exist_ok=True)
    report = dict(executed=False, source_repository='VarunGumma/IndicTransToolkit', history=[])
    for commit in commits:
        revision = commit['sha']
        row = dict(revision=revision, message=commit['commit']['message'].splitlines()[0])
        raw = requests.get('https://raw.githubusercontent.com/VarunGumma/IndicTransToolkit/'+revision+'/IndicTransToolkit/processor.py', timeout=(10,30))
        row['status'] = raw.status_code
        if raw.status_code == 200:
            path = directory / (revision+'-processor.py')
            path.write_bytes(raw.content)
            row.update(path=str(path), sha256=hashlib.sha256(raw.content).hexdigest())
        report['history'].append(row)
    receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-toolkit-review.json'
    receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
