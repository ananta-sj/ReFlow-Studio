"""Remove only owned GPU transfer files after package and speech verification."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    wheels = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-wheels.json').read_text())
    environment = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-environment.json').read_text())
    speech = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-user-voices-e3683178.json').read_text(encoding='utf-8'))
    if not (wheels['verified'] and wheels['dependency_requirements_satisfied'] and environment['passed'] and
            speech['completed'] and speech['trained_weights_strictly_loaded'] and speech['device']=='cuda:0'):
        raise ValueError('Package, GPU and trained speech gates must pass before transfer cleanup')
    owned = ROOT / 'temp/indicf5-gpu-wheels'
    planned = []
    for row in wheels['packages']:
        path = Path(row['wheel'])
        if path.resolve().parent != owned.resolve() or path.is_symlink() or owned.is_symlink():
            raise ValueError('Unsafe owned wheel path')
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Owned wheel changed since verification')
        planned.append((path, row['sha256']))
    original_partial = ROOT / 'temp/pip-unpack-dpbswj0s/torch-2.9.1+cu128-cp310-cp310-win_amd64.whl'
    snapshot = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-prefix-snapshot.json').read_text())
    if Path(snapshot['source']).resolve() != original_partial.resolve():
        raise ValueError('Unexpected original partial-transfer path')
    if original_partial.exists():
        if original_partial.resolve().parent.parent != (ROOT / 'temp').resolve() or original_partial.is_symlink() or original_partial.parent.is_symlink():
            raise ValueError('Unsafe owned partial path')
        planned.append((original_partial, None))
    report = dict(completed=False, user_sources_changed=False, models_changed=False,
                  runtime_packages_changed=False, removed=[])
    for path, checksum in planned:
        if getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Refuse reparse-point cleanup')
        size = path.stat().st_size
        path.unlink()
        report['removed'].append(dict(path=str(path), bytes=size, verified_wheel_sha256=checksum))
    report.update(completed=True, removed_bytes=sum(row['bytes'] for row in report['removed']))
    (ROOT / 'docs/validation/2026-10-06-indicf5-gpu-transfer-cleanup.json').write_text(json.dumps(report, indent=2))
    profile_path = ROOT / 'runtime_profiles/indicf5-gpu-evaluation/profile.json'
    profile = json.loads(profile_path.read_text())
    profile.update(trained_speech_verified=True, speech_receipt='docs/validation/2026-10-06-indicf5-gpu-user-voices-e3683178.json',
                   human_voice_quality_accepted=False, production_integrated=False)
    profile_path.write_text(json.dumps(profile, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
