"""Build a model-free, reviewable Windows test candidate using installed files.

No package installation, model downloads, default runtime changes or publishing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('portable_builder', ROOT/'packaging/build_portable.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
PROFILES = ('f5', 'vision', 'musetalk', builder.XTTS_PROFILE,
            builder.RECOGNITION_PROFILE, builder.TRANSLATION_PROFILE,
            builder.SEPARATION_PROFILE, builder.VISUAL_PROFILE)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def selected_files():
    yield ROOT/'packaging/START_HERE.txt', 'START_HERE.txt', 'core'
    for profile in ('f5', 'vision', 'musetalk'):
        folder = ROOT/'runtime_profiles'/profile
        if json.loads((folder/'profile.json').read_text())['status'] != 'ready':
            raise RuntimeError('Optional runtime is not prepared: '+profile)
    for index, (source, relative, group) in enumerate(builder.entries(PROFILES)):
        if index % 4096 == 0:
            print('Inventory: %d files (%s)' % (index, group), flush=True)
        parts = Path(relative).parts
        # Installer provenance can contain local paths. Retain package METADATA,
        # RECORD and license files; neither inference nor runtime checks use this.
        if source.name == 'direct_url.json' or source.suffix.lower() in {'.old', '.bak', '.log'}:
            continue
        if any(part in {'temp', 'results', '.git', '.codex', '.agents'} for part in parts):
            continue
        if source.name.startswith('.env') or source.suffix.lower() == '.egg-link':
            raise RuntimeError('Unexpected private/development file in package: '+relative)
        if source.name in {'settings.json', 'models.json', 'ui_preferences.json',
                           'queue_state.json', 'hardware_profile.json', 'graph.json'}:
            raise RuntimeError('Personal state in package: '+relative)
        yield source, relative, group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='ReflowStudio-Windows-RC1-2026-10-31')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.name):
        raise ValueError('Use a simple ASCII candidate name')
    output = ROOT/'dist'/args.name
    report_path = ROOT/'docs/validation'/('2026-10-31-'+args.name+'-assembly.json')
    print('Checking installed runtimes and inventory...', flush=True)
    files = list(selected_files())
    groups = {}
    for source, relative, group in files:
        groups[group] = groups.get(group, 0)+source.stat().st_size
    report = dict(platform='windows', python_version='3.10.11', optional_profiles=list(PROFILES),
                  bytes_by_component=groups, file_count=len(files), release_ready=False,
                  downloaded_model_weights_included=False, personal_state_included=False,
                  vendor_bundled_engine_assets_included=True, software_installed=False,
                  models_downloaded=False, excluded_evaluation_profiles=[
                      'desktop-candidate','xtts-candidate','indicf5-evaluation',
                      'indicf5-gpu-evaluation','indictrans2-evaluation'],
                  files=[dict(path=relative, bytes=source.stat().st_size, component=group)
                         for source, relative, group in files])
    print(json.dumps({k:v for k,v in report.items() if k != 'files'}, indent=2), flush=True)
    if not args.build:
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        return
    if output.exists() or output.is_symlink():
        raise RuntimeError('Candidate already exists; refusing replacement')
    output.mkdir(parents=True)
    started = time.monotonic()

    def copy(item):
        source, relative, group = item
        target = output/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(source)
        import shutil
        shutil.copy2(source, target)
        if sha(target) != before:
            raise RuntimeError('Copied file differs: '+relative)
        return dict(path=relative, bytes=target.stat().st_size, component=group, sha256=before)

    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for offset in range(0, len(files), 128):
            records.extend(pool.map(copy, files[offset:offset+128]))
            if offset % 2048 == 0:
                print('Copied and verified %d/%d files' % (len(records), len(files)), flush=True)
    report.update(files=records, assembly_seconds=round(time.monotonic()-started,3),
                  content_hashes_verified=True)
    (output/'portable-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Candidate assembled: '+str(output), flush=True)


if __name__ == '__main__':
    main()
