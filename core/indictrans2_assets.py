"""Pinned local English-to-Hindi IndicTrans2 route; no network discovery."""
import hashlib
import json
from pathlib import Path
from core.python_runtime import project_root


def validate_assets(path, verify_weights=False):
    root = project_root()
    manifest = json.loads((root / 'core/indictrans2_manifest.json').read_text(encoding='utf-8'))
    path = Path(path).resolve()
    for row in manifest['files']:
        asset = path / row['name']
        if not asset.is_file() or asset.stat().st_size != row['bytes']:
            raise ValueError('Pinned IndicTrans2 asset missing or changed: '+row['name'])
        if asset.suffix != '.safetensors' or verify_weights:
            checksum = hashlib.sha256()
            with asset.open('rb') as stream:
                for block in iter(lambda: stream.read(8*1024*1024), b''):
                    checksum.update(block)
            if checksum.hexdigest() != row['sha256']:
                raise ValueError('Pinned IndicTrans2 asset identity changed: '+row['name'])
    processor = root / 'core/vendor/indictrans2/processor.py'
    if hashlib.sha256(processor.read_bytes()).hexdigest() != manifest['processor_sha256']:
        raise ValueError('Reviewed IndicTrans2 processor changed')
    return {'adapter':'indictrans2', 'model_path':str(path), 'revision':manifest['revision'],
            'processor_path':str(processor), 'supported_source_languages':['en'],
            'supported_languages':['hi']}


def isolated_interpreter():
    executable = project_root() / 'runtime_profiles/indictrans2-evaluation/python.exe'
    if not executable.is_file():
        raise RuntimeError('The existing isolated IndicTrans2 runtime is unavailable.')
    return str(executable)


def installed_path():
    return project_root() / 'models/translation/indictrans2-evaluation'
