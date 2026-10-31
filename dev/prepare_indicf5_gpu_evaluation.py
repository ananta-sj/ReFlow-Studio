"""Prepare a GPU package overlay without copying models or modifying CPU packages."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'runtime_profiles/indicf5-evaluation'
    destination = ROOT / 'runtime_profiles/indicf5-gpu-evaluation'
    if destination.exists():
        raise FileExistsError('Preserve existing GPU evaluation profile')
    if not (source / 'Lib/site-packages/f5_tts/api.py').is_file():
        raise ValueError('Approved IndicF5 dependency profile missing')
    destination.mkdir()
    for item in source.iterdir():
        if item.is_file() and (item.suffix.lower() in {'.dll', '.pyd'} or
                             item.name in {'python.exe', 'pythonw.exe', 'python310.zip'}):
            shutil.copy2(item, destination / item.name)
    (destination / 'Lib/site-packages').mkdir(parents=True)
    (destination / 'python310._pth').write_text(
        'python310.zip\n.\nLib/site-packages\n../indicf5-evaluation/Lib/site-packages\nimport site\n', encoding='utf-8')
    (destination / 'requirements.gpu.txt').write_text(
        'torch==2.9.1\ntorchvision==0.24.1\ntorchaudio==2.9.1\n', encoding='utf-8')
    report = dict(profile='indicf5-gpu-evaluation', status='prepared-not-ready', python='3.10.11',
        shared_non_torch_dependencies=str(source / 'Lib/site-packages'),
        gpu_packages_directory=str(destination / 'Lib/site-packages'),
        dependency_profile_required=True, model_weights_duplicated=False,
        cpu_profile_changed=False, core_runtime_changed=False,
        source_python_pth_sha256=hashlib.sha256((source / 'python310._pth').read_bytes()).hexdigest(),
        package_index='https://download.pytorch.org/whl/cu128',
        readiness_requirement='Verify local CUDA torch/torchvision/torchaudio origins and actual CUDA execution before use')
    (destination / 'profile.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
