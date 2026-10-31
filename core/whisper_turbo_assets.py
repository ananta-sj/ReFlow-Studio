"""Exact existing Whisper turbo checkpoint and isolated runtime."""
import hashlib
import json
from pathlib import Path
from core.python_runtime import project_root


def installed_path():
    return project_root()/'models/f5/reference-asr'


def validate_assets(path, verify_weights=False):
    manifest = json.loads((project_root()/'core/whisper_turbo_manifest.json').read_text(encoding='utf-8'))
    path = Path(path).resolve()
    for row in manifest['files']:
        asset = path/row['name']
        if not asset.is_file() or asset.stat().st_size != row['bytes']:
            raise ValueError('Whisper turbo asset missing or changed: '+row['name'])
        if asset.suffix != '.safetensors' or verify_weights:
            digest = hashlib.sha256()
            with asset.open('rb') as stream:
                for block in iter(lambda: stream.read(8*1024*1024), b''):
                    digest.update(block)
            if digest.hexdigest() != row['sha256']:
                raise ValueError('Whisper turbo asset identity changed: '+row['name'])
    return dict(adapter='whisper_turbo',model_path=str(path),revision=manifest['revision'])


def isolated_interpreter():
    from core.providers.tts.indicf5_local import isolated_interpreter as speech_interpreter
    return speech_interpreter('cuda:0')
