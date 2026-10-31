"""Read access/package metadata; never print tokens or accept gated conditions."""
import json
import os
from pathlib import Path
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / 'models/indicf5/evaluation/auth/token').is_file():
    os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')


def main():
    from huggingface_hub import get_token
    token = get_token()
    report = dict(model='ai4bharat/indictrans2-en-indic-1B', token_available=bool(token),
                  gated_conditions_accepted_by_agent=False, model_code_executed=False, packages=[])
    started = time.monotonic()
    try:
        headers = {'Authorization': 'Bearer '+token} if token else {}
        response = requests.get('https://huggingface.co/api/models/'+report['model'], headers=headers, timeout=(10, 30))
        report['metadata_status'] = response.status_code
        response.raise_for_status()
        data = response.json()
        report.update(revision=data['sha'], gated=data.get('gated'), siblings=[row['rfilename'] for row in data['siblings']])
        access = requests.get('https://huggingface.co/'+report['model']+'/resolve/'+data['sha']+'/config.json',
                              headers={**headers, 'Cache-Control': 'no-cache'},
                              params={'access_probe': str(time.time_ns())},
                              timeout=(10, 30), allow_redirects=False)
        report['config_access_status'] = access.status_code
        report['access_error_code'] = access.headers.get('X-Error-Code')
        report['access_error_message'] = access.headers.get('X-Error-Message')
        report['model_access_available'] = access.status_code in (200, 302, 307)
        for package in ('indictranstoolkit', 'indic-nlp-library-itt', 'sentencepiece'):
            response = requests.get('https://pypi.org/pypi/'+package+'/json', timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
            row = dict(package=package, version=data['info']['version'],
                       requires_dist=data['info'].get('requires_dist'), releases=[])
            for version, files in data['releases'].items():
                if package == 'indictranstoolkit' or version == data['info']['version']:
                    row['releases'].append(dict(version=version, files=[dict(filename=f['filename'],
                        url=f['url'], bytes=f['size'], sha256=f['digests']['sha256']) for f in files]))
            report['packages'].append(row)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-access-packages.json'
        receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(dict(receipt=str(receipt), model_access_available=report.get('model_access_available'),
                             revision=report.get('revision'), error_type=report.get('error_type'))), flush=True)


if __name__ == '__main__':
    main()
