"""Reviewed repository subsets; never guess filenames for arbitrary models."""
import hashlib
import json
from pathlib import Path
from core.python_runtime import project_root


def repository_download_recipe(stage, source_url, preset):
    from core.downloader import hf_repo_id_for_url
    if (stage, hf_repo_id_for_url(source_url), preset) != ('filter', 'Falconsai/nsfw_image_detection', 'image_classifier'):
        return None
    return json.loads((project_root()/'packaging/downloads/falconsai-image-classifier.json').read_text(encoding='utf-8'))


def validate_snapshot_metadata(info, revision, expected_files):
    if info is None or getattr(info, 'sha', None) != revision:
        raise RuntimeError('Pinned repository metadata is unavailable or changed')
    siblings={f.rfilename:f for f in (info.siblings or [])}
    for name, expected in expected_files.items():
        actual=siblings.get(name)
        if actual is None or actual.size != expected['bytes']:
            raise RuntimeError('Required repository metadata is missing or changed')
        if expected.get('lfs'):
            lfs=getattr(actual,'lfs',None)
            checksum=lfs.get('sha256') if isinstance(lfs,dict) else getattr(lfs,'sha256',None)
            if checksum != expected['sha256']:raise RuntimeError('Repository weight identity changed')
        elif expected.get('blob_id') != getattr(actual,'blob_id',None):
            raise RuntimeError('Repository file identity changed')


def validate_snapshot_files(directory, expected_files):
    root=Path(directory).resolve()
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.cache' not in p.relative_to(root).parts}
    if actual != set(expected_files):raise RuntimeError('Repository artifact identity differs from the reviewed subset')
    for name, expected in expected_files.items():
        path=root/name
        if not path.resolve().is_relative_to(root) or path.is_symlink() or path.stat().st_size != expected['bytes']:
            raise RuntimeError('Repository artifact identity differs from the reviewed subset')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=expected['sha256']:raise RuntimeError('Repository artifact identity differs from the reviewed subset')
