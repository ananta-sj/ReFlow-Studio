"""Read replacement metadata only; no package or model downloads/installations."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.request
from packaging.specifiers import SpecifierSet
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import parse_wheel_filename

OUT=Path(__file__).resolve().parents[1]/'docs/validation'
TARGET=set(cpython_tags((3,13),abis=['cp313'],platforms=['win_amd64']))
TARGET.update(compatible_tags((3,13),interpreter='cp313',platforms=['win_amd64']))

def fetch(name):
    source=f'https://pypi.org/pypi/{name}/json'
    with urllib.request.urlopen(source,timeout=30) as response:
        payload=response.read(15000001)
    assert len(payload)<=15000000
    data=json.loads(payload); info=data['info']
    wheels=[]
    for row in data['urls']:
        if row['filename'].endswith('.whl') and parse_wheel_filename(row['filename'])[3]&TARGET:
            wheels.append(dict(filename=row['filename'],sha256=row['digests']['sha256'],bytes=row['size'],yanked=row['yanked']))
    return dict(name=name,version=info['version'],source=source,requires_python=info['requires_python'],
        python_compatible=not info['requires_python'] or '3.13.16' in SpecifierSet(info['requires_python']),
        requires_dist=info.get('requires_dist'),compatible_wheels=wheels)

def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(fetch,['torch','torchaudio','torchcodec','transformers','coqui-tts']))
    report=dict(metadata_only=True,runtime_modified=False,model_downloaded=False,packages=rows)
    (OUT/'2026-10-13-xtts-security-replacement-metadata.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for row in rows:print(row['name'],row['version'],'python compatible:',row['python_compatible'],'wheels:',len(row['compatible_wheels']))

if __name__=='__main__':main()
