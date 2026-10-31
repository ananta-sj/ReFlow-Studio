"""Refresh only the owned QA copy, never a user's original portable runtime."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('reflow_portable_builder', ROOT / 'packaging/build_portable.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
entries = builder.entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-only', action='store_true', help='Refresh code after the full runtime inventory passed')
    args = parser.parse_args()
    target = ROOT / 'dist/portable-architecture-check'
    if target.resolve() != target or not (target / 'portable-manifest.json').is_file():
        raise RuntimeError('Expected owned QA distribution and its manifest')
    prior = json.loads((target / 'portable-manifest.json').read_text(encoding='utf-8'))
    if args.app_only:
        receipt = json.loads((ROOT / 'docs/validation/2026-10-04-portable-final-refresh.json').read_text(encoding='utf-8'))
        if not receipt.get('acceptance'):
            raise RuntimeError('Application-only refresh requires a previously accepted full inventory')
    files = list(entries(trees=('bridge', 'core', 'frontend/dist') if args.app_only else None))
    updated = []
    expected = {relative for _, relative, _ in files}
    checked_directories = set()
    for source, relative, _ in files:
        destination = target / relative
        if destination.parent not in checked_directories:
            if destination.parent.resolve() != destination.parent or not destination.parent.is_relative_to(target):
                raise RuntimeError('Copy target escaped QA distribution')
            checked_directories.add(destination.parent)
        if destination.exists() and (destination.is_symlink() or getattr(destination.lstat(), 'st_file_attributes', 0) & 0x400):
            raise RuntimeError('Copy target contains a reparse point')
        changed = not destination.is_file() or source.stat().st_size != destination.stat().st_size
        if not changed and not relative.startswith(('build/', 'ffmpeg/')):
            changed = hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest()
        if changed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            updated.append(relative)
    # Remove stale assets solely from this generated frontend copy.
    removed = []
    frontend = target / 'frontend/dist'
    for artifact in frontend.rglob('*'):
        if artifact.is_symlink() or getattr(artifact.lstat(), 'st_file_attributes', 0) & 0x400:
            raise RuntimeError('QA frontend contains a reparse point')
        if artifact.is_file() and artifact.relative_to(target).as_posix() not in expected:
            removed.append(artifact.relative_to(target).as_posix())
            artifact.unlink()
    mismatches = [relative for source, relative, _ in files
                  if not (target / relative).is_file() or (target / relative).stat().st_size != source.stat().st_size]
    report = dict(output=str(target), updated=updated, removed_stale_frontend=removed,
                  inventory_files=len(files), scope='application' if args.app_only else 'full',
                  size_mismatches=mismatches, acceptance=not mismatches)
    inventory = {item['path']: item for item in prior['files']} if args.app_only else {}
    for stale in removed:
        inventory.pop(stale, None)
    inventory.update({relative: dict(path=relative, bytes=source.stat().st_size, component=group) for source, relative, group in files})
    manifest = dict(platform='windows', python_version='3.10.11', personal_state_included=False,
                    downloaded_model_weights_included=False,
                    bytes_by_component={'core': sum(item['bytes'] for item in inventory.values())},
                    files=list(inventory.values()))
    (target / 'portable-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    receipt = '2026-10-04-portable-app-refresh.json' if args.app_only else '2026-10-04-portable-final-refresh.json'
    (ROOT / 'docs/validation' / receipt).write_text(json.dumps(report, indent=2), encoding='utf-8')
    if mismatches:
        raise RuntimeError('QA copy does not match the source inventory')
    print(json.dumps({key: value for key, value in report.items() if key != 'updated'}))


if __name__ == '__main__':
    main()
