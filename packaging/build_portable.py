"""Assemble the current Windows portable setup without personal data or weights.

The default writes a reviewable size manifest. --output creates a NEW directory;
it never deletes or replaces an existing build. Optional environments are
explicitly selected and remain separate from the core size calculation.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ('main.py', 'config.py', 'Launch_Reflow.bat', 'README.txt', 'requirements.txt', 'LICENSE.txt', 'assets/icon.ico', 'assets/icon.png')
TREES = ('bridge', 'core', 'frontend/dist', 'ffmpeg', 'build/windows-portable')
WEIGHT_SUFFIXES = {'.pth', '.pt', '.onnx', '.safetensors', '.th', '.bin'}
XTTS_PROFILE = 'xtts-security-candidate'
XTTS_LOCK = 'docs/validation/2026-10-13-xtts-security-cpu-lock-review.json'
RECOGNITION_PROFILE = 'recognition-candidate'
RECOGNITION_LOCK = 'docs/validation/2026-10-15-recognition-candidate-lock-review.json'
TRANSLATION_PROFILE='translation-candidate'
TRANSLATION_PLAN='docs/validation/2026-10-16-m2m100-runtime-proposal.json'
VISUAL_PROFILE='visual-candidate'
VISUAL_LOCK='docs/validation/2026-10-16-visual-runtime-lock-review.json'
SEPARATION_PROFILE='separation-candidate'
SEPARATION_LOCK='docs/validation/2026-10-16-separation-runtime-lock-review.json'


def copy_entries(files, output, workers=4):
    """Bound both I/O concurrency and queued tasks; preserve copy errors."""
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('Portable copy workers must be between 1 and 8')
    def copy(item):
        source, relative, _ = item
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for offset in range(0, len(files), 64):
            list(executor.map(copy, files[offset:offset + 64]))
    # The caller publishes the manifest only after every copy succeeds.


def entries(profiles=(), trees=None):
    if VISUAL_PROFILE in profiles:
        sys.path.insert(0,str(ROOT))
        from core.visual_runtime import validate
        validate(ROOT)
        yield ROOT/VISUAL_LOCK,VISUAL_LOCK,VISUAL_PROFILE
    if SEPARATION_PROFILE in profiles:
        sys.path.insert(0,str(ROOT))
        from core.separation_runtime import validate
        validate(ROOT)
        yield ROOT/SEPARATION_LOCK,SEPARATION_LOCK,SEPARATION_PROFILE
    if TRANSLATION_PROFILE in profiles:
        sys.path.insert(0,str(ROOT))
        from core.m2m100_runtime import validate
        validate(ROOT)
        yield ROOT/TRANSLATION_PLAN,TRANSLATION_PLAN,TRANSLATION_PROFILE
    if RECOGNITION_PROFILE in profiles:
        sys.path.insert(0, str(ROOT))
        from core.recognition_runtime import validate
        validate(ROOT)
        yield ROOT / RECOGNITION_LOCK, RECOGNITION_LOCK, RECOGNITION_PROFILE
    if XTTS_PROFILE in profiles:
        sys.path.insert(0, str(ROOT))
        from core.xtts_runtime import validate
        validate(ROOT)  # An unverified recipe cannot enter a portable candidate.
        yield ROOT / XTTS_LOCK, XTTS_LOCK, XTTS_PROFILE
    for name in ROOT_FILES:
        path = ROOT / name
        if not path.is_file():
            raise RuntimeError(f'Missing portable application file: {name}')
        yield path, name, 'core'
    trees = [(name, 'core') for name in (TREES if trees is None else trees)] + [(f'runtime_profiles/{profile}', profile) for profile in profiles]
    for name, group in trees:
        base = ROOT / name
        if not base.is_dir():
            raise RuntimeError(f'Missing portable component: {name}')
        for directory, children, files in os.walk(base, followlinks=False):
            parent = Path(directory)
            for item in [parent, *(parent / child for child in children + files)]:
                if item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise RuntimeError(f'Portable build refuses reparse points: {item}')
            children[:] = [child for child in children if child not in {'__pycache__', '.cache', '.hf-cache', 'node_modules', '.pytest_cache'}]
            # These source/installed-package directories contain model weights,
            # not inference code. Reflow recovers them when a feature is used.
            if name == 'core' and parent.relative_to(ROOT).as_posix() in {'core/MuseTalk/models', 'core/Wav2Lip/checkpoints'}:
                children[:] = []
                continue
            for filename in files:
                path = parent / filename
                if path.suffix.lower() in {'.pyc', '.pyo', '.lock', '.tmp', '.whl'}:
                    continue
                if name in {'core', 'build/windows-portable'} and path.suffix.lower() in WEIGHT_SUFFIXES:
                    # python packages can contain unrelated .bin resources;
                    # exclude only known model storage inside the runtime.
                    if name == 'core' or 'base_model' in path.parts:
                        continue
                yield path, path.relative_to(ROOT).as_posix(), group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--copy-workers', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--profile', action='append', choices=['vision', 'f5', 'musetalk', XTTS_PROFILE, RECOGNITION_PROFILE,TRANSLATION_PROFILE,SEPARATION_PROFILE,VISUAL_PROFILE], default=[])
    parser.add_argument('--manifest', type=Path, default=ROOT / 'docs/validation/2026-10-04-portable-manifest.json')
    args = parser.parse_args()
    files = list(entries(sorted(set(args.profile))))
    groups = {}
    for source, _, group in files:
        groups[group] = groups.get(group, 0) + source.stat().st_size
    report = {'platform': 'windows', 'python_version': '3.10.11', 'bytes_by_component': groups,
              'core_under_500_MB': groups['core'] <= 500_000_000,
              'downloaded_model_weights_included': False, 'vendor_bundled_engine_assets_included': True,
              'personal_state_included': False,
              'optional_profiles': sorted(set(args.profile)),
              'release_ready': False,
              'copy_workers': args.copy_workers,
              'files': [{'path': relative, 'bytes': source.stat().st_size, 'component': group} for source, relative, group in files]}
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(ROOT) or output == ROOT or output.exists():
            raise RuntimeError('Output must be a new directory inside the project')
        output.mkdir(parents=True)
        copy_entries(files, output, args.copy_workers)
        (output / 'portable-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        report['output'] = str(output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}, indent=2))


if __name__ == '__main__':
    main()
