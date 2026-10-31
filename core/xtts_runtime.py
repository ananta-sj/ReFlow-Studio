"""Explicit CPU XTTS isolation; validation never installs or switches defaults."""
import hashlib
import json
from pathlib import Path
from email.parser import Parser
import re
from core.python_runtime import project_root
from core.stage_checkpoints import safe_path,tree_identity,digest

def sha(path):
    return hashlib.sha256(safe_path(path).read_bytes()).hexdigest()

def validate(root=None):
    root=Path(root or project_root())
    try:
        folder=safe_path(root/'runtime_profiles/xtts-security-candidate')
        data=json.loads((folder/'profile.json').read_text(encoding='utf-8'))
        if (data.get('status')!='candidate-offline-validated-with-adapter' or
            data.get('python')!='3.13.16' or data.get('device')!='cpu' or
            not data.get('runtime_verified') or not data.get('real_model_inference_verified') or
            not data.get('persistent_session_verified')):
            raise ValueError('XTTS isolated runtime has not passed its required validation')
        adapter=root/'core/xtts_compat.py';worker=root/'core/xtts_worker.py'
        lock=root/'docs/validation/2026-10-13-xtts-security-cpu-lock-review.json'
        if data.get('production_adapter_sha256')!=sha(adapter) or data.get('production_worker_sha256')!=sha(worker):
            raise ValueError('XTTS worker recipe changed; validate it before rendering')
        if data.get('dependency_lock_sha256')!=sha(lock):
            raise ValueError('XTTS dependency lock changed; validate the runtime again')
        executable=folder/'python.exe'
        if not executable.is_file():raise ValueError('XTTS isolated Python is missing')
        records={name:sha(folder/name) for name in ('python.exe','python313.dll','python313.zip')}
        if records!=data.get('production_bootstrap_sha256'):
            raise ValueError('XTTS Python bootstrap changed; validate the runtime again')
        expected={p['name']:p['version'] for p in json.loads(lock.read_text(encoding='utf-8'))['packages']}
        actual={}
        metadata_files=sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA'))
        for path in metadata_files:
            headers=Parser().parsestr(path.read_text(encoding='utf-8'))
            name=re.sub(r'[-_.]+','-',headers.get('Name','')).lower()
            if not name or name in actual:raise ValueError('Duplicate or invalid XTTS distribution metadata')
            actual[name]=headers.get('Version')
        if actual!=expected:raise ValueError('XTTS installed package versions differ from the validated lock')
        records.update(adapter=sha(adapter),worker=sha(worker),lock=sha(lock))
        records['metadata']=digest([(p.parent.name,sha(p)) for p in metadata_files])
        return dict(executable=str(executable),identity=digest(records),profile=str(folder),device='cpu')
    except (OSError,ValueError,KeyError) as error:
        raise RuntimeError('Isolated XTTS is unavailable: '+str(error)) from error

def readiness(root=None):
    try:return dict(status='ready-for-explicit-trial',runtime=validate(root),release_ready=False)
    except RuntimeError as error:return dict(status='unverified',details=[str(error)],release_ready=False)

def model_identity(path):
    directory=safe_path(path)
    for name in ('config.json','model.pth','vocab.json','speakers_xtts.pth'):
        if not (directory/name).is_file():raise ValueError('Missing XTTS asset: '+name)
    return tree_identity(directory,{'.json','.pth'})
