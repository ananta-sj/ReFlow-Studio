"""Reuse the approved modern CPU packages for an explicit NLLB trial."""
import json
from pathlib import Path
from core.python_runtime import project_root
from core.runtime_integrity import sha, digest, safe_path

MANIFEST = 'core/nllb_runtime_manifest.json'
SOURCES = ('core/nllb_worker.py', 'core/providers/translation/nllb_local.py',
           'core/translation_completion.py', 'core/generation_control.py',
           'core/languages.py', 'core/source_language.py', 'core/nllb_runtime.py')


def validate(root=None):
    root = Path(root or project_root())
    try:
        from core.xtts_runtime import validate as existing_cpu_runtime
        route = existing_cpu_runtime(root)
        manifest = json.loads(safe_path(root/MANIFEST).read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('schema') != 'reflow.nllb-runtime.v1':
            raise ValueError('Invalid NLLB runtime recipe')
        sources = {name: sha(root/name) for name in SOURCES}
        if manifest.get('source_sha256') != sources or manifest.get('package_runtime_identity') != route['identity']:
            raise ValueError('NLLB worker or underlying CPU runtime changed; revalidate this trial')
        return {**route, 'identity': digest(dict(package_runtime_identity=route['identity'], source_sha256=sources))}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError('Isolated NLLB is unavailable: '+str(error)) from error


def readiness(root=None):
    try:
        return dict(status='ready-for-explicit-trial', runtime=validate(root), release_ready=False)
    except RuntimeError as error:
        return dict(status='unverified', details=[str(error)], release_ready=False)
