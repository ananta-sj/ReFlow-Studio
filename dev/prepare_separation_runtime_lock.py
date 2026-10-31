"""Exact metadata closure for a future CPU profile; no runtime installation."""
import csv
from email.parser import Parser
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'dev')]
from inspect_desktop_dependency_projection import ENV,TAGS
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name,parse_wheel_filename
from core.runtime_integrity import sha


def main():
    from core.xtts_runtime import validate
    source_runtime=validate()
    out=ROOT/'docs/validation';prefix='2026-10-16-separation-runtime'
    helpers=json.loads((out/'2026-10-16-separation-helpers/build-receipt.json').read_text());assert helpers['passed']
    review=json.loads((out/'2026-10-16-separation-artifact-review.json').read_text())
    site=ROOT/'runtime_profiles/xtts-security-candidate/Lib/site-packages'
    rows={};headers={};requests=[]
    for dist in metadata.distributions(path=[str(site)]):
        name=canonicalize_name(dist.metadata['Name']);assert name not in rows
        records=list(csv.reader((Path(dist._path)/'RECORD').read_text(encoding='utf-8').splitlines()))
        size=sum(int(size) for filename,digest,size in records if size and not Path(filename).is_absolute() and '..' not in Path(filename).parts and Path(filename).suffix not in {'.pyc','.pyo'})
        rows[name]=dict(name=name,version=dist.version,source='copy-existing',metadata_sha256=sha(Path(dist._path)/'METADATA'),
            record_sha256=sha(Path(dist._path)/'RECORD'),estimated_payload_bytes=size,source_metadata=str((Path(dist._path)/'METADATA').relative_to(ROOT)))
        headers[name]=dist.metadata
    for package in review['packages']:
        name=package['name'];assert name not in rows
        if package['source_build_needed']:
            helper=next(row for row in helpers['packages'] if row['name']==name)
            wheel=ROOT/helper['wheel'];assert sha(wheel)==helper['wheel_sha256']
            with zipfile.ZipFile(wheel) as archive:
                content=archive.read(next(n for n in archive.namelist() if n.endswith('/METADATA')))
            artifact=dict(filename=wheel.name,local_wheel=helper['wheel'],sha256=helper['wheel_sha256'],archive_bytes=helper['wheel_bytes'])
            origin='approved-built-wheel'
        else:
            assert len(package['compatible_wheels'])==1
            wheel=package['compatible_wheels'][0];assert parse_wheel_filename(wheel['filename'])[3]&set(TAGS)
            url=wheel['url']+'.metadata';parsed=urlsplit(url)
            assert parsed.hostname=='files.pythonhosted.org' and parsed.scheme=='https'
            with urllib.request.urlopen(url,timeout=25) as response:
                assert urlsplit(response.url).hostname==parsed.hostname
                content=response.read(2_000_001)
            assert len(content)<=2_000_000
            requests.append(url)
            artifact=dict(filename=wheel['filename'],url=wheel['url'],sha256=wheel['sha256'],archive_bytes=wheel['bytes'])
            origin='published-wheel-pending-approval'
        path=out/(prefix+'-'+name+'.metadata');path.write_bytes(content)
        header=Parser().parsestr(content.decode('utf-8'))
        assert canonicalize_name(header['Name'])==name and header['Version']==package['version']
        rows[name]=dict(name=name,version=header['Version'],source=origin,metadata_sha256=hashlib.sha256(content).hexdigest(),
            metadata_file=str(path.relative_to(ROOT)),**artifact)
        headers[name]=header
    # Modern torchaudio.save uses TorchCodec, which is not a declared hard
    # requirement; the real Demucs stem writer needs it as an explicit root.
    roots={'demucs','torch','torchaudio','torchcodec','numpy','soundfile','psutil'}
    selected=set(roots);extras={name:set() for name in rows}
    for _ in range(len(rows)+1):
        before=(set(selected),{name:set(values) for name,values in extras.items()})
        for name in list(selected):
            header=headers[name]
            assert not header.get('Requires-Python') or '3.13.16' in SpecifierSet(header['Requires-Python']),name
            for raw in header.get_all('Requires-Dist',[]):
                req=Requirement(raw);assert not req.url
                if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|extras[name]):continue
                dep=canonicalize_name(req.name)
                assert dep in rows and rows[dep]['version'] in req.specifier,(name,raw,rows.get(dep))
                selected.add(dep);extras[dep].update(req.extras)
        if before==(selected,extras):break
    else:raise ValueError('Dependency closure did not converge')
    edges=[]
    for name in sorted(selected):
        row=rows[name];header=headers[name]
        row.update(requires_dist=header.get_all('Requires-Dist',[]),requested_extras=sorted(extras[name]),requires_python=header.get('Requires-Python'))
        for raw in row['requires_dist']:
            req=Requirement(raw)
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=extra)) for extra in {''}|extras[name]):continue
            edges.append(dict(parent=name,requirement=raw,dependency=canonicalize_name(req.name)))
    packages=[rows[name] for name in sorted(selected)]
    bootstrap=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(site.parents[1].iterdir()) if p.is_file() and (p.suffix in {'.exe','.dll','.pyd','.zip','._pth'} or p.name=='LICENSE.txt')]
    report=dict(schema='reflow.separation.runtime-plan.v1',metadata_closure_satisfied=True,pip_resolver_verified=False,
        source_runtime_identity=source_runtime['identity'],target_environment=ENV,proposed_profile='runtime_profiles/separation-candidate',
        roots=sorted(roots),packages=packages,package_count=len(packages),dependency_edges=edges,bootstrap=bootstrap,
        copied_package_count=sum(row['source']=='copy-existing' for row in packages),built_helper_count=sum(row['source']=='approved-built-wheel' for row in packages),
        pending_download_count=sum(row['source']=='published-wheel-pending-approval' for row in packages),
        pending_download_bytes=sum(row.get('archive_bytes',0) for row in packages if row['source']=='published-wheel-pending-approval'),
        copied_payload_estimate_bytes=sum(row.get('estimated_payload_bytes',0) for row in packages),bootstrap_bytes=sum(row['bytes'] for row in bootstrap),
        metadata_requests=requests,packages_installed=False,models_downloaded=False,runtime_created=False,ready_to_install=False,
        installation_approval_required=True,release_ready=False,
        limitations=['Metadata closure is exact but is not yet a pip resolver acceptance.',
            'Six published wheel archives have not been downloaded or byte-verified.',
            'Real modern Demucs inference, compatibility and separation quality remain untested.',
            'Copied storage estimate excludes unpacked new wheels and entrypoint/RECORD overhead.'])
    (out/(prefix+'-proposal.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['package_count','copied_package_count','built_helper_count','pending_download_count','pending_download_bytes','copied_payload_estimate_bytes','bootstrap_bytes']},indent=2))


if __name__=='__main__':main()
