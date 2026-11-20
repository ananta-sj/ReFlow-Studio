"""Provision explicitly supplied, reviewed shared FFmpeg files; never download."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


def verify_shared(root, directory):
    directory=Path(directory)
    recipe=json.loads((Path(root)/'packaging/optional/ffmpeg-shared.json').read_text(encoding='utf-8'))
    if directory.is_symlink():
        raise RuntimeError('FFmpeg identity: symlink directory is not accepted')
    for name, expected in recipe['files'].items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Unsafe reviewed FFmpeg path')
        path=directory/relative
        if (not path.is_file() or path.is_symlink()
                or not path.resolve().is_relative_to(directory.resolve())
                or path.stat().st_size != expected['bytes']
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']):
            raise RuntimeError('FFmpeg file identity differs from the reviewed recipe: '+name)
    return recipe


def prepare_shared(root, profile, source):
    root=Path(root).resolve();profile=Path(profile)
    if not profile.resolve().is_relative_to(root/'runtime_profiles') or profile.is_symlink():
        raise RuntimeError('FFmpeg destination escapes runtime profiles')
    destination=profile/'ffmpeg'
    if destination.exists() or destination.is_symlink():
        verify_shared(root,destination)
        return destination
    recipe=verify_shared(root,source)
    with tempfile.TemporaryDirectory(prefix='.ffmpeg-',dir=profile) as folder:
        staged=Path(folder)/'ffmpeg';staged.mkdir()
        for name in recipe['files']:
            output=staged/name;output.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(Path(source)/name,output)
        verify_shared(root,staged)
        staged.rename(destination)
    return destination
