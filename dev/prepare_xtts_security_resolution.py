"""Prepare revised roots and official index hashes using metadata only."""
import json
from pathlib import Path
import re
from urllib.parse import unquote,urljoin,urlsplit
import urllib.request
from packaging.tags import cpython_tags,compatible_tags
from packaging.utils import parse_wheel_filename

OUT=Path(__file__).resolve().parents[1]/'docs/validation'

def main():
    tags=set(cpython_tags((3,13),abis=['cp313'],platforms=['win_amd64']))
    tags.update(compatible_tags((3,13),interpreter='cp313',platforms=['win_amd64']))
    plan=json.loads((OUT/'2026-10-13-runtime-repair-plan.json').read_text(encoding='utf-8'))
    latest=json.loads((OUT/'2026-10-13-xtts-security-replacement-metadata.json').read_text(encoding='utf-8'))
    versions={r['name']:r['version'] for r in latest['packages']}
    plan['xtts_candidate_roots']=[{k:r[k] for k in ['name','version','why']} for r in plan['xtts_candidate_roots']]
    artifact_checks=[]
    for root in plan['xtts_candidate_roots']:
        name=root['name']
        if name in versions:
            root['version']=versions[name]
            if name in {'torch','torchaudio','torchcodec'}:root['version']+='+cpu'
            if name in {'torch','torchaudio','torchcodec'}:
                source=f'https://download.pytorch.org/whl/cpu/{name}/'
                with urllib.request.urlopen(source,timeout=30) as response:html=response.read(8000000).decode()
                matches=[]
                for url in re.findall(r'href=[\"\x27]([^\"\x27]+)',html):
                    filename=unquote(urlsplit(url).path.rsplit('/',1)[-1])
                    if not filename.endswith('.whl'):continue
                    package,version,build,wheel_tags=parse_wheel_filename(filename)
                    if package==name and str(version)==root['version'] and wheel_tags&tags:
                        matches.append(urljoin(source,url))
                if not matches and name=='torchcodec':
                    metadata=next(r for r in latest['packages'] if r['name']==name)
                    assert len(metadata['compatible_wheels'])==1
                    artifact_checks.append(dict(name=name,version=root['version'],source=metadata['source'],
                        **metadata['compatible_wheels'][0],basis='Official documentation states Windows PyPI wheels are CPU builds; actual decoding still requires verification'))
                    continue
                assert len(matches)==1,(name,matches)
                url=matches[0];digest=urlsplit(url).fragment.removeprefix('sha256=')
                assert len(digest)==64
                artifact_checks.append(dict(name=name,version=root['version'],source=source,url=url.split('#')[0],sha256=digest))
    result=dict(install_authorized=False,runtime_modified=False,model_downloaded=False,
        python=plan['python'],xtts_candidate_roots=plan['xtts_candidate_roots'],official_cpu_artifacts=artifact_checks,
        compatibility_sources=['https://docs.pytorch.org/audio/stable/installation.html','https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions'],
        actual_model_execution_verified=False)
    (OUT/'2026-10-13-xtts-security-plan.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(revised=[(r['name'],r['version']) for r in result['xtts_candidate_roots'] if r['name'] in versions],official_cpu_artifacts=artifact_checks),indent=2))

if __name__=='__main__':main()
