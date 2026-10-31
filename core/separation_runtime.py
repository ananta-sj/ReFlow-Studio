"""Explicit CPU Demucs runtime with a bound dependency and worker recipe."""
from email.parser import Parser
import json,re
from pathlib import Path
from core.python_runtime import project_root
from core.runtime_integrity import sha,safe_path,digest
LOCK='docs/validation/2026-10-16-separation-runtime-lock-review.json'
SOURCES=('core/separation_runtime.py','core/audio_separator.py','core/run_demucs.py')
MODEL_SHA256='8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4'

def validate(root=None):
    root=Path(root or project_root())
    try:
        folder=safe_path(root/'runtime_profiles/separation-candidate')
        profile=json.loads(safe_path(folder/'profile.json').read_text(encoding='utf-8'))
        lock=json.loads(safe_path(root/LOCK).read_text(encoding='utf-8'))
        if profile.get('python')!='3.13.16' or profile.get('device')!='cpu' or profile.get('lock_sha256')!=sha(root/LOCK):raise ValueError('Separation profile/lock changed')
        bootstrap={row['name']:sha(folder/row['name']) for row in lock['bootstrap']}
        if bootstrap!=profile.get('bootstrap_sha256'):raise ValueError('Separation Python bootstrap changed')
        recipe=json.loads(safe_path(folder/'routing-recipe.json').read_text(encoding='utf-8'))
        sources={name:sha(root/name) for name in SOURCES}
        if recipe.get('schema')!='reflow.separation-runtime.v1' or recipe.get('source_sha256')!=sources:raise ValueError('Separation worker recipe changed; revalidate this candidate')
        actual={};metadata=[]
        for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
            header=Parser().parsestr(safe_path(path).read_text(encoding='utf-8'));name=re.sub(r'[-_.]+','-',header.get('Name','')).lower()
            if not name or name in actual:raise ValueError('Duplicate or invalid separation metadata')
            actual[name]=header.get('Version');metadata.append((path.parent.name,sha(path)))
        if len(actual)!=32 or actual!={row['name']:row['version'] for row in lock['packages']}:raise ValueError('Separation packages differ from approved closure')
        return dict(executable=str(folder/'python.exe'),profile=str(folder),device='cpu',identity=digest(dict(bootstrap=bootstrap,metadata=metadata,sources=sources,lock=sha(root/LOCK))))
    except (OSError,ValueError,KeyError,TypeError) as error:raise RuntimeError('Isolated separation is unavailable: '+str(error)) from error

def model_contract(root=None,verify_weights=False):
    root=Path(root or project_root());path=safe_path(root/'models/uvr/955717e8-8726e21a.th')
    if not path.is_file() or not path.stat().st_size:raise ValueError('Existing Demucs model is missing; recover it before this offline trial')
    if verify_weights and sha(path)!=MODEL_SHA256:raise ValueError('Demucs checkpoint checksum mismatch')
    return dict(model_path=str(path))

def readiness(root=None):
    try:return dict(status='ready-for-explicit-trial',runtime=validate(root),release_ready=False)
    except RuntimeError as error:return dict(status='unverified',details=[str(error)],release_ready=False)
