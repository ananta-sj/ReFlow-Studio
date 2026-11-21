"""Per-user Linux/macOS installation; only manifest-owned files are replaced."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

TARGETS=('linux-x64','macos-arm64','macos-x64')


def home_directory():
    return Path.home().resolve()


def sha(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def safe_path(root, relative):
    value=Path(relative)
    if value.is_absolute() or value.drive or '..' in value.parts or '\\' in relative or not value.parts:
        raise RuntimeError('Unsafe installation path')
    return root/value


def no_link_parents(file, home):
    relative=file.relative_to(home)
    current=home
    for part in relative.parts[:-1]:
        current=current/part
        if current.is_symlink():
            raise RuntimeError('Installation parent is a link')


def locations(target):
    home=home_directory()
    payload=home/('Library/Application Support/ReflowStudio/runtime' if target.startswith('macos-')
                  else '.local/share/ReflowStudio')
    return home,payload


@contextmanager
def application_idle(payload):
    import fcntl
    lock=payload/'.reflow-instance.lock'
    if lock.is_symlink():
        raise RuntimeError('Application lock is a link')
    with lock.open('a+b') as stream:
        try:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Close Reflow Studio before installing or removing it') from error
        try:
            yield
        finally:
            fcntl.flock(stream,fcntl.LOCK_UN)


def inventory(source,target):
    manifest=json.loads((source/'candidate-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('target')!=target:
        raise RuntimeError('Installer target mismatch')
    rows=[];seen=set()
    for row in manifest['files']:
        file=safe_path(source,row['path'])
        if row['path'] in seen:
            raise RuntimeError('Duplicate inventory path')
        seen.add(row['path'])
        if not file.resolve().is_relative_to(source.resolve()):
            raise RuntimeError('Inventory path leaves source')
        if 'symlink' in row:
            if not file.is_symlink() or os.readlink(file)!=row['symlink']:
                raise RuntimeError('Source link checksum mismatch')
        elif file.is_symlink() or not file.is_file() or sha(file)!=row['sha256']:
            raise RuntimeError('Source checksum mismatch')
        rows.append(row)
    return rows


def unchanged(file,row):
    if 'symlink' in row:
        return file.is_symlink() and os.readlink(file)==row['symlink']
    return file.is_file() and not file.is_symlink() and sha(file)==row['sha256']


def receipt_for(payload,target):
    file=payload/'.installation.json'
    if file.is_symlink():
        raise RuntimeError('Installation receipt is a link')
    if not file.exists():
        return dict(target=target,files=[])
    receipt=json.loads(file.read_text(encoding='utf-8'))
    if receipt.get('target')!=target:
        raise RuntimeError('Installed architecture differs; use the matching installer')
    return receipt


def install(source,target):
    home,payload=locations(target)
    rows=inventory(source,target)
    no_link_parents(payload/'placeholder',home)
    payload.mkdir(parents=True,exist_ok=True)
    with application_idle(payload):
        old=receipt_for(payload,target)
        owned={row['path']:row for row in old['files']}
        for row in old['files']:
            old_file=safe_path(home,row['path'])
            if not (old_file.is_relative_to(payload) or target.startswith('macos-') and old_file.is_relative_to(home/'Applications/ReflowStudio.app')):
                raise RuntimeError('Receipt path leaves installed application')
            no_link_parents(old_file,home)
        desktop=None
        if target=='linux-x64':
            desktop=home/'.local/share/applications/ReflowStudio.desktop'
            no_link_parents(desktop,home)
            if desktop.is_symlink():
                raise RuntimeError('Desktop entry is a link')
            command=str(payload/'ReflowStudio').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
            text=f'[Desktop Entry]\nType=Application\nName=Reflow Studio\nExec="{command}"\nIcon={payload}/assets/icon.png\nTerminal=false\nCategories=AudioVideo;\n'
            if desktop.exists() and desktop.read_text(encoding='utf-8')!=old.get('desktop'):
                raise RuntimeError('Desktop entry is unowned or modified')
        copies=[]
        for row in rows:
            if target.startswith('macos-'):
                if not row['path'].startswith('ReflowStudio.app/'):
                    continue
                destinations=[home/'Applications'/row['path']]
                marker='ReflowStudio.app/Contents/Resources/ReflowStudio/'
                if row['path'].startswith(marker):
                    if 'symlink' in row and not (source/row['path']).resolve().is_relative_to((source/marker).resolve()):
                        raise RuntimeError('Mac runtime link leaves relocatable payload')
                    destinations.append(payload/row['path'][len(marker):])
            else:
                destinations=[payload/row['path']]
            for dest in destinations:
                no_link_parents(dest,home)
                relative=dest.relative_to(home).as_posix()
                if dest.exists() or dest.is_symlink():
                    if relative not in owned:
                        raise RuntimeError('Refusing to overwrite an unowned file: '+relative)
                    if not unchanged(dest,owned[relative]):
                        raise RuntimeError('Installed program was modified; preserve it before updating: '+relative)
                copies.append((source/row['path'],dest,{**row,'path':relative}))
        # Validate all destinations before writing any program files.
        receipt=dict(target=target,files=[row for _,_,row in copies])
        if desktop is not None:
            receipt['desktop']=text
        for src,dest,row in copies:
            dest.parent.mkdir(parents=True,exist_ok=True)
            if 'symlink' in row:
                if dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(row['symlink'],target_is_directory=src.is_dir())
            else:
                shutil.copy2(src,dest)
        current={row['path'] for row in receipt['files']}
        for row in old['files']:
            file=safe_path(home,row['path'])
            no_link_parents(file,home)
            if row['path'] not in current and unchanged(file,row):
                file.unlink()
        receipt_file=payload/'.installation.json'
        temporary=payload/'.installation.json.new'
        if temporary.is_symlink():
            raise RuntimeError('Installation receipt staging is a link')
        temporary.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        temporary.replace(receipt_file)
        if desktop is not None:
            desktop.parent.mkdir(parents=True,exist_ok=True)
            desktop.write_text(text,encoding='utf-8')
    print('Installed Desktop Preview. Native testing and engine setup are still required.')


def uninstall(target):
    home,payload=locations(target)
    no_link_parents(payload/'placeholder',home)
    if not (payload/'.installation.json').is_file():
        raise RuntimeError('No matching per-user installation receipt')
    with application_idle(payload):
        receipt=receipt_for(payload,target)
        for row in receipt['files']:
            file=safe_path(home,row['path'])
            allowed=(file.is_relative_to(payload) or target.startswith('macos-') and file.is_relative_to(home/'Applications/ReflowStudio.app'))
            if not allowed:
                raise RuntimeError('Receipt path leaves installed application')
            no_link_parents(file,home)
        for row in receipt['files']:
            file=safe_path(home,row['path'])
            if unchanged(file,row):
                file.unlink()
        parents={parent for row in receipt['files'] for parent in safe_path(home,row['path']).parents
                 if parent.is_relative_to(payload) or target.startswith('macos-') and parent.is_relative_to(home/'Applications/ReflowStudio.app')}
        for parent in sorted(parents,key=lambda file:len(file.parts),reverse=True):
            try:
                parent.rmdir()  # Only empty program directories; never recursive user-data deletion.
            except OSError:
                pass
        (payload/'.installation.json').unlink()
        desktop=home/'.local/share/applications/ReflowStudio.desktop'
        if target=='linux-x64' and desktop.is_file() and not desktop.is_symlink():
            if desktop.read_text(encoding='utf-8')==receipt.get('desktop'):
                desktop.unlink()
    print('Removed unchanged program files. Settings, models, outputs and modified files were preserved.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',choices=TARGETS,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--uninstall',action='store_true')
    args=parser.parse_args()
    expected='macos-' if sys.platform=='darwin' else 'linux-' if sys.platform.startswith('linux') else ''
    if not expected or not args.target.startswith(expected):
        raise RuntimeError('Use this installer on its matching operating system')
    if hasattr(os,'geteuid') and os.geteuid()==0:
        raise RuntimeError('Run as your normal user, without sudo')
    if args.uninstall:
        uninstall(args.target)
    elif args.source:
        install(args.source.resolve(),args.target)
    else:
        parser.error('--source is required for installation')


if __name__=='__main__':
    main()
