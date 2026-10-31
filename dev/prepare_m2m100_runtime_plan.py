"""Metadata-only M2M100 proposal: no archives, installs or model transfers."""
import csv
from email.parser import Parser
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'dev')]
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from inspect_desktop_dependency_projection import ENV, TAGS

OUT = ROOT/'docs/validation'
PREFIX = '2026-10-16-m2m100-runtime'
SITE = ROOT/'runtime_profiles/xtts-security-candidate/Lib/site-packages'


def main():
    from core.xtts_runtime import validate
    from core.runtime_integrity import sha
    source_runtime = validate()
    requests = []
    def fetch(url):
        parsed = urlsplit(url)
        allowed = parsed.scheme=='https' and not parsed.username and (
            parsed.hostname=='pypi.org' and parsed.path.startswith('/pypi/') and parsed.path.endswith('/json')
            or parsed.hostname=='files.pythonhosted.org' and parsed.path.endswith('.whl.metadata'))
        if not allowed:raise RuntimeError('Non-metadata transfer refused: '+url)
        requests.append(dict(method='GET',url=url))
        with urllib.request.urlopen(url,timeout=25) as response:
            final = urlsplit(response.url)
            if final.hostname!=parsed.hostname or final.scheme!='https':raise RuntimeError('Unexpected metadata redirect')
            value = response.read(8_000_001)
        if len(value)>8_000_000:raise RuntimeError('Metadata size bound exceeded')
        return value
    published = json.loads(fetch('https://pypi.org/pypi/sentencepiece/json'))
    version = published['info']['version']
    if Version(version).is_prerelease:raise RuntimeError('Review a stable SentencePiece release explicitly')
    matches = []
    for item in published['urls']:
        if item['yanked'] or item['packagetype']!='bdist_wheel':continue
        if item.get('requires_python') and '3.13.16' not in SpecifierSet(item['requires_python']):continue
        if parse_wheel_filename(item['filename'])[3] & set(TAGS):matches.append(item)
    if len(matches)!=1:raise RuntimeError('Expected one compatible SentencePiece wheel, found '+str(len(matches)))
    wheel = matches[0]
    artifact_url = urlsplit(wheel['url'])
    assert artifact_url.scheme=='https' and artifact_url.hostname=='files.pythonhosted.org'
    wheel_metadata = fetch(wheel['url']+'.metadata')
    headers = Parser().parsestr(wheel_metadata.decode('utf-8'))
    assert canonicalize_name(headers['Name'])=='sentencepiece' and headers['Version']==version
    (OUT/(PREFIX+'-sentencepiece-release.json')).write_text(json.dumps(published,indent=2),encoding='utf-8')
    (OUT/(PREFIX+'-sentencepiece-wheel.metadata')).write_bytes(wheel_metadata)
    installed = {}
    for dist in metadata.distributions(path=[str(SITE)]):
        name = canonicalize_name(dist.metadata['Name'])
        if name in installed:raise RuntimeError('Duplicate installed metadata: '+name)
        installed[name] = dist
    roots = {'torch','transformers','psutil','requests','sentencepiece'}
    requires = {name: list(dist.requires or []) for name,dist in installed.items()}
    versions = {name: dist.version for name,dist in installed.items()}
    requires['sentencepiece'] = headers.get_all('Requires-Dist', [])
    versions['sentencepiece'] = version
    selected, extras = set(roots), {name:set() for name in versions}
    for _ in range(len(versions)+1):
        before = (set(selected),{name:set(values) for name,values in extras.items()})
        for name in list(selected):
            if name not in requires:raise RuntimeError('Unreviewed dependency is missing: '+name)
            for value in requires[name]:
                req = Requirement(value)
                if req.url:raise RuntimeError('Direct dependency URL not allowed: '+value)
                if req.marker and not any(req.marker.evaluate(dict(ENV,extra=e)) for e in {''}|extras[name]):continue
                dep = canonicalize_name(req.name)
                if dep not in versions or versions[dep] not in req.specifier:raise RuntimeError('Unsatisfied dependency: '+name+' -> '+value)
                selected.add(dep);extras[dep].update(req.extras)
        if before==(selected,extras):break
    else:raise RuntimeError('Dependency closure did not converge')
    edges, rows, copied_files = [], [], set()
    existing_lock = json.loads((OUT/'2026-10-13-xtts-security-cpu-lock-review.json').read_text())
    locked = {item['name']:item for item in existing_lock['packages']}
    for name in sorted(selected):
        for value in requires[name]:
            req=Requirement(value)
            if req.marker and not any(req.marker.evaluate(dict(ENV,extra=e)) for e in {''}|extras[name]):continue
            edges.append(dict(parent=name,requirement=value,dependency=canonicalize_name(req.name),satisfied=True))
        if name=='sentencepiece':
            rows.append(dict(name=name,version=version,source='new approved wheel required',
                filename=wheel['filename'],url=wheel['url'],sha256=wheel['digests']['sha256'],
                archive_bytes=wheel['size'],requires_dist=requires[name],
                license_expression=headers.get('License-Expression'),license=headers.get('License'),
                metadata_sha256=hashlib.sha256(wheel_metadata).hexdigest(),artifact_bytes_verified=False))
            continue
        dist = installed[name]
        record = Path(dist._path)/'RECORD'
        records = list(csv.reader(record.read_text(encoding='utf-8').splitlines()))
        estimated = 0
        for filename,checksum,size in records:
            path = Path(filename)
            if '..' in path.parts or path.is_absolute() or path.suffix in ('.pyc','.pyo'):continue
            if size and filename not in copied_files:
                estimated += int(size);copied_files.add(filename)
        row = locked[name]
        assert row['version']==dist.version
        rows.append(dict(name=name,version=dist.version,source='copy existing verified package',
            requires_dist=requires[name],requested_extras=sorted(extras[name]),
            record_sha256=sha(record),metadata_sha256=sha(Path(dist._path)/'METADATA'),
            estimated_payload_bytes=estimated,original_wheel_sha256=row['sha256'],
            license_expression=dist.metadata.get('License-Expression'),license=dist.metadata.get('License')))
    bootstrap=[]
    for path in sorted(SITE.parents[1].iterdir()):
        if path.is_file() and (path.suffix in {'.exe','.dll','.pyd','.zip','._pth'} or path.name=='LICENSE.txt'):
            bootstrap.append(dict(name=path.name,bytes=path.stat().st_size,sha256=sha(path)))
    assert any(row['name']=='python313._pth' for row in bootstrap)
    result = dict(schema='reflow.m2m100.runtime-proposal.v1',metadata_only=True,packages_installed=False,
        package_archives_downloaded=False,models_downloaded=False,source_runtime_identity=source_runtime['identity'],
        target_environment=ENV,proposed_profile='runtime_profiles/translation-candidate',
        roots={name:versions[name] for name in sorted(roots)},packages=rows,package_count=len(rows),
        reused_package_count=len(rows)-1,new_package_count=1,new_download_bytes=wheel['size'],
        existing_payload_estimate_bytes=sum(row.get('estimated_payload_bytes',0) for row in rows),
        bootstrap=bootstrap,bootstrap_bytes=sum(row['bytes'] for row in bootstrap),
        dependency_edges=edges,metadata_closure_satisfied=True,requests=requests,
        sentencepiece_pypi_advisories=published.get('vulnerabilities',[]),
        security_scope='No full new advisory audit for copied packages; rerun advisory checks before installation',
        ready_to_install=False,approval_required=True,
        preservation='Copy files into a new profile; do not modify XTTS/NLLB/recognition/desktop environments',
        limitations=['Wheel bytes not downloaded or hash verified','Native tokenizer compatibility and actual translation untested',
                     'Installed size is an estimate until archive approval/build','No runtime or default change is authorized by this proposal'])
    (OUT/(PREFIX+'-proposal.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ['package_count','reused_package_count','new_package_count','new_download_bytes','existing_payload_estimate_bytes','bootstrap_bytes','metadata_closure_satisfied','ready_to_install']},indent=2))


if __name__=='__main__':main()
