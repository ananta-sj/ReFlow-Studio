"""Run inside the isolated interpreter; publish readiness only after verification."""
import importlib
from importlib import metadata
import json
import hashlib
import re
import os
from pathlib import Path
import sys
import wave
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def locked_package_problems(lock, installed):
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    actual = {normalize(name): version for name, version in installed.items()}
    expected = {}
    for line in lock.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)(?:\s|$)', line)
        if not match:
            raise ValueError('Unsupported reviewed lock entry')
        expected[normalize(match[1])] = match[2]
    if not expected:
        raise ValueError('Reviewed engine lock is empty')
    problems = [f'Lock mismatch: {name} needs {version}, found {actual.get(name, "missing")}'
                for name, version in expected.items() if actual.get(name) != version]
    problems.extend(f'Unreviewed package: {name}' for name in actual if name not in expected and name != 'pip')
    return problems


def main():
    profile = sys.argv[1]
    directory = ROOT / 'runtime_profiles' / profile
    os.environ['HF_HOME'] = str(ROOT / 'models' / profile / 'cache')
    os.environ['TORCH_HOME'] = str(ROOT / 'models' / profile / 'torch-cache')
    if Path(sys.executable).resolve() != (directory / 'python.exe').resolve():
        raise RuntimeError('Verification must use the profile interpreter')
    from packaging.requirements import Requirement
    problems = []
    distributions = list(metadata.distributions())
    for distribution in distributions:
        for value in distribution.requires or []:
            requirement = Requirement(value)
            if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
                continue
            try:
                version = metadata.version(requirement.name)
                if requirement.specifier and version not in requirement.specifier:
                    problems.append(f'{distribution.metadata["Name"]}: {requirement} (installed {version})')
            except metadata.PackageNotFoundError:
                problems.append(f'{distribution.metadata["Name"]}: missing {requirement}')
    profile_path = directory/'profile.json'
    profile_metadata = json.loads(profile_path.read_text(encoding='utf-8'))
    if profile in {'musetalk', 'f5'}:
        recipe = json.loads((ROOT/'packaging/optional/python-runtime.json').read_text(encoding='utf-8'))
        actual_python = '.'.join(map(str, sys.version_info[:3]))
        if (profile_metadata.get('profile') != profile
                or profile_metadata.get('bootstrap_sha256') != recipe['sha256']
                or actual_python != recipe['python']):
            problems.append('Runtime does not match the reviewed Python bootstrap')
        if not (sys.flags.isolated and sys.flags.ignore_environment and sys.flags.no_user_site):
            problems.append('Runtime must use isolated Python startup')
    lock = ROOT/'packaging/optional'/(profile+'.lock.txt')
    if profile in {'musetalk', 'f5'}:
        problems.extend(locked_package_problems(lock, {d.metadata['Name']: d.version for d in distributions}))
    if profile == 'f5':
        try:
            from dev.optional_ffmpeg import verify_shared
            verify_shared(ROOT, directory/'ffmpeg')
        except (OSError, ValueError, RuntimeError) as exc:
            problems.append('Shared decoder runtime: '+str(exc))
    handles = []
    imports = {
        'vision': ['numpy', 'cv2', 'onnxruntime', 'nudenet'],
        'f5': ['torch', 'torchaudio', 'torchcodec', 'f5_tts.api'],
        'musetalk': ['torch', 'torchvision', 'torchaudio', 'diffusers', 'transformers',
                     'face_alignment', 'librosa', 'omegaconf'],
    }
    for name in imports[profile]:
        try:
            if name == 'f5_tts.api':
                from core.f5_imports import load_f5_api
                load_f5_api()
            else:
                importlib.import_module(name)
            if name == 'torch' and profile == 'f5' and hasattr(os, 'add_dll_directory') and (directory/'ffmpeg/bin').is_dir():
                handles.append(os.add_dll_directory(str(directory/'ffmpeg/bin')))
        except Exception as exc:
            problems.append(f'Import {name}: {exc}')
    if not problems:
        try:
            if profile in ('f5', 'musetalk'):
                import torch
                result = torch.nn.functional.conv2d(torch.ones(1, 1, 8, 8), torch.ones(1, 1, 3, 3))
                if result.shape != (1, 1, 6, 6) or not torch.all(result == 9):
                    raise RuntimeError('CPU convolution probe failed')
            if profile == 'vision':
                import numpy as np
                from nudenet import NudeDetector
                NudeDetector().detect(np.zeros((64, 64, 3), dtype=np.uint8))
            elif profile == 'f5':
                from torchcodec.decoders import AudioDecoder
                with tempfile.TemporaryDirectory(dir=directory) as folder:
                    audio = Path(folder) / 'verify.wav'
                    with wave.open(str(audio), 'wb') as stream:
                        stream.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                        stream.writeframes(b'\0\0' * 2400)
                    samples = AudioDecoder(str(audio)).get_all_samples()
                    if samples.data.numel() == 0:
                        raise RuntimeError('Audio decoder returned no samples')
            else:
                sys.path.insert(0, str(ROOT / 'core' / 'MuseTalk'))
                importlib.import_module('scripts.inference')
        except Exception as exc:
            problems.append(f'Feature probe: {exc}')
    report = {'profile': profile, 'python': sys.version, 'executable': sys.executable,
              'sys_path': sys.path, 'packages': sorted(
                  f'{d.metadata["Name"]}=={d.version}' for d in distributions),
              'problems': problems,
              'checkpoint_render_verified': False,
              'bytes': sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
              'real_model_inference_verified': profile == 'vision' and not problems}
    destination = directory / 'verification.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    profile_path = directory/'profile.json'
    profile_metadata = json.loads(profile_path.read_text(encoding='utf-8'))
    profile_metadata.update(profile=profile, status='prepared' if problems else 'ready',
                    python='.'.join(map(str, sys.version_info[:3])), device='cpu')
    if profile in {'musetalk', 'f5'} and not problems:
        profile_metadata['lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
    profile_path.write_text(json.dumps(profile_metadata), encoding='utf-8')
    print(json.dumps({'profile': profile, 'problems': problems, 'bytes': report['bytes']}))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
