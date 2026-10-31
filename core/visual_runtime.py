"""Explicit isolated CPU face restoration with a bound worker/security recipe."""
from email.parser import Parser
import json,re
from pathlib import Path
from core.python_runtime import project_root
from core.runtime_integrity import sha,safe_path,digest
LOCK='docs/validation/2026-10-16-visual-runtime-lock-review.json'
SOURCES=('core/visual_runtime.py','core/visual_imports.py','core/run_visual.py','core/providers/enhancer/gfpgan_local.py','core/enhancer.py','core/media_io.py','core/video_frames.py')
MODELS={'GFPGANv1.4.pth':'e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad',
        'parsing_parsenet.pth':'3d558d8d0e42c20224f13cf5a29c79eba2d59913419f945545d8cf7b72920de2',
        'detection_Resnet50_Final.pth':'6d1de9c2944f2ccddca5f5e010ea5ae64a39845a86311af6fdf30841b0a5a16d'}

def validate(root=None):
    root=Path(root or project_root())
    try:
        folder=safe_path(root/'runtime_profiles/visual-candidate');profile=json.loads(safe_path(folder/'profile.json').read_text())
        lock=json.loads(safe_path(root/LOCK).read_text())
        if profile.get('python')!='3.13.16' or profile.get('device')!='cpu' or profile.get('lock_sha256')!=sha(root/LOCK):raise ValueError('Visual profile/lock changed')
        bootstrap={row['name']:sha(folder/row['name']) for row in lock['bootstrap']}
        if bootstrap!=profile.get('bootstrap_sha256'):raise ValueError('Visual Python bootstrap changed')
        recipe=json.loads(safe_path(folder/'routing-recipe.json').read_text())
        sources={name:sha(root/name) for name in SOURCES}
        if recipe.get('schema')!='reflow.visual-runtime.v1' or recipe.get('source_sha256')!=sources:raise ValueError('Visual worker recipe changed; revalidate the candidate')
        actual={};metadata=[]
        for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
            header=Parser().parsestr(safe_path(path).read_text(encoding='utf-8'));name=re.sub(r'[-_.]+','-',header.get('Name','')).lower()
            if not name or name in actual:raise ValueError('Duplicate or invalid visual package metadata')
            actual[name]=header.get('Version');metadata.append((path.parent.name,sha(path)))
        if len(actual)!=55 or actual!={row['name']:row['version'] for row in lock['packages']}:raise ValueError('Visual packages differ from approved closure')
        from core.visual_imports import HASHES
        for name,digest_expected in HASHES.items():
            if sha(folder/'Lib/site-packages'/Path(*name.split('.')).with_suffix('.py'))!=digest_expected:raise ValueError('Reviewed BasicSR source changed')
        return dict(executable=str(folder/'python.exe'),profile=str(folder),device='cpu',identity=digest(dict(bootstrap=bootstrap,metadata=metadata,sources=sources,lock=sha(root/LOCK))))
    except (OSError,ValueError,KeyError,TypeError) as error:raise RuntimeError('Isolated face enhancement is unavailable: '+str(error)) from error

def model_contract(model_path=None,root=None,verify_weights=False):
    root=Path(root or project_root());paths={name:safe_path(root/'gfpgan/weights'/name) for name in MODELS}
    if model_path:paths['GFPGANv1.4.pth']=safe_path(model_path)
    for name,path in paths.items():
        if not path.is_file() or not path.stat().st_size:raise ValueError('Local face enhancement asset is missing: '+name)
        if verify_weights and sha(path)!=MODELS[name]:raise ValueError('Face enhancement checkpoint checksum mismatch: '+name)
    return dict(model_path=str(paths['GFPGANv1.4.pth']))

def readiness(root=None):
    try:return dict(status='ready-for-explicit-trial',runtime=validate(root),release_ready=False)
    except RuntimeError as error:return dict(status='unverified',details=[str(error)],release_ready=False)
