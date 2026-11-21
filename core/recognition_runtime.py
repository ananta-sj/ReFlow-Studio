"""Explicit CPU recognition runtime; no installation or automatic fallback."""
import json
import os
import re
from email.parser import Parser
from pathlib import Path

from core.python_runtime import project_root, worker_python
from core.runtime_integrity import safe_path, digest, sha

PROFILE = 'recognition-candidate'
LOCK = 'docs/validation/2026-10-15-recognition-candidate-lock-review.json'
SOURCES = ('core/stt/stt_handler.py', 'core/run_stt.py', 'core/recognition_compat.py',
           'core/recognition_language.py', 'core/transcription.py',
           'core/providers/stt/whisper_local.py')


def venv_bootstrap(root, folder):
    """Fixed existing base + isolated launcher; recipe cannot choose an interpreter."""
    root, folder = Path(root), Path(folder)
    base = safe_path(root/'build/ci-runtime/python')
    cfg = safe_path(folder/'venv/pyvenv.cfg')
    values = {}
    for line in cfg.read_text(encoding='utf-8').splitlines():
        if '=' not in line:
            continue
        key, value = (part.strip() for part in line.split('=', 1))
        if key in values:
            raise ValueError('Duplicate recognition environment configuration key')
        values[key] = value
    if (values.get('include-system-site-packages', '').lower() != 'false' or
            values.get('version') != '3.13.18' or Path(values.get('home', '')).resolve() != base.resolve()):
        raise ValueError('Recognition virtual environment must remain isolated on the verified base')
    scripts = safe_path(folder/'venv/Scripts')
    paths = [cfg]
    paths += [safe_path(path) for path in scripts.iterdir() if path.is_file() and path.suffix.lower() in ('.exe', '.dll', '.zip', '._pth')]
    paths += [path for path in base.iterdir() if path.is_file() and path.suffix.lower() in ('.exe', '.dll', '.zip', '._pth')]
    for directory in ('Lib', 'DLLs'):
        for current, directories, files in os.walk(safe_path(base/directory), followlinks=False):
            directories[:] = [name for name in directories if name != 'site-packages']
            for name in directories:
                safe_path(Path(current)/name)
            paths.extend(safe_path(Path(current)/name) for name in files)
    if not (base/'python.exe').is_file() or not (base/'python313.dll').is_file():
        raise ValueError('Recognition base interpreter is incomplete')
    return {path.relative_to(root).as_posix(): sha(path) for path in sorted(paths)}


def validate(root=None):
    root = Path(root or project_root())
    try:
        folder = safe_path(root/'runtime_profiles'/PROFILE)
        recipe = json.loads(safe_path(folder/'routing-recipe.json').read_text(encoding='utf-8'))
        if not isinstance(recipe, dict) or recipe.get('device') != 'cpu':
            raise ValueError('Unrecognized CPU recognition runtime recipe')
        if recipe.get('schema') == 'reflow.recognition-runtime.v1' and recipe.get('python') == '3.13.16':
            records = {name: sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')}
            executable = folder/'python.exe'
            site = folder/'Lib/site-packages'
        elif recipe.get('schema') == 'reflow.recognition-runtime.v2' and recipe.get('python') == '3.13.18':
            records = venv_bootstrap(root, folder)
            executable = folder/'venv/Scripts/python.exe'
            site = folder/'venv/Lib/site-packages'
        else:
            raise ValueError('Unrecognized CPU recognition runtime recipe')
        if records != recipe.get('bootstrap_sha256'):
            raise ValueError('Recognition Python bootstrap changed; revalidate this runtime')
        sources = {name: sha(root/name) for name in SOURCES}
        if sources != recipe.get('source_sha256'):
            raise ValueError('Recognition worker recipe changed; revalidate before rendering')
        lock = root/LOCK
        if sha(lock) != recipe.get('lock_sha256'):
            raise ValueError('Recognition dependency lock changed')
        expected = {row['name']: row['version'] for row in json.loads(lock.read_text(encoding='utf-8'))['packages']}
        actual, metadata = {}, []
        for path in sorted(site.glob('*.dist-info/METADATA')):
            headers = Parser().parsestr(safe_path(path).read_text(encoding='utf-8'))
            name = re.sub(r'[-_.]+', '-', headers.get('Name', '')).lower()
            if not name or name in actual:
                raise ValueError('Duplicate or invalid recognition distribution metadata')
            actual[name] = headers.get('Version')
            metadata.append((path.parent.name, sha(path)))
        if actual != expected:
            raise ValueError('Recognition installed package versions differ from the verified lock')
        records.update(sources=sources, lock=sha(lock), metadata=metadata)
        return dict(executable=str(executable), identity=digest(records), device='cpu', profile=str(folder), portable=recipe['schema']=='reflow.recognition-runtime.v1')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError('Isolated recognition is unavailable: '+str(error)) from error


def readiness(root=None):
    try:
        return dict(status='ready-for-explicit-trial', runtime=validate(root), release_ready=False)
    except RuntimeError as error:
        return dict(status='unverified', details=[str(error)], release_ready=False)


def resolve(selection='legacy'):
    if selection in (None, 'legacy'):
        return dict(executable=worker_python(), device='cpu')
    if selection == 'isolated':
        return validate()
    raise ValueError('Choose current or isolated recognition runtime')
