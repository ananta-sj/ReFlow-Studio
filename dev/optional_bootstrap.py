"""Prepare reviewed standalone Python without replacing an existing profile."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import tarfile
import tempfile


def prepare_modern(root, name, archive=None):
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("This reviewed optional runtime supports Windows x64 only")
    root = Path(root).resolve()
    if name not in {'musetalk', 'f5'}:
        raise ValueError('Unknown modern runtime profile')
    parent = root/'runtime_profiles'
    destination = parent/name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'Preserve existing profile: {destination}')
    recipe = json.loads((root/'packaging/optional/python-runtime.json').read_text(encoding='utf-8'))
    archive = Path(archive) if archive else root/'build/optional-python'/recipe['filename']
    if not archive.is_file() or archive.is_symlink():
        raise RuntimeError('Provide the reviewed Python archive with --python-archive; see packaging/optional/python-runtime.json')
    checksum = hashlib.sha256()
    with archive.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            checksum.update(block)
    if archive.stat().st_size != recipe['bytes'] or checksum.hexdigest() != recipe['sha256']:
        raise RuntimeError('Python archive identity differs from the reviewed recipe')
    parent.mkdir(exist_ok=True)
    if not parent.resolve().is_relative_to(root):
        raise RuntimeError('Runtime directory escapes project')
    lock = parent/(name+'.prepare-lock')
    with lock.open('x', encoding='utf-8') as stream:
        stream.write('reflow.optional-bootstrap.v1')
    try:
        with tempfile.TemporaryDirectory(prefix='.prepare-'+name+'-', dir=parent) as temporary:
            staging = Path(temporary)
            with tarfile.open(archive, 'r:gz') as bundle:
                members = bundle.getmembers()
                if sum(member.size for member in members) > 256*1024*1024:
                    raise RuntimeError('Python archive expands beyond the reviewed limit')
                for member in members:
                    path = Path(member.name)
                    if ('\\' in member.name or path.is_absolute() or '..' in path.parts
                            or not path.parts or path.parts[0] != 'python'
                            or not (member.isfile() or member.isdir())):
                        raise RuntimeError('Unsafe Python archive member')
                bundle.extractall(staging, filter='data')
            prepared = staging/'python'
            if not (prepared/'python.exe').is_file():
                raise RuntimeError('Python archive layout changed')
            (prepared/'Lib/site-packages').mkdir(parents=True, exist_ok=True)
            (prepared/'python311._pth').write_text(
                'python311.zip\n.\nDLLs\nLib\nLib/site-packages\n', encoding='utf-8')
            (prepared/'profile.json').write_text(json.dumps(dict(profile=name, status='prepared',
                python=recipe['python'], device='cpu', bootstrap_sha256=recipe['sha256'])), encoding='utf-8')
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f'Preserve existing profile: {destination}')
            prepared.rename(destination)
    finally:
        lock.unlink()
    return destination
