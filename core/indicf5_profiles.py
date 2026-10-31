"""Discover and preview confirmed local IndicF5 voices without loading a model."""
import base64
import re
from pathlib import Path

import config
from core.model_contract import local_contract
from core.providers.tts.indicf5_local import load_reference_profile, isolated_interpreter


def profile(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier):
        raise ValueError('Invalid Hindi voice identifier.')
    root = (Path(config.MODELS_DIR) / 'indicf5' / 'references').resolve()
    path = (root / identifier / 'profile.json').resolve()
    if not path.is_relative_to(root):
        raise ValueError('Hindi voice profile is outside its library.')
    return load_reference_profile(path)


def available():
    root = Path(config.MODELS_DIR) / 'indicf5' / 'references'
    result = []
    if root.is_dir():
        for folder in sorted(root.iterdir()):
            if folder.is_dir():
                try:
                    item = profile(folder.name)
                    result.append(dict(id=folder.name, name=folder.name.replace('_', ' ').title(),
                        text=item['reference_text'], reference_audio=item['reference_audio']))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
    devices = []
    for device in ('cuda:0', 'cpu'):
        try:
            isolated_interpreter(device)
            devices.append(device)
        except (OSError, ValueError, RuntimeError):
            pass
    try:
        model_path()
        ready, message = True, ''
    except (OSError, ValueError) as exc:
        ready, message = False, str(exc)
    return dict(profiles=result, devices=devices, model_ready=ready, message=message)


def model_path():
    path = Path(config.MODELS_DIR) / 'indicf5' / 'evaluation' / 'assets'
    if local_contract('tts', str(path), 'indicf5')['adapter'] != 'indicf5':
        raise ValueError('The local Hindi speech model is unavailable.')
    return str(path.resolve())


def preview(identifier):
    item = profile(identifier)
    audio = Path(item['reference_audio'])
    if audio.suffix.lower() != '.wav' or audio.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Hindi reference preview must be a WAV smaller than 8 MB.')
    from core.audio_utils import load_speech_audio
    load_speech_audio(str(audio))
    return 'data:audio/wav;base64,' + base64.b64encode(audio.read_bytes()).decode('ascii')
