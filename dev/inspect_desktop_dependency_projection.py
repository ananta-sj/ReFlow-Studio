"""Review dependency metadata and published artifacts, without downloading code.

This is a projection, not an installable lock: proxy-tools needs an approved
source-to-wheel build and subsequent real resolver acceptance.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'dev')]
from prepare_desktop_runtime_lock import ROOTS
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.tags import cpython_tags, compatible_tags
from packaging.version import Version, InvalidVersion

OUT = ROOT / 'docs/validation'
ENV = dict(implementation_name='cpython', implementation_version='3.13.16',
           os_name='nt', platform_machine='AMD64', platform_release='10',
           platform_system='Windows', platform_version='10', python_full_version='3.13.16',
           platform_python_implementation='CPython', python_version='3.13', sys_platform='win32')
TAGS = list(cpython_tags((3, 13), abis=['cp313'], platforms=['win_amd64']))
TAGS += list(compatible_tags((3, 13), interpreter='cp313', platforms=['win_amd64']))
RANK = {tag: index for index, tag in reversed(list(enumerate(TAGS)))}
CACHE = {}


def metadata(name, version=None):
    url = 'https://pypi.org/pypi/' + name + ('/' + version if version else '') + '/json'
    if url not in CACHE:
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = response.read(8_000_001)
        if len(payload) > 8_000_000:
            raise ValueError('Metadata size bound exceeded')
        CACHE[url] = json.loads(payload)
    return CACHE[url]


def artifact(data, allow_source=False):
    choices = []
    for row in data['urls']:
        if row['yanked'] or row.get('requires_python') and '3.13.16' not in SpecifierSet(row['requires_python']):
            continue
        if row['packagetype'] == 'bdist_wheel':
            tags = parse_wheel_filename(row['filename'])[3]
            ranks = [RANK[tag] for tag in tags if tag in RANK]
            if ranks:
                choices.append((min(ranks), row))
        elif allow_source and row['packagetype'] == 'sdist':
            choices.append((100_000, row))
    return min(choices, key=lambda entry: entry[0])[1] if choices else None


def choose(name, constraints):
    spec = SpecifierSet(','.join(str(req.specifier) for req in constraints if req.specifier))
    root_pin = ROOTS.get(name)
    latest = metadata(name)
    versions = [root_pin] if root_pin else [latest['info']['version']]
    versions += sorted((version for version in latest['releases']
                        if valid_version(version) and not Version(version).is_prerelease), key=Version, reverse=True)
    for version in dict.fromkeys(versions):
        if version not in spec or root_pin and version != root_pin:
            continue
        data = metadata(name, version)
        if data['info'].get('requires_python') and '3.13.16' not in SpecifierSet(data['info']['requires_python']):
            continue
        selected = artifact(data, allow_source=name == 'proxy-tools')
        if selected:
            return data, selected
    raise ValueError('No target artifact satisfies ' + name + ': ' + str(spec))


def valid_version(value):
    try:
        Version(value)
        return True
    except InvalidVersion:
        return False


def project():
    selected = {}
    extras = {}
    constraints = {canonicalize_name(name): [Requirement(name + '==' + version)] for name, version in ROOTS.items()}
    for iteration in range(20):
        new_selected = {name: choose(name, requirements) for name, requirements in constraints.items()}
        new_constraints = {canonicalize_name(name): [Requirement(name + '==' + version)] for name, version in ROOTS.items()}
        new_extras = {name: set() for name in new_selected}
        edges = []
        for name, (data, _) in new_selected.items():
            for raw in data['info'].get('requires_dist') or []:
                req = Requirement(raw)
                if req.url:
                    raise ValueError('Unexpected direct dependency URL')
                if req.marker and not any(req.marker.evaluate(dict(ENV, extra=e)) for e in {''} | extras.get(name, set())):
                    continue
                dependency = canonicalize_name(req.name)
                new_constraints.setdefault(dependency, []).append(req)
                new_extras.setdefault(dependency, set()).update(req.extras)
                edges.append(dict(parent=name, requirement=raw, dependency=dependency))
        stable = (new_constraints == constraints and new_extras == extras)
        selected, constraints, extras = new_selected, new_constraints, new_extras
        if stable:
            break
    else:
        raise ValueError('Dependency projection did not converge')
    rows = []
    for name, (data, file) in sorted(selected.items()):
        parsed = urlsplit(file['url'])
        assert parsed.scheme == 'https' and parsed.hostname == 'files.pythonhosted.org'
        info = data['info']
        rows.append(dict(name=name, version=info['version'], filename=file['filename'], url=file['url'],
                         sha256=file['digests']['sha256'], bytes=file['size'], artifact_type=file['packagetype'],
                         requires_python=info.get('requires_python'), requires_dist=info.get('requires_dist'),
                         license_expression=info.get('license_expression'), license=info.get('license'),
                         license_files=info.get('license_files'),
                         parents=sorted({edge['parent'] for edge in edges if edge['dependency'] == name}),
                         requested_extras=sorted(extras[name]), root=name in ROOTS))
    for edge in edges:
        req = Requirement(edge['requirement'])
        edge['satisfied'] = selected[edge['dependency']][0]['info']['version'] in req.specifier
    assert all(edge['satisfied'] for edge in edges)
    return dict(schema='reflow.desktop.dependency-projection.v1', checked_at=datetime.now(timezone.utc).isoformat(),
                target_environment=ENV, roots=ROOTS, packages=rows, edges=edges,
                declared_metadata_constraints_satisfied=True, installable_lock=False,
                source_build_required=['proxy-tools==0.1.0'],
                source_archive_dependency_metadata_verified=False,
                packages_installed=False, archives_downloaded=False, release_ready=False,
                total_published_artifact_bytes=sum(row['bytes'] for row in rows),
                extracted_footprint_verified=False)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--security-revised', action='store_true')
    args = parser.parse_args()
    if args.security_revised:
        ROOTS.update(pillow='12.3.0', requests='2.34.2')
    label = 'desktop-security-candidate' if args.security_revised else 'desktop-candidate'
    path = OUT / ('2026-10-13-' + label + '-dependency-projection.json')
    assert not path.exists(), 'Preserve previous evidence'
    result = project()
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(packages=len(result['packages']), edges=len(result['edges']),
                         bytes=result['total_published_artifact_bytes'], source_build_required=result['source_build_required']), indent=2))


if __name__ == '__main__':
    main()
