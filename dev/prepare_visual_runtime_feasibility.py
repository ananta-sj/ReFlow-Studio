"""Official metadata-only visual runtime feasibility; never download archives."""
from html.parser import HTMLParser
import json,sys,urllib.request
from pathlib import Path
from urllib.parse import urljoin,urlsplit,unquote
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from inspect_desktop_dependency_projection import TAGS
from packaging.utils import parse_wheel_filename
from packaging.version import Version
from packaging.requirements import Requirement
from email.parser import Parser

class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.urls.extend(value for name,value in attrs if name=='href')

def main():
    out=ROOT/'docs/validation';requests=[]
    def fetch(url):
        parsed=urlsplit(url)
        assert parsed.scheme=='https' and parsed.hostname in {'pypi.org','download.pytorch.org','download-r2.pytorch.org','files.pythonhosted.org'}
        assert parsed.path.endswith('/json') or parsed.path.endswith('.metadata') or parsed.path.endswith('/torchvision/')
        with urllib.request.urlopen(url,timeout=25) as response:
            assert urlsplit(response.url).hostname in {'pypi.org','download.pytorch.org','download-r2.pytorch.org','files.pythonhosted.org'}
            payload=response.read(8_000_001)
        assert len(payload)<=8_000_000;requests.append(url);return payload
    packages=[]
    for name,version in [('gfpgan','1.3.8'),('basicsr','1.4.2'),('facexlib','0.3.0'),('filterpy','1.4.5')]:
        url=f'https://pypi.org/pypi/{name}/{version}/json';content=fetch(url);data=json.loads(content)
        (out/f'2026-10-16-visual-{name}-release.json').write_bytes(content)
        wheels=[];sources=[]
        for row in data['urls']:
            if row.get('yanked'):continue
            artifact=dict(filename=row['filename'],url=row['url'],bytes=row['size'],sha256=row['digests']['sha256'])
            if row['packagetype']=='bdist_wheel' and parse_wheel_filename(row['filename'])[3]&set(TAGS):wheels.append(artifact)
            elif row['packagetype']=='sdist':sources.append(artifact)
        packages.append(dict(name=name,version=version,requires_dist=data['info'].get('requires_dist') or [],compatible_wheels=wheels,
            source_archives=sources,source_build_needed=not wheels and bool(sources),requires_python=data['info'].get('requires_python')))
    index='https://download.pytorch.org/whl/cpu/torchvision/';parser=Links();parser.feed(fetch(index).decode());candidates=[]
    for link in parser.urls:
        url=urljoin(index,link).split('#')[0];filename=unquote(urlsplit(url).path.rsplit('/',1)[-1])
        try:name,version,build,tags=parse_wheel_filename(filename)
        except ValueError:continue
        if name=='torchvision' and not version.is_prerelease and tags&set(TAGS):candidates.append((version,url,filename))
    selected=None;checked=[]
    for version,url,filename in sorted(candidates,reverse=True)[:12]:
        content=fetch(url+'.metadata');header=Parser().parsestr(content.decode('utf-8'))
        torch_requirements=[Requirement(raw) for raw in header.get_all('Requires-Dist',[]) if Requirement(raw).name=='torch']
        matched=bool(torch_requirements) and all('2.14.1+cpu' in req.specifier for req in torch_requirements)
        checked.append(dict(filename=filename,torch_requirements=[str(req) for req in torch_requirements],matches_existing_torch=matched))
        if matched:
            selected=dict(version=str(version),filename=filename,url=url,requires_dist=header.get_all('Requires-Dist',[]))
            (out/'2026-10-16-visual-torchvision.metadata').write_bytes(content);break
    report=dict(metadata_only=True,packages_installed=False,package_archives_downloaded=False,models_downloaded=False,ready_to_install=False,
        source_builds_authorized=False,target_python='3.13.16',existing_torch='2.14.1+cpu',packages=packages,
        compatible_cpu_torchvision=selected,torchvision_candidates_checked=checked,requests=requests,release_ready=False,
        unresolved=['Exact transitive lock and advisory review are not complete.','Source-only helpers require separate approval before download/build.',
            'BasicSR/GFPGAN inference compatibility must be tested without altering existing installed packages.',
            'Training-oriented tb-nightly dependencies must remain accounted for; do not silently substitute a different distribution.'])
    (out/'2026-10-16-visual-runtime-feasibility.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
