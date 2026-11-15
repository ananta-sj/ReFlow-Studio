"""Validated CUDA overlay using the existing engine packages and model files."""
import json
import time
from email.parser import Parser
import re
from pathlib import Path

from core.python_runtime import project_root
from core.runtime_integrity import safe_path, sha, digest

STAGES = ('speech', 'translation', 'recognition', 'separate')
SOURCES = ('core/cuda_runtime.py', 'core/cuda_worker.py', 'core/cuda_providers.py',
           'core/cuda_xtts_compat.py', 'core/tts/tts_handler.py', 'core/xtts_text.py',
           'core/providers/translation/nllb_local.py', 'core/translation_completion.py',
           'core/stt/stt_handler.py', 'core/recognition_compat.py',
           'core/recognition_language.py', 'core/transcription.py', 'core/generation_control.py',
           'core/voice_conditioning.py','core/speech_generation_budget.py','core/worker_json.py')
SHARED = ('xtts-security-candidate', 'separation-candidate', 'recognition-candidate')
PTH = 'python313.zip\n.\nLib/site-packages\n'+''.join(
    f'../{name}/Lib/site-packages\n' for name in SHARED)+'import site\n'
_status_cache = None
_status_time = 0
_status_stamp = None


def recognition_dependencies(root):
    # Reuse only the recognition packages. The GPU worker has its own source
    # recipe and does not execute the CPU-only recognition worker.
    folder = safe_path(root/'runtime_profiles/recognition-candidate')
    recipe = json.loads((folder/'routing-recipe.json').read_text(encoding='utf-8'))
    lock = root/'docs/validation/2026-10-15-recognition-candidate-lock-review.json'
    if sha(lock) != recipe.get('lock_sha256'):
        raise ValueError('Recognition dependency lock changed')
    bootstrap = {name:sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')}
    if bootstrap != recipe.get('bootstrap_sha256'):
        raise ValueError('Recognition dependency interpreter changed')
    if (folder/'python313._pth').read_text() != 'python313.zip\n.\nLib/site-packages\nimport site\n':
        raise ValueError('Recognition dependency import paths changed')
    expected = {row['name']:row['version'] for row in json.loads(lock.read_text())['packages']}
    actual, records = {}, []
    for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
        headers = Parser().parsestr(path.read_text(encoding='utf-8'))
        name = re.sub(r'[-_.]+', '-', headers.get('Name', '')).lower()
        if not name or name in actual:
            raise ValueError('Invalid recognition package metadata')
        actual[name] = headers.get('Version')
        records.append((path.parent.name, sha(path)))
    if actual != expected:
        raise ValueError('Recognition dependency versions changed')
    return digest(dict(bootstrap=bootstrap, lock=sha(lock), packages=records))


def validate(stage=None, *, candidate=False, root=None):
    root = Path(root or project_root())
    try:
        folder = safe_path(root/'runtime_profiles/cuda')
        data = json.loads((folder/'profile.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('schema') != 'reflow.cuda-runtime.v1' or (folder/'.owner').read_text() != 'reflow.cuda.v1':
            raise ValueError('Unrecognized CUDA runtime')
        if (folder/'python313._pth').read_text(encoding='utf-8') != PTH:
            raise ValueError('CUDA runtime import paths changed')
        bootstrap = {name:sha(folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')}
        if data.get('bootstrap') != bootstrap:
            raise ValueError('CUDA Python bootstrap changed')
        versions = {'torch': '2.14.1+cu130', 'torchaudio': '2.11.0+cu130'}
        for package, version in versions.items():
            metadata = folder/'Lib/site-packages'/f'{package}-{version}.dist-info/METADATA'
            if not metadata.is_file() or f'Version: {version}' not in metadata.read_text(encoding='utf-8'):
                raise ValueError('CUDA package version changed: '+package)
        from core.xtts_runtime import validate as speech_base
        from core.separation_runtime import validate as separation_base
        bases = [speech_base(root)['identity'], separation_base(root)['identity'], recognition_dependencies(root)]
        sources = {name:sha(root/name) for name in SOURCES}
        identity = digest(dict(bootstrap=bootstrap, packages=data['packages'], bases=bases, sources=sources))
        receipt = data.get('gpu_validation', {})
        if not isinstance(receipt, dict) or not isinstance(receipt.get('stages', {}), dict):
            raise ValueError('Invalid CUDA validation receipt')
        tested = receipt.get('stages', {}).get(stage)
        if not candidate and (receipt.get('identity') != identity or not isinstance(tested, dict)
                              or tested.get('ok') is not True or tested.get('device') != 'cuda:0'):
            raise ValueError('CUDA model tests are still required for '+str(stage))
        if stage is not None and stage not in STAGES:
            raise ValueError('Unknown CUDA stage')
        return dict(executable=str(folder/'python.exe'), profile=str(folder), identity=identity, device='cuda:0')
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError('CUDA runtime unavailable: '+str(error)) from error


def readiness():
    global _status_cache, _status_time, _status_stamp
    root = project_root()
    paths = [root/'runtime_profiles/cuda/profile.json', *[root/name for name in SOURCES]]
    stamp = tuple((str(path), path.stat().st_mtime_ns if path.exists() else None) for path in paths)
    if _status_cache is not None and stamp == _status_stamp and time.monotonic()-_status_time < 5:
        return dict(_status_cache)
    try:
        route = validate(candidate=True)
        try:
            for stage in STAGES:
                validate(stage)
        except RuntimeError:
            result = dict(status='prepared-awaiting-tests', device='cuda:0')
        else:
            result = dict(status='ready', device='cuda:0', identity=route['identity'])
    except RuntimeError as error:
        result = dict(status='unavailable', message=str(error))
    _status_cache, _status_stamp, _status_time = result, stamp, time.monotonic()
    return dict(result)


def settings_for_device(values, device):
    values = dict(values)
    if str(device).startswith('cuda') and readiness()['status'] == 'ready':
        values.update(xtts_runtime='cuda', nllb_runtime='cuda',
                      recognition_runtime='cuda', separation_runtime='cuda')
    return values
