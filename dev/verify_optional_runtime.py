"""Run inside the isolated interpreter; publish readiness only after verification."""
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import wave
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


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
    handles = []
    imports = {
        'vision': ['numpy', 'cv2', 'onnxruntime', 'nudenet'],
        'f5': ['torch', 'torchaudio', 'torchcodec', 'f5_tts.api'],
        'musetalk': ['torch', 'torchvision', 'torchaudio', 'diffusers', 'transformers',
                     'face_alignment', 'librosa', 'omegaconf'],
    }
    for name in imports[profile]:
        try:
            importlib.import_module(name)
            if name == 'torch' and hasattr(os, 'add_dll_directory'):
                handles.append(os.add_dll_directory(str(ROOT / 'ffmpeg' / 'shared_libs')))
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
                with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as folder:
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
    destination = ROOT / 'docs' / 'validation' / f'2026-10-03-{profile}-runtime.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    (directory / 'profile.json').write_text(json.dumps({
        'profile': profile, 'status': 'prepared' if problems else 'ready',
        'python': '3.10.11', 'device': 'cpu'}), encoding='utf-8')
    print(json.dumps({'profile': profile, 'problems': problems, 'bytes': report['bytes']}))
    raise SystemExit(1 if problems else 0)


if __name__ == '__main__':
    main()
