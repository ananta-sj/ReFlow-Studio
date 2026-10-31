"""Explicit CPU recognition runtime; no installation or automatic fallback."""
import json
import re
from email.parser import Parser
from pathlib import Path

from core.python_runtime import project_root, worker_python
from core.runtime_integrity import safe_path, digest, sha

PROFILE = 'recognition-candidate'
LOCK = 'docs/validation/2026-10-15-recognition-candidate-lock-review.json'
SOURCES = ('core/stt/stt_handler.py', 'core/run_stt.py', 'core/recognition_compat.py',
           'core/recognition_language.py', 'core/transcription.py')


def validate(root=None):
    root = Path(root or project_root())
    try:
        folder = safe_path(root/'runtime_profiles'/PROFILE)
        recipe = json.loads(safe_path(folder/'routing-recipe.json').read_text(encoding='utf-8'))
        if not isinstance(recipe, dict) or recipe.get('schema') != 'reflow.recognition-runtime.v1' or recipe.get('python') != '3.13.16' or recipe.get('device') != 'cpu':
            raise ValueError('Unrecognized CPU recognition runtime recipe')
        records = {name: sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')}
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
        for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
            headers = Parser().parsestr(safe_path(path).read_text(encoding='utf-8'))
            name = re.sub(r'[-_.]+', '-', headers.get('Name', '')).lower()
            if not name or name in actual:
                raise ValueError('Duplicate or invalid recognition distribution metadata')
            actual[name] = headers.get('Version')
            metadata.append((path.parent.name, sha(path)))
        if actual != expected:
            raise ValueError('Recognition installed package versions differ from the verified lock')
        records.update(sources=sources, lock=sha(lock), metadata=metadata)
        return dict(executable=str(folder/'python.exe'), identity=digest(records), device='cpu', profile=str(folder))
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
