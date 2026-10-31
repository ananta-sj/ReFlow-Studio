"""Project exact visual dependencies from existing payloads and official metadata."""
import csv,hashlib,importlib.metadata as metadata,json,sys,urllib.request,zipfile
from email.parser import Parser
from pathlib import Path
from urllib.parse import urlsplit,unquote
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from inspect_desktop_dependency_projection import ENV,TAGS,artifact,metadata as release
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version,InvalidVersion
from core.runtime_integrity import sha
from prepare_visual_runtime_feasibility import Links
OUT=ROOT/'docs/validation';PREFIX='2026-10-16-visual-runtime'

def main():
    sites=[ROOT/'runtime_profiles'/name/'Lib/site-packages' for name in ['xtts-security-candidate','desktop-candidate','separation-candidate']]
    available={};headers={};requests=[];chosen={}
    for site in sites:
        for dist in metadata.distributions(path=[str(site)]):
            if not dist.metadata.get('Name'):continue
            name=canonicalize_name(dist.metadata['Name'])
            if name in available:continue
            record=Path(dist._path)/'RECORD'
            size=sum(int(size) for filename,digest,size in csv.reader(record.read_text(encoding='utf-8').splitlines()) if size and not Path(filename).is_absolute() and '..' not in Path(filename).parts and Path(filename).suffix not in {'.pyc','.pyo'})
            available[name]=(dict(name=name,version=dist.version,source='copy-existing',metadata_sha256=sha(Path(dist._path)/'METADATA'),record_sha256=sha(record),estimated_payload_bytes=size,source_metadata=str((Path(dist._path)/'METADATA').relative_to(ROOT))),dist.metadata)
    def fetch(url,head=False):
        parsed=urlsplit(url);assert parsed.scheme=='https' and parsed.hostname in {'pypi.org','files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
        assert head or parsed.path.endswith('.metadata') or parsed.path.endswith('/torchvision/')
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD' if head else 'GET'),timeout=25) as response:
            assert urlsplit(response.url).hostname in {'pypi.org','files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org'}
            value=dict(response.headers) if head else response.read(8_000_001)
        if not head:assert len(value)<=8_000_000
        requests.append(dict(url=url,method='HEAD' if head else 'GET'));return value
    helpers=json.loads((OUT/'2026-10-16-visual-helpers/build-receipt.json').read_text());assert helpers['passed']
    for row in helpers['packages']:
        wheel=ROOT/row['wheel'];assert sha(wheel)==row['wheel_sha256']
        with zipfile.ZipFile(wheel) as archive:content=archive.read(next(n for n in archive.namelist() if n.endswith('/METADATA')))
        header=Parser().parsestr(content.decode());name=row['name']
        chosen[name]=(dict(name=name,version=row['version'],source='approved-built-wheel',filename=wheel.name,local_wheel=row['wheel'],sha256=row['wheel_sha256'],archive_bytes=row['wheel_bytes']),header,content)
    feasibility=json.loads((OUT/'2026-10-16-visual-runtime-feasibility.json').read_text())
    tv=feasibility['compatible_cpu_torchvision'];parser=Links();parser.feed(fetch('https://download.pytorch.org/whl/cpu/torchvision/').decode())
    link=next(link for link in parser.urls if unquote(urlsplit(link).path).endswith('/'+tv['filename']))
    digest=urlsplit(link).fragment.removeprefix('sha256=');assert len(digest)==64
    size_headers=fetch(tv['url'],True);size=int(next(v for k,v in size_headers.items() if k.lower()=='content-length'))
    content=fetch(tv['url']+'.metadata');header=Parser().parsestr(content.decode())
    chosen['torchvision']=(dict(name='torchvision',version=tv['version'],source='published-wheel-pending-approval',filename=tv['filename'],url=tv['url'],sha256=digest,archive_bytes=size),header,content)
    roots={'gfpgan':'1.3.8','facexlib':'0.3.0','basicsr':'1.4.2','filterpy':'1.4.5','torch':'2.14.1+cpu','torchvision':tv['version'],'psutil':available['psutil'][0]['version']}
    def select(name,constraints):
        spec=SpecifierSet(','.join(str(req.specifier) for req in constraints))
        if name in chosen:
            row,header,content=chosen[name];assert row['version'] in spec,(name,spec);return row,header
        if name in available and available[name][0]['version'] in spec:return available[name]
        data=release(name);versions=[data['info']['version']]
        # tb-nightly intentionally publishes prerelease builds; other new selections prefer stable releases.
        for raw in data['releases']:
            try:version=Version(raw)
            except InvalidVersion:continue
            if (not version.is_prerelease or name=='tb-nightly') and version in spec:versions.append(raw)
        versions=sorted(set(versions),key=Version,reverse=True)
        for version in versions:
            if version not in spec:continue
            data=release(name,version);file=artifact(data)
            if file:
                content=fetch(file['url']+'.metadata');header=Parser().parsestr(content.decode())
                assert canonicalize_name(header['Name'])==name and header['Version']==version
                row=dict(name=name,version=version,source='published-wheel-pending-approval',filename=file['filename'],url=file['url'],sha256=file['digests']['sha256'],archive_bytes=file['size'])
                chosen[name]=(row,header,content);return row,header
        raise ValueError('No compatible wheel for '+name+' '+str(spec))
    constraints={name:[Requirement(name+'=='+version)] for name,version in roots.items()};extras={};selected={}
    for iteration in range(30):
        selected={name:select(name,reqs) for name,reqs in constraints.items()}
        following={name:[Requirement(name+'=='+version)] for name,version in roots.items()};new_extras={}
        for name,(row,header) in selected.items():
            assert not header.get('Requires-Python') or '3.13.16' in SpecifierSet(header['Requires-Python']),name
            for raw in header.get_all('Requires-Dist',[]):
                req=Requirement(raw);assert not req.url
                if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|extras.get(name,set())):continue
                dep=canonicalize_name(req.name);following.setdefault(dep,[]).append(req);new_extras.setdefault(dep,set()).update(req.extras)
        if following==constraints and new_extras==extras:break
        constraints,extras=following,new_extras
    else:raise ValueError('Closure did not converge')
    edges=[];packages=[]
    for name,(row,header) in sorted(selected.items()):
        row=dict(row);row.update(requires_dist=header.get_all('Requires-Dist',[]),requested_extras=sorted(extras.get(name,set())),requires_python=header.get('Requires-Python'))
        if name in chosen:
            content=chosen[name][2];path=OUT/(PREFIX+'-'+name+'.metadata');path.write_bytes(content);row.update(metadata_file=str(path.relative_to(ROOT)),metadata_sha256=sha(path))
        for raw in row['requires_dist']:
            req=Requirement(raw)
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|set(row['requested_extras'])):continue
            dep=canonicalize_name(req.name);assert selected[dep][0]['version'] in req.specifier
            edges.append(dict(parent=name,requirement=raw,dependency=dep))
        packages.append(row)
    bootstrap_root=sites[0].parents[1]
    bootstrap=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bootstrap_root.iterdir()) if p.is_file() and (p.suffix in {'.exe','.dll','.pyd','.zip','._pth'} or p.name=='LICENSE.txt')]
    report=dict(schema='reflow.visual.runtime-plan.v1',roots=roots,packages=packages,package_count=len(packages),dependency_edges=edges,target_environment=ENV,bootstrap=bootstrap,
        copied_package_count=sum(row['source']=='copy-existing' for row in packages),built_helper_count=2,
        pending_download_count=sum(row['source']=='published-wheel-pending-approval' for row in packages),pending_download_bytes=sum(row.get('archive_bytes',0) for row in packages if row['source']=='published-wheel-pending-approval'),
        copied_payload_estimate_bytes=sum(row.get('estimated_payload_bytes',0) for row in packages),bootstrap_bytes=sum(row['bytes'] for row in bootstrap),
        metadata_closure_satisfied=True,pip_resolver_verified=False,proposed_profile='runtime_profiles/visual-candidate',metadata_requests=requests,
        runtime_created=False,models_downloaded=False,packages_installed=False,installation_approval_required=True,ready_to_install=False,release_ready=False,
        limitations=['Real modern GFPGAN/TorchVision compatibility remains untested.','BasicSR removed functional_tensor import requires reviewed adaptation.','Package/model redistribution decisions remain open.'])
    (OUT/(PREFIX+'-proposal.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'packages','dependency_edges','bootstrap','metadata_requests'}},indent=2))
if __name__=='__main__':main()
