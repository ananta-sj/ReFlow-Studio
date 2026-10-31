"""Verify official wheel hashes, metadata and inherited dependency compatibility."""
import hashlib
import html
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import urllib.parse
import zipfile
from email.parser import BytesParser

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    package_versions = {'torch': '2.9.1+cu128', 'torchvision': '0.24.1+cu128', 'torchaudio': '2.9.1+cu128'}
    base = ROOT / 'runtime_profiles/indicf5-evaluation/Lib/site-packages'
    inherited = {canonicalize_name(dist.metadata['Name']): dist.version for dist in metadata.distributions(path=[str(base)])}
    inherited.update(package_versions)
    folder = ROOT / 'temp/indicf5-gpu-wheels'
    report = dict(verified=False, dependency_requirements_satisfied=False, packages=[], source='official PyTorch CUDA 12.8 package index')
    for name, version in package_versions.items():
        filename = f'{name}-{version}-cp310-cp310-win_amd64.whl'
        wheel = folder / filename
        if not wheel.is_file():
            raise FileNotFoundError('Required wheel incomplete: ' + filename)
        index = f'https://download.pytorch.org/whl/cu128/{name}/'
        response = requests.get(index, timeout=30)
        response.raise_for_status()
        links = [html.unescape(value) for value in re.findall(r'href="([^"]+)"', response.text)]
        matches = [urllib.parse.urljoin(index, value) for value in links
                   if urllib.parse.unquote(urllib.parse.urlsplit(value).path).endswith('/'+filename)]
        if len(matches) != 1:
            raise ValueError('Official wheel link missing or ambiguous')
        parsed = urllib.parse.urlsplit(matches[0])
        if parsed.scheme != 'https' or parsed.hostname not in {'download.pytorch.org', 'download-r2.pytorch.org'}:
            raise ValueError('Unexpected official artifact host')
        expected = urllib.parse.parse_qs(parsed.fragment)['sha256'][0]
        digest = hashlib.sha256()
        with wheel.open('rb') as handle:
            for block in iter(lambda: handle.read(8*1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError('Official checksum mismatch: ' + filename)
        with zipfile.ZipFile(wheel) as archive:
            entries = [value for value in archive.namelist() if value.endswith('.dist-info/METADATA')]
            if len(entries) != 1:
                raise ValueError('Wheel metadata ambiguous')
            info = BytesParser().parsebytes(archive.read(entries[0]))
        if canonicalize_name(info['Name']) != name or info['Version'] != version:
            raise ValueError('Wheel name/version differs from approved package set')
        requirements = info.get_all('Requires-Dist', [])
        missing = []
        for value in requirements:
            requirement = Requirement(value)
            if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
                continue
            installed = inherited.get(canonicalize_name(requirement.name))
            if installed is None or Version(installed) not in requirement.specifier:
                missing.append(dict(requirement=value, inherited_version=installed))
        row = dict(name=name, version=version, wheel=str(wheel), bytes=wheel.stat().st_size,
                   sha256=expected, official_checksum_pass=True, requires_dist=requirements,
                   unsatisfied_requirements=missing)
        report['packages'].append(row)
    report.update(verified=True, dependency_requirements_satisfied=not any(row['unsatisfied_requirements'] for row in report['packages']))
    (ROOT / 'docs/validation/2026-10-06-indicf5-gpu-wheels.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
    if not report['dependency_requirements_satisfied']:
        raise ValueError('GPU package dependency requirements are not satisfied')


if __name__ == '__main__':
    main()
