"""Assemble native desktop previews; optional AI runtimes are not implied."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portable_inventory',ROOT/'packaging/build_portable.py')
inventory=importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def sha(path):
    checksum=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024),b''):
            checksum.update(block)
    return checksum.hexdigest()


def assemble(target):
    base=ROOT/'dist'/('ReflowStudio-'+target+'-desktop-preview')
    if base.exists():
        raise RuntimeError('Candidate already exists')
    launcher=ROOT/'build/ci-launcher/ReflowStudio'
    if sys.platform=='darwin':
        app=base/'ReflowStudio.app'
        shutil.copytree(launcher.with_suffix('.app'),app,symlinks=True)
        payload=app/'Contents/Resources/ReflowStudio'
    else:
        shutil.copytree(launcher,base,symlinks=True)
        payload=base
    payload.mkdir(parents=True,exist_ok=True)
    for source,relative,_ in inventory.entries(trees=('core','bridge','frontend/dist')):
        if relative=='Launch_Reflow.bat':
            continue  # The CI runtime lives under python/, not the old BAT path.
        if relative=='README.txt':
            relative='SOURCE_README.txt'
        dest=payload/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
    shutil.copytree(ROOT/'build/ci-runtime/python',payload/'python',symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo','direct_url.json'))
    (payload/'packaging').mkdir()
    shutil.copy2(ROOT/'packaging/verify_payload.py',payload/'packaging/verify_payload.py')
    shutil.copy2(ROOT/'dev/verify_portable_desktop.py',payload/'packaging/desktop_smoke.py')
    status=('REFLOW STUDIO - DESKTOP PREVIEW\n\n'
        'Open ReflowStudio.exe (Windows), ReflowStudio (Linux), or ReflowStudio.app (macOS).\n'
        'Extract the entire archive to a writable folder. Keep all companion files.\n'
        'Python is included; a system Python installation is not needed.\n'
        'Only desktop dependencies and application source are included in this CI preview.\n'
        'Local AI engine runtimes, models, voices and credentials are NOT bundled.\n'
        'This is not equivalent to the locally tested Windows engine bundle.\n'
        'FFmpeg and FFprobe must be available separately on PATH.\n'
        'Windows needs WebView2 and Visual C++ runtimes. Linux uses the Qt backend.\n'
        'The macOS preview is not Developer ID signed or notarized.\n'
        'macOS writable-data layout/signing and native engine support need further validation.\n'
        'These are development previews, not approved public releases.\n'
        'Application licensing and component distribution review remain pending.\n')
    (base/'START_HERE.txt').write_text(status,encoding='utf-8')
    return base,payload


def archive(base,target):
    output=ROOT/'release-assets'
    output.mkdir(exist_ok=True)
    manifest=[]
    for path in sorted(base.rglob('*')):
        if path.is_symlink():
            if not path.resolve().is_relative_to(base):
                raise RuntimeError('Archive link leaves candidate: '+str(path))
            manifest.append(dict(path=path.relative_to(base).as_posix(),symlink=os.readlink(path)))
        elif path.is_file():
            manifest.append(dict(path=path.relative_to(base).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    (base/'candidate-manifest.json').write_text(json.dumps(dict(target=target,scope='desktop-preview',
        release_ready=False,files=manifest),indent=2),encoding='utf-8')
    if sys.platform=='win32':
        result=output/(base.name+'.zip')
        with zipfile.ZipFile(result,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as bundle:
            for path in base.rglob('*'):
                if path.is_file():
                    bundle.write(path,base.name+'/'+path.relative_to(base).as_posix())
        with zipfile.ZipFile(result) as bundle:
            if bundle.testzip() is not None:
                raise RuntimeError('ZIP readback failed')
    else:
        result=output/(base.name+'.tar.gz')
        if result.exists():
            raise RuntimeError('Archive already exists')
        with tarfile.open(result,'w:gz') as bundle:
            bundle.add(base,arcname=base.name)
        with tarfile.open(result,'r:gz') as bundle:
            for member in bundle:
                if member.isfile():
                    with bundle.extractfile(member) as stream:
                        while stream.read(1024*1024): pass
    (output/(result.name+'.sha256')).write_text(sha(result)+'  '+result.name+'\n',encoding='ascii')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('target',choices=('windows-x64','linux-x64','macos-arm64','macos-x64'))
    args=parser.parse_args()
    base,payload=assemble(args.target)
    executable=(base/'ReflowStudio.app/Contents/MacOS/ReflowStudio' if sys.platform=='darwin'
                else base/('ReflowStudio.exe' if sys.platform=='win32' else 'ReflowStudio'))
    report=ROOT/'build'/('ci-'+args.target+'-smoke.json')
    env={**os.environ,'PYSTRAY_BACKEND':'dummy'}
    result=subprocess.run([str(executable),'--verify-package',str(report)],env=env,timeout=240)
    if result.returncode or not json.loads(report.read_text(encoding='utf-8')).get('passed'):
        raise RuntimeError('Native executable model-free smoke check failed')
    # Remove only empty test folders and specifically named fresh test state.
    for name in ('models','outputs','temp','.reflow-instance.lock','hardware_profile.json','ui_preferences.json'):
        item=payload/name
        if not item.resolve().is_relative_to(base):
            raise RuntimeError('Test cleanup escaped candidate')
        if item.is_dir():
            for child in sorted(item.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                if child.is_dir(): child.rmdir()
                else: raise RuntimeError('Unexpected generated content: '+str(child))
            item.rmdir()
        elif item.is_file(): item.unlink()
    if sys.platform=='darwin':
        subprocess.run(['codesign','--force','--deep','--sign','-',str(base/'ReflowStudio.app')],check=True)
    print(str(archive(base,args.target)),flush=True)


if __name__=='__main__':
    main()
