"""Local artifact shapes and cloud configuration accepted by bundled adapters."""
import json
from pathlib import Path
from urllib.parse import urlsplit


def _file(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Required model artifact is missing/empty: ' + str(path))
    with path.open('rb') as stream:
        head = stream.read(256).lstrip().lower()
    if head.startswith((b'<html', b'<!doctype html')):
        raise ValueError('Model artifact is an HTML page: ' + str(path))
    return path


def _json(path):
    with _file(path).open(encoding='utf-8') as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError('Model configuration must be an object: ' + str(path))
    return value


def local_contract(stage, path, preset=None):
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError('Selected model has no installed artifact path')
    root = Path(path)
    if stage == 'stt':
        if preset == 'whisper_turbo':
            from core.whisper_turbo_assets import validate_assets
            return validate_assets(root)
        _file(root / 'model.bin')
        _json(root / 'config.json')
        return {'adapter': 'faster_whisper'}
    if stage == 'translation':
        config = _json(root / 'config.json')
        if config.get('model_type') == 'IndicTrans':
            from core.indictrans2_assets import validate_assets
            return validate_assets(root)
        tokenizer = _json(root / 'tokenizer_config.json')
        if config.get('model_type') not in ('m2m_100', 'nllb-moe') or not str(tokenizer.get('tokenizer_class', '')).startswith('Nllb'):
            raise ValueError('Local translation requires an NLLB checkpoint/tokenizer')
        if not any(root.glob('*.safetensors')) and not any(root.glob('pytorch_model*.bin')):
            raise ValueError('NLLB weights are missing')
        return {'adapter': 'nllb'}
    if stage == 'tts':
        config = _json(root / 'config.json')
        if config.get('model_type') == 'inf5':
            if config.get('architectures') != ['INF5Model']:
                raise ValueError('IndicF5 configuration has an unsupported architecture')
            return {'adapter': 'indicf5', 'checkpoint_path': str(_file(root / 'model.safetensors')),
                    'vocab_path': str(_file(root / 'checkpoints/vocab.txt')),
                    'supported_languages': ['hi'], 'recipe': 'IndicF5_DiT_1024_22'}
        if config.get('model') != 'xtts':
            raise ValueError('Local TTS requires an XTTS configuration')
        _file(root / 'model.pth')
        _json(root / 'vocab.json')
        return {'adapter': 'xtts'}
    if stage == 'voice' and preset == 'f5tts':
        canonical = root / 'F5TTS_v1_Base' / 'model_1250000.safetensors'
        checkpoints = ([root] if root.is_file() else [canonical] if canonical.is_file()
                       else list(root.rglob('*.safetensors')) + list(root.rglob('*.pt')))
        if len(checkpoints) != 1:
            raise ValueError('F5 requires one explicitly selected checkpoint; repository variants are ambiguous')
        vocab = list(root.rglob('vocab.txt'))
        if canonical.is_file() and (canonical.parent / 'vocab.txt').is_file():
            vocab = [canonical.parent / 'vocab.txt']
        if not vocab:
            vocab = [Path(__file__).resolve().parents[1] / 'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/examples/vocab.txt']
        if len(vocab) != 1:
            raise ValueError('F5 requires one vocabulary file')
        return {'adapter': 'f5tts', 'checkpoint_path': str(_file(checkpoints[0])),
                'vocab_path': str(_file(vocab[0])), 'recipe': 'F5TTS_v1_Base',
                'supported_languages': ['en', 'zh']}
    if stage == 'voice':
        _file(root)
        if root.suffix.lower() != '.pth':
            raise ValueError('RVC requires an inference .pth checkpoint')
        import torch
        checkpoint = torch.load(str(root), map_location='cpu', weights_only=True)
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get('config'), list) or len(checkpoint['config']) < 18:
            raise ValueError('RVC requires an inference checkpoint with embedded configuration')
        weights = checkpoint.get('weight')
        if not isinstance(weights, dict) or 'emb_g.weight' not in weights or 'enc_p.emb_phone.weight' not in weights:
            raise ValueError('RVC checkpoint lacks required inference weights')
        channels = weights['enc_p.emb_phone.weight'].shape[1]
        detected = 'v1' if channels == 256 else 'v2' if channels == 768 else None
        if detected is None or checkpoint.get('version', detected) != detected:
            raise ValueError('RVC checkpoint architecture/version is unsupported or inconsistent')
        return {'adapter': 'rvc', 'checkpoint_path': str(root), 'rvc_version': detected}
    if stage == 'enhancer':
        candidate = root / 'GFPGANv1.4.pth' if root.is_dir() else root
        _file(candidate)
        if candidate.suffix.lower() != '.pth':
            raise ValueError('GFPGAN requires a .pth checkpoint')
        return {'adapter': 'gfpgan', 'checkpoint_path': str(candidate)}
    if stage == 'lipsync':
        if root.is_file() and root.suffix.lower() == '.pth':
            return {'adapter': 'wav2lip', 'checkpoint_path': str(_file(root))}
        _file(root / 'musetalkV15/unet.pth')
        _json(root / 'musetalkV15/musetalk.json')
        return {'adapter': 'musetalk'}
    if stage in ('filter', 'profanity_filter'):
        if stage == 'filter' and preset != 'image_classifier':
            raise ValueError('Connected local visual models must declare the image_classifier adapter')
        config = _json(root / 'config.json')
        from core.providers.label_contract import positive_index
        labels = config.get('id2label', {})
        if stage == 'filter':
            positive_index(labels, {'nsfw', 'unsafe'}, {'normal', 'sfw', 'safe', 'not_nsfw', 'non_nsfw'})
        else:
            positive_index(labels, {'toxic', 'toxicity'}, {'neutral', 'non_toxic', 'not_toxic', 'non_toxicity'})
        if not list(root.glob('*.safetensors')) and not list(root.glob('pytorch_model*.bin')):
            raise ValueError('Classifier weights are missing')
        return {'adapter': 'image_classifier' if stage == 'filter' else 'text_classifier'}
    raise ValueError('Unsupported local model stage: ' + str(stage))


def cloud_contract(stage, url, preset, config=None, voice_id=None):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Service URL must use HTTP(S) without embedded credentials')
    presets = {'stt': ('custom', 'openai_whisper'), 'translation': ('custom', 'openai_chat'),
               'tts': ('custom', 'openai_tts', 'elevenlabs_tts'),
               'voice': ('custom', 'elevenlabs_sts'), 'profanity_filter': ('custom', 'openai_chat'),
               'enhancer': ('custom',), 'filter': ('custom',), 'lipsync': ('custom',)}
    if preset not in presets.get(stage, ()):
        raise ValueError('Unsupported service preset for this stage')
    if config is not None and not isinstance(config, dict):
        raise ValueError('Service configuration must be an object')
    if preset in ('elevenlabs_sts', 'elevenlabs_tts') and not (voice_id or (config or {}).get('voice_id')):
        raise ValueError('ElevenLabs requires a service voice ID, distinct from its display name')
    return {stage + '_request': dict(config or {}), 'voice_id': voice_id or (config or {}).get('voice_id')}
