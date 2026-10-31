from core.render_context import check_cancelled
"""Recover only the model files a requested feature needs.

No downloads occur at import time. Downloads use temporary files and exact
sizes when known, so an interrupted transfer is never treated as installed.
"""
import os
from pathlib import Path
import sys
import json
from core.checkpoint_hash import MUSE_PARSER_SHA256, MUSE_FACE_SHA256, require_asset_hash as _require_hash

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]

# The revisions below were captured from the installed HF download metadata.
HF = 'https://huggingface.co'
ASSETS = {
    'rvc': [
        ('base_model/hubert_base.pt', f'{HF}/Daswer123/RVC_Base/resolve/main/hubert_base.pt', 189507909),
        ('base_model/rmvpe.pt', f'{HF}/Daswer123/RVC_Base/resolve/main/rmvpe.pt', 181184272),
        ('base_model/rmvpe.onnx', f'{HF}/Daswer123/RVC_Base/resolve/main/rmvpe.onnx', 361688443),
    ],
    'xtts': [
        ('models/xtts/default/model.pth', f'{HF}/coqui/XTTS-v2/resolve/main/model.pth', 1867929118),
        ('models/xtts/default/config.json', f'{HF}/coqui/XTTS-v2/resolve/main/config.json', None),
        ('models/xtts/default/vocab.json', f'{HF}/coqui/XTTS-v2/resolve/main/vocab.json', None),
        ('models/xtts/default/speakers_xtts.pth', f'{HF}/coqui/XTTS-v2/resolve/main/speakers_xtts.pth', 7754818),
    ],
    'wav2lip': [
        ('core/Wav2Lip/checkpoints/Wav2Lip_GAN.pth', f'{HF}/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth', 435801865),
    ],
    'gfpgan': [
        ('gfpgan/weights/GFPGANv1.4.pth', 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth', 348632874),
        ('gfpgan/weights/parsing_parsenet.pth', 'https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth', 85331193),
        ('gfpgan/weights/detection_Resnet50_Final.pth', 'https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth', 109497761),
    ],
    'musetalk': [
        ('models/musetalk/torch-cache/hub/checkpoints/s3fd-619a316812.pth', 'https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth', None),
        ('models/musetalk/torch-cache/hub/checkpoints/2DFAN4-11f355bf06.pth.tar', 'https://www.adrianbulat.com/downloads/python-fan/2DFAN4-11f355bf06.pth.tar', None),
        ('core/MuseTalk/models/musetalkV15/unet.pth', f'{HF}/TMElyralab/MuseTalk/resolve/3ef28bc5cff08c90ad8178a25f1b570cd800170f/musetalkV15/unet.pth', 3400074924),
        ('core/MuseTalk/models/musetalkV15/musetalk.json', f'{HF}/TMElyralab/MuseTalk/resolve/3ef28bc5cff08c90ad8178a25f1b570cd800170f/musetalkV15/musetalk.json', None),
        ('core/MuseTalk/models/sd-vae/config.json', f'{HF}/stabilityai/sd-vae-ft-mse/resolve/31f26fdeee1355a5c34592e401dd41e45d25a493/config.json', None),
        ('core/MuseTalk/models/sd-vae/diffusion_pytorch_model.bin', f'{HF}/stabilityai/sd-vae-ft-mse/resolve/31f26fdeee1355a5c34592e401dd41e45d25a493/diffusion_pytorch_model.bin', 334707217),
        ('core/MuseTalk/models/whisper/config.json', f'{HF}/openai/whisper-tiny/resolve/169d4a4341b33bc18d8881c4b69c2e104e1cc0af/config.json', None),
        ('core/MuseTalk/models/whisper/preprocessor_config.json', f'{HF}/openai/whisper-tiny/resolve/169d4a4341b33bc18d8881c4b69c2e104e1cc0af/preprocessor_config.json', None),
        ('core/MuseTalk/models/whisper/pytorch_model.bin', f'{HF}/openai/whisper-tiny/resolve/169d4a4341b33bc18d8881c4b69c2e104e1cc0af/pytorch_model.bin', 151095027),
        ('core/MuseTalk/models/face-parse-bisent/79999_iter.pth', f'{HF}/ManyOtherFunctions/face-parse-bisent/resolve/0073b233a5a3c4b1377d4dbf49245017938a72b5/79999_iter.pth', 53289463),
        ('core/MuseTalk/models/face-parse-bisent/resnet18-5c106cde.pth', f'{HF}/ManyOtherFunctions/face-parse-bisent/resolve/0073b233a5a3c4b1377d4dbf49245017938a72b5/resnet18-5c106cde.pth', 46827520),
    ],
}


RECOVERY_SOURCES = json.loads((ROOT / 'core/recovery_sources.json').read_text(encoding='utf-8'))
RECOVERY_HASHES = {}
for _feature, _source in RECOVERY_SOURCES.items():
    ASSETS[_feature] = [
        (f"{_source['folder']}/{item['name']}",
         f"{HF}/{_source['repo']}/resolve/{_source['revision']}/{item['name']}", item['size'])
        for item in _source['files']
    ]
    RECOVERY_HASHES.update({f"{_source['folder']}/{item['name']}": item['sha256']
                           for item in _source['files'] if item['sha256']})


def require_asset_hash(path, expected):
    _require_hash(path, expected, check_cancelled)


def _valid(path, expected_size, expected_hash=None):
    valid = path.is_file() and (path.stat().st_size == expected_size if expected_size else path.stat().st_size > 0)
    if valid and expected_hash:
        try:
            require_asset_hash(path, expected_hash)
        except RuntimeError as exc:
            from core.render_context import RenderCancelled
            if isinstance(exc, RenderCancelled):
                raise
            return False
    return valid


def ensure_assets(feature, root=None, *, include=None):
    """Return local paths; raise on download failure rather than skip a stage."""
    if feature == 'rvc' and root is None:
        import importlib.util
        spec = importlib.util.find_spec('rvc_python')
        if spec is None:
            raise RuntimeError('RVC recovery requires the rvc-python package in the selected Python environment.')
        root = Path(spec.origin).parent
    base = Path(root) if root is not None else ROOT
    paths = []
    for relative, url, expected_size in ASSETS[feature]:
        if include is not None and relative not in include:
            continue
        check_cancelled()
        target = base / relative
        expected_hash = ((MUSE_PARSER_SHA256.get(target.name) or MUSE_FACE_SHA256.get(target.name))
                         if feature == 'musetalk' else RECOVERY_HASHES.get(relative))
        paths.append(target)
        if _valid(target, expected_size, expected_hash):
            continue
        if os.environ.get('REFLOW_OFFLINE') == '1':
            raise RuntimeError(f'Missing {feature} asset: {relative}. Restore it with dev/restore_models.py before offline use.')
        target.parent.mkdir(parents=True, exist_ok=True)
        # The shared downloader owns locking, cancellation, fsync, unique
        # staging and transfer validation. Asset size is checked before publish.
        from core.downloader import download_with_progress
        print(f'[MODELS] Downloading {feature}: {relative}', flush=True)
        for _ in download_with_progress(url, str(target), expected_size=expected_size, expected_sha256=expected_hash):
            pass
    return paths

