"""Explicit CPU fallback runtime bound to the approved 41-package proposal."""
from email.parser import Parser
import json
from pathlib import Path
import re
from core.python_runtime import project_root
from core.runtime_integrity import sha, safe_path, digest

PLAN='docs/validation/2026-10-16-m2m100-runtime-proposal.json'
SOURCES=('core/m2m100_worker.py','core/llm_translator.py',
         'core/providers/translation/m2m100_isolated.py','core/languages.py',
         'core/source_language.py','core/translation_completion.py',
         'core/generation_control.py','core/recovery_sources.json')


def validate(root=None):
    root=Path(root or project_root())
    try:
        folder=safe_path(root/'runtime_profiles/translation-candidate')
        profile=json.loads(safe_path(folder/'profile.json').read_text(encoding='utf-8'))
        plan=json.loads(safe_path(root/PLAN).read_text(encoding='utf-8'))
        if not isinstance(profile,dict) or profile.get('python')!='3.13.16' or profile.get('device')!='cpu':
            raise ValueError('Invalid translation runtime profile')
        if sha(root/PLAN)!=profile.get('proposal_sha256'):
            raise ValueError('Translation dependency proposal changed')
        bootstrap={row['name']:sha(folder/row['name']) for row in plan['bootstrap']}
        if bootstrap!=profile.get('bootstrap_sha256'):
            raise ValueError('Translation Python bootstrap changed')
        recipe=json.loads(safe_path(folder/'routing-recipe.json').read_text(encoding='utf-8'))
        sources={name:sha(root/name) for name in SOURCES}
        if not isinstance(recipe,dict) or recipe.get('schema')!='reflow.m2m100-runtime.v1' or recipe.get('source_sha256')!=sources:
            raise ValueError('M2M100 worker recipe changed; revalidate this candidate')
        actual={};metadata=[]
        for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
            headers=Parser().parsestr(safe_path(path).read_text(encoding='utf-8'))
            name=re.sub(r'[-_.]+','-',headers.get('Name','')).lower()
            if not name or name in actual:raise ValueError('Duplicate or invalid translation metadata')
            actual[name]=headers.get('Version');metadata.append((path.parent.name,sha(path)))
        expected={row['name']:row['version'] for row in plan['packages']}
        if actual!=expected or len(actual)!=41:
            raise ValueError('Translation packages differ from the approved closure')
        identity=digest(dict(bootstrap=bootstrap,metadata=metadata,sources=sources,proposal=sha(root/PLAN)))
        return dict(executable=str(folder/'python.exe'),profile=str(folder),device='cpu',identity=identity)
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise RuntimeError('Isolated M2M100 is unavailable: '+str(error)) from error


def readiness(root=None):
    try:return dict(status='ready-for-explicit-trial',runtime=validate(root),release_ready=False)
    except RuntimeError as error:return dict(status='unverified',details=[str(error)],release_ready=False)


def model_contract(root=None,verify_weights=False):
    root=Path(root or project_root())
    source=json.loads((root/'core/recovery_sources.json').read_text(encoding='utf-8'))['m2m100']
    model=safe_path(root/source['folder'])
    for row in source['files']:
        if row['name']=='README.md':continue
        path=safe_path(model/row['name'])
        if not path.is_file() or path.stat().st_size!=row['size']:
            raise ValueError('Existing M2M100 asset missing or changed: '+row['name']+'. Recover the model before this offline trial.')
        if row.get('sha256') and (verify_weights or path.suffix!='.bin') and sha(path)!=row['sha256']:
            raise ValueError('M2M100 asset hash changed: '+row['name'])
    return dict(model_path=str(model),revision=source['revision'])
