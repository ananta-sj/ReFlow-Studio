"""Export source files without local media, runtimes, private state or logs."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'main.py','config.py','requirements.txt','README.txt','README.md','LICENSE.txt',
            'Launch_Reflow.bat','LAUNCH_REFLOW.sh','.gitignore','.gitattributes','.gitmodules'}
LOCKS={'docs/validation/2026-10-13-xtts-security-cpu-lock-review.json',
       'docs/validation/2026-10-15-recognition-candidate-lock-review.json',
       'docs/validation/2026-10-16-m2m100-runtime-proposal.json',
       'docs/validation/2026-10-16-separation-runtime-lock-review.json',
       'docs/validation/2026-10-16-visual-runtime-lock-review.json'}
DENY_SUFFIXES={'.wav','.mp3','.mp4','.pth','.pt','.onnx','.safetensors','.bin',
               '.exe','.dll','.pyd','.so','.dylib','.msi','.7z','.tar','.gz',
               '.pyc','.pyo','.whl','.zip','.log','.tmp','.bak','.old','.tsbuildinfo'}
DENY_NAMES={'settings.json','models.json','ui_preferences.json','hardware_profile.json',
            'graph.json','queue_state.json','render_state.json','direct_url.json'}


def include(name):
    path=Path(name)
    if '\\' in name or path.is_absolute() or path.drive or '..' in path.parts:
        return False
    if any(part in {'__pycache__','node_modules','dist','.git','temp','results','checkpoints'} for part in path.parts):
        return False
    if name.startswith('core/MuseTalk/models/'):
        return False
    if path.suffix.lower() in DENY_SUFFIXES or path.name in DENY_NAMES or path.name.startswith('.env'):
        return False
    if name in ROOT_FILES or name in LOCKS or name in {'docs/GITHUB_NATIVE_BUILDS.md','docs/GITHUB_UPLOAD_GUIDE.md'}:
        return True
    if name in {'assets/icon.ico','assets/icon.png'}:
        return True
    if name.startswith('frontend/'):
        return path.parent.as_posix()=='frontend' or name.startswith(('frontend/src/','frontend/public/','frontend/dev/'))
    return name.startswith(('core/','bridge/','packaging/','.github/','dev/'))


def collect_names():
    names=set();revisions={};missing=[];visited=set()
    def collect(folder):
        if folder.resolve() in visited:
            raise RuntimeError('Repeated nested source repository')
        visited.add(folder.resolve())
        listed=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=folder)
        for item in listed.decode('utf-8').split('\0'):
            if not item: continue
            path=folder/item
            relative=path.relative_to(ROOT).as_posix().rstrip('/')
            if not include(relative): continue
            if path.is_dir():
                if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
                    raise RuntimeError('Nested source repository is a link')
                if (path/'.git').exists():
                    revisions[relative]=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
                    collect(path)
                else:
                    missing.append(relative)
            elif path.is_file():
                names.add(relative)
    collect(ROOT)
    return sorted(names),revisions,missing


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='ReflowStudio-source.zip')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.zip',args.name):
        raise ValueError('Use a simple source ZIP name')
    output=ROOT/'release-assets'
    output.mkdir(exist_ok=True)
    archive=output/args.name
    names,revisions,missing=collect_names()
    if not {'main.py','frontend/package.json','.github/workflows/build.yml'}<=set(names):
        raise RuntimeError('Source inventory is incomplete')
    records=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,strict_timestamps=False) as bundle:
        for name in names:
            source=ROOT/name
            for item in (source,*source.parents):
                if item.is_symlink() or getattr(item.lstat(),'st_file_attributes',0)&0x400:
                    raise RuntimeError('Source export refuses links and junctions')
                if item==ROOT: break
            if not source.resolve().is_relative_to(ROOT):
                raise RuntimeError('Source export escaped project')
            payload=source.read_bytes()
            records.append(dict(path=name,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest()))
            bundle.writestr('ReflowStudio-source/'+name,payload)
        bundle.writestr('ReflowStudio-source/SOURCE_MANIFEST.json',json.dumps(dict(
            files=records,release_ready=False,licensing_review_pending=True,
            personal_media_excluded=True,model_weights_excluded=True,
            nested_source_revisions=revisions,unavailable_nested_repositories=missing),indent=2))
    with zipfile.ZipFile(archive) as bundle:
        for row in records:
            if hashlib.sha256(bundle.read('ReflowStudio-source/'+row['path'])).hexdigest()!=row['sha256']:
                raise RuntimeError('Source ZIP readback mismatch')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps(dict(archive=str(archive),files=len(records),bytes=archive.stat().st_size,sha256=digest),indent=2))


if __name__=='__main__':
    main()
