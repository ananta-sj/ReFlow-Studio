"""Independently bind the approved desktop dry run to target metadata/artifacts."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
sys.path[:0] = [str(ROOT / 'dev')]
from inspect_desktop_dependency_projection import ENV, TAGS
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename


def published_artifact(item):
    name = canonicalize_name(item['metadata']['name'])
    info = item['download_info']
    parsed = urlsplit(info['url'])
    filename = unquote(parsed.path.rsplit('/', 1)[-1])
    digest = info['archive_info']['hashes']['sha256']
    if parsed.scheme == 'file':
        path = Path(urllib.request.url2pathname(parsed.path)).resolve()
        assert path.is_relative_to((OUT / '2026-10-13-proxy-tools-helper').resolve()) and name == 'proxy-tools'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        return dict(bytes=path.stat().st_size, artifact_bytes_verified=True, source='approved local build')
    assert parsed.scheme == 'https' and parsed.hostname == 'files.pythonhosted.org'
    metadata_url = f"https://pypi.org/pypi/{name}/{item['metadata']['version']}/json"
    with urllib.request.urlopen(metadata_url, timeout=25) as response:
        payload = response.read(5_000_001)
    assert len(payload) <= 5_000_000
    data = json.loads(payload)
    matches = [row for row in data['urls'] if row['filename'] == filename and row['digests']['sha256'] == digest]
    assert len(matches) == 1 and not matches[0]['yanked']
    row = matches[0]
    assert row['url'] == info['url'] and row['packagetype'] == 'bdist_wheel'
    return dict(bytes=row['size'], artifact_bytes_verified=False, source=metadata_url,
                published_hash_verified=True, yanked=False)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='2026-10-13-desktop-candidate')
    parser.add_argument('--resolution-label', default='with-approved-helper')
    parser.add_argument('--without-desktop-projection', action='store_true')
    args = parser.parse_args()
    assert args.prefix.replace('-', '').isalnum() and args.resolution_label.replace('-', '').isalnum()
    destination = OUT / (args.prefix + '-lock-review.json')
    assert not destination.exists(), 'Preserve historical locks'
    report = json.loads((OUT / (args.prefix + '-' + args.resolution_label + '-resolution-report.json')).read_text())
    receipt = json.loads((OUT / (args.prefix + '-' + args.resolution_label + '-resolution-receipt.json')).read_text())
    assert receipt['exit_code'] == 0 and receipt['resolution_complete'] and not receipt['archives_allowed']
    selected = {canonicalize_name(item['metadata']['name']): item for item in report['install']}
    assert len(selected) == len(report['install'])
    roots = {canonicalize_name(name): version for name, version in receipt['roots'].items()}
    reachable = set(roots)
    extras = {name: set() for name in selected}
    for _ in range(len(selected) + 1):
        before = (set(reachable), {name: set(values) for name, values in extras.items()})
        for name in list(reachable):
            assert name in selected, 'Missing target dependency ' + name
            for value in selected[name]['metadata'].get('requires_dist', []):
                req = Requirement(value)
                assert not req.url
                if req.marker and not any(req.marker.evaluate(dict(ENV, extra=e)) for e in {''} | extras[name]):
                    continue
                dependency = canonicalize_name(req.name)
                reachable.add(dependency)
                assert dependency in selected, 'Missing target dependency ' + dependency
                extras[dependency].update(req.extras)
        if before == (reachable, extras):
            break
    else:
        raise AssertionError('Extras/reachability did not converge')
    edges = []
    rows = []
    for name in sorted(reachable):
        item = selected[name]
        meta = item['metadata']
        parsed = urlsplit(item['download_info']['url'])
        filename = unquote(parsed.path.rsplit('/', 1)[-1])
        assert parse_wheel_filename(filename)[3] & set(TAGS), 'Wrong target wheel ' + name
        assert not meta.get('requires_python') or '3.13.16' in SpecifierSet(meta['requires_python'])
        if name in roots:
            assert meta['version'] == roots[name]
        for value in meta.get('requires_dist', []):
            req = Requirement(value)
            if req.marker and not any(req.marker.evaluate(dict(ENV, extra=e)) for e in {''} | extras[name]):
                continue
            dependency = canonicalize_name(req.name)
            assert selected[dependency]['metadata']['version'] in req.specifier, 'Constraint failure: ' + value
            edges.append(dict(parent=name, requirement=value, dependency=dependency, satisfied=True))
        rows.append(dict(name=name, version=meta['version'], filename=filename,
                         url=item['download_info']['url'], sha256=item['download_info']['archive_info']['hashes']['sha256'],
                         license=meta.get('license'), license_expression=meta.get('license_expression'),
                         requested_extras=sorted(extras[name]), root=name in roots,
                         requires_python=meta.get('requires_python'), requires_dist=meta.get('requires_dist', [])))
    with ThreadPoolExecutor(max_workers=6) as pool:
        budgets = list(pool.map(published_artifact, [selected[row['name']] for row in rows]))
    for row, budget in zip(rows, budgets):
        row.update(budget)
        row['parents'] = sorted({edge['parent'] for edge in edges if edge['dependency'] == row['name']})
    projection = {'packages': []} if args.without_desktop_projection else json.loads((OUT / '2026-10-13-desktop-security-candidate-dependency-projection.json').read_text())
    old_versions = {row['name']: row['version'] for row in projection['packages']}
    version_changes = {row['name']: dict(projected=old_versions.get(row['name']), resolved=row['version'])
                       for row in rows if old_versions and row['version'] != old_versions.get(row['name'])}
    lock = dict(schema='reflow.feature.candidate-lock.review.v1' if args.without_desktop_projection else 'reflow.desktop.candidate-lock.review.v1', target_environment=ENV, roots=roots,
                metadata_closure_valid=True, packages=rows, edges=edges, issues=[],
                excluded_host_marker_packages=sorted(set(selected) - reachable),
                versions_changed_from_projection=version_changes,
                artifact_download_bytes=sum(row['bytes'] for row in rows), download_size_verified=True,
                remote_artifact_bytes_verified=False, install_authorized=False,
                runtime_execution_verified=False, notice_review_complete=False, release_ready=False,
                approved_helper_sha256=receipt['approved_local_helper_sha256'])
    destination.write_text(json.dumps(lock, indent=2), encoding='utf-8')
    lines = ['# Reviewed Windows CPython 3.13.16 candidate; installation NOT authorized.',
             '# Remote archive hashes are published values; local helper bytes are verified.']
    lines += [f"{row['name']} @ {row['url']} --hash=sha256:{row['sha256']}" for row in rows]
    (OUT / (args.prefix + '-review.lock.txt')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(dict(packages=len(rows), active_edges=len(edges), bytes=lock['artifact_download_bytes'],
                         excluded=lock['excluded_host_marker_packages'], version_changes=version_changes), indent=2))


if __name__ == '__main__':
    main()
