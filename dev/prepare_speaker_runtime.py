"""Install the approved speaker evaluation packages without modifying shared runtimes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import distributions
from packaging.requirements import Requirement
from packaging.markers import default_environment
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SHARED = ('cuda', 'xtts-security-candidate', 'separation-candidate', 'recognition-candidate')


def main():
    from core.cuda_runtime import validate
    from core.runtime_integrity import sha
    validate('speech')
    folder = ROOT/'runtime_profiles/speaker-diarization'
    owner = folder/'.owner'
    if folder.exists() and (not owner.is_file() or owner.read_text() != 'reflow.speaker-evaluation.v1'):
        raise RuntimeError('Refusing to modify an unowned runtime folder')
    folder.mkdir(exist_ok=True)
    owner.write_text('reflow.speaker-evaluation.v1')
    for path in (ROOT/'runtime_profiles/cuda').iterdir():
        if path.is_file() and path.name not in ('profile.json', '.owner', 'python313._pth'):
            shutil.copy2(path, folder/path.name)
    packages = folder/'Lib/site-packages'
    packages.mkdir(parents=True, exist_ok=True)
    pth = 'python313.zip\n.\nLib/site-packages\n'+''.join(
        f'../{name}/Lib/site-packages\n' for name in SHARED)+'import site\n'
    (folder/'python313._pth').write_text(pth, encoding='utf-8')
    paths = [packages, *[ROOT/'runtime_profiles'/name/'Lib/site-packages' for name in SHARED]]
    marker = {**default_environment(), 'python_version':'3.13', 'python_full_version':'3.13.16'}
    root = Requirement('pyannote.audio==4.0.7')
    receipts = []
    for iteration in range(16):
        installed = {}
        for location in paths:
            for dist in distributions(path=[str(location)]):
                installed.setdefault(canonicalize_name(dist.metadata['Name']), dist)
        pending, visited, missing = [root], set(), {}
        while pending:
            requirement = pending.pop()
            key = canonicalize_name(requirement.name)
            extras = tuple(sorted(requirement.extras))
            if (key, extras, str(requirement.specifier)) in visited:
                continue
            visited.add((key, extras, str(requirement.specifier)))
            dist = installed.get(key)
            if dist is None or not requirement.specifier.contains(dist.version, prereleases=True):
                missing.setdefault(key, []).append(requirement)
                continue
            for raw in dist.requires or []:
                child = Requirement(raw)
                if child.marker is None or any(child.marker.evaluate({**marker, 'extra':extra}) for extra in ('', *extras)):
                    pending.append(child)
        if not missing:
            break
        wanted = []
        for key, requirements in sorted(missing.items()):
            extras = sorted(set().union(*(req.extras for req in requirements)))
            specifiers = ','.join(str(req.specifier) for req in requirements if str(req.specifier))
            wanted.append(key+('['+','.join(extras)+']' if extras else '')+specifiers)
        print('Installing evaluation dependencies:', ', '.join(wanted), flush=True)
        receipt = folder/f'install-{iteration:02d}.json'
        with tempfile.TemporaryDirectory(prefix='speaker-install-', dir=ROOT/'build') as stage:
            subprocess.run([str(ROOT/'build/windows-portable/python.exe'), '-B', '-m', 'pip', '--isolated',
                'install', '--index-url', 'https://pypi.org/simple', '--no-deps', '--no-compile',
                '--only-binary=:all:', '--python-version', '3.13', '--platform', 'win_amd64',
                '--implementation', 'cp', '--abi', 'cp313', '--target', stage, '--report', str(receipt),
                *wanted], check=True)
            shutil.copytree(stage, packages, dirs_exist_ok=True)
        receipts.append(receipt.name)
    else:
        raise RuntimeError('Speaker dependency resolution did not converge; shared runtimes were not changed')
    record = dict(schema='reflow.speaker-evaluation.v1', status='packages-installed-model-access-required',
        python='3.13.16', pth=pth, package='pyannote.audio==4.0.7', receipts=receipts,
        bootstrap={name:sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')},
        installed={key:dist.version for key,dist in installed.items() if str(dist._path).startswith(str(packages))})
    (folder/'profile.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print('Isolated speaker runtime prepared. No model weights downloaded yet.', flush=True)


if __name__ == '__main__':
    main()
