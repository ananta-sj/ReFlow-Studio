"""Read package metadata for planning only: no pip, downloads or installation."""
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
import requests

ROOT=Path(__file__).resolve().parents[1]
PACKAGES={'coqui-tts':'0.27.5','rvc-python':'0.1.5','fairseq':'0.12.2',
    'numpy':'1.26.4','scipy':'1.15.3','transformers':'4.57.1',
    'torch':'2.9.1','torchaudio':'2.9.1','torchcodec':'0.8.1',
    'omegaconf':'2.0.6','hydra-core':'1.0.7','encodec':'0.1.1'}


def main():
    results=[]
    session=requests.Session()
    for name,version in PACKAGES.items():
        url=f'https://pypi.org/pypi/{name}/{version}/json'
        result=dict(name=name,requested_version=version,source=url)
        try:
            response=session.get(url,timeout=(10,30));response.raise_for_status()
            data=response.json();info=data['info']
            result.update(version=info['version'],requires_python=info.get('requires_python'),
                requires_dist=info.get('requires_dist') or [],
                artifacts=[dict(filename=item['filename'],bytes=item['size'],
                    requires_python=item.get('requires_python'),sha256=item['digests']['sha256'],
                    yanked=item.get('yanked',False)) for item in data['urls']])
        except Exception as error:
            result.update(error_type=type(error).__name__,error=str(error))
        results.append(result)
        print(name,version,'metadata read' if 'artifacts' in result else result['error'],flush=True)
    windows_url='https://www.python.org/downloads/windows/'
    response=session.get(windows_url,timeout=(10,30));response.raise_for_status()
    releases=list(dict.fromkeys(re.findall(r'/downloads/release/(python-[0-9]+)/',response.text)))
    report=dict(schema='reflow.runtime-repair.metadata.v1',requested_date='2026-10-13',
        retrieved_at_utc=datetime.now(timezone.utc).isoformat(),metadata_only=True,
        packages_installed=False,package_archives_downloaded=False,packages=results,
        python_windows_source=windows_url,python_release_ids=releases[:25])
    path=ROOT/'docs/validation/2026-10-13-runtime-repair-metadata.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('REPORT',path,flush=True)


if __name__=='__main__':main()
