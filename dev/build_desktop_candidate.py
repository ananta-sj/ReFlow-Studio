"""Build only the user-approved 31-package desktop candidate; preserve defaults."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev import build_xtts_runtime_candidate as helpers
PROFILE = ROOT / 'runtime_profiles/desktop-candidate'
STAGING = ROOT / 'temp/desktop-candidate-2026-10-14-staging'
OUT = ROOT / 'docs/validation'
OWNER = 'reflow.desktop.candidate.2026-10-14'
LOCK = OUT / '2026-10-13-desktop-candidate-lock-review.json'
helpers.PROFILE = PROFILE


def fetch(row):
    target = STAGING / row['filename']
    assert Path(row['filename']).name == row['filename']
    if target.exists():
        assert helpers.hash_file(target) == row['sha256']
    elif urlsplit(row['url']).scheme == 'file':
        source = Path(urllib.request.url2pathname(urlsplit(row['url']).path)).resolve()
        assert source.is_relative_to((OUT / '2026-10-13-proxy-tools-helper').resolve())
        shutil.copy2(source, target)
    else:
        parsed = urlsplit(row['url'])
        assert parsed.scheme == 'https' and parsed.hostname == 'files.pythonhosted.org'
        pending = target.with_suffix('.partial')
        try:
            opener = urllib.request.build_opener(helpers.SourcesOnly())
            with opener.open(row['url'], timeout=45) as response:
                data = response.read(row['bytes'] + 1)
            assert len(data) == row['bytes']
            pending.write_bytes(data)
            assert helpers.hash_file(pending) == row['sha256']
            pending.replace(target)
        finally:
            if pending.exists():
                pending.unlink()
    assert target.stat().st_size == row['bytes'] and helpers.hash_file(target) == row['sha256']
    return dict(filename=row['filename'], bytes=row['bytes'], sha256=row['sha256'])


def main():
    global PROFILE, STAGING, OWNER, LOCK
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['download', 'install', 'clean-staging'])
    parser.add_argument('--recognition', action='store_true')
    args = parser.parse_args()
    prefix = '2026-10-15-recognition-candidate' if args.recognition else '2026-10-14-desktop-candidate'
    expected_packages = 24 if args.recognition else 31
    if args.recognition:
        PROFILE = ROOT / 'runtime_profiles/recognition-candidate'
        STAGING = ROOT / 'temp/recognition-candidate-2026-10-15-staging'
        OWNER = 'reflow.recognition.candidate.2026-10-15'
        LOCK = OUT / '2026-10-15-recognition-candidate-lock-review.json'
        helpers.PROFILE = PROFILE
    if args.phase == 'clean-staging':
        assert STAGING.resolve().is_relative_to((ROOT / 'temp').resolve())
        assert (STAGING / '.owner').read_text() == OWNER
        assert not any(path.is_symlink() or path.stat().st_file_attributes & 1024 for path in STAGING.rglob('*'))
        size = sum(path.stat().st_size for path in STAGING.rglob('*') if path.is_file())
        shutil.rmtree(STAGING)
        (OUT / (prefix + '-staging-cleanup.json')).write_text(json.dumps(dict(removed=True, bytes=size, path=str(STAGING)), indent=2))
        print('Staging removed:', size)
        return
    lock = json.loads(LOCK.read_text())
    integrity = json.loads((OUT / ('2026-10-15-recognition-plan-integrity.json' if args.recognition else '2026-10-13-desktop-helper-lock-integrity.json')).read_text())
    assert integrity['passed'] and helpers.hash_file(LOCK) == integrity['lock_sha256']
    assert len(lock['packages']) == expected_packages and lock['metadata_closure_valid']
    assert not PROFILE.exists(), 'Preserve any existing candidate; no automatic replacement'
    if args.phase == 'download':
        STAGING.mkdir(parents=True, exist_ok=True)
        if not (STAGING / '.owner').exists():
            assert not any(STAGING.iterdir())
            (STAGING / '.owner').write_text(OWNER)
        assert (STAGING / '.owner').read_text() == OWNER
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(fetch, lock['packages']))
        (OUT / (prefix + '-downloads.json')).write_text(json.dumps(dict(
            authorization='User approved separate recognition candidate, offline conversion and tests' if args.recognition else 'User approved separate desktop candidate and deep acceptance tests',
            artifacts=receipts, total_bytes=sum(row['bytes'] for row in receipts), model_downloaded=False), indent=2))
        print('Verified artifacts:', len(receipts))
        return
    assert (STAGING / '.owner').read_text() == OWNER
    for row in lock['packages']:
        assert helpers.hash_file(STAGING / row['filename']) == row['sha256']
    PROFILE.mkdir()
    (PROFILE / '.owner').write_text(OWNER)
    receipt = dict(completed=False, candidate_only=True, defaults_changed=False, model_downloaded=False,
                   approved_packages=expected_packages, lock_sha256=helpers.hash_file(LOCK))
    try:
        bootstrap = json.loads((OUT / '2026-10-13-desktop-runtime-plan-integrity.json').read_text())['bootstrap']
        for name, row in bootstrap.items():
            source = ROOT / 'runtime_profiles/xtts-security-candidate' / name
            assert not source.is_symlink() and helpers.hash_file(source) == row['sha256']
            shutil.copy2(source, PROFILE / name)
            assert helpers.hash_file(PROFILE / name) == row['sha256']
        (PROFILE / 'python313._pth').write_text('python313.zip\n.\nLib/site-packages\nimport site\n')
        destination = PROFILE / 'Lib/site-packages'
        destination.mkdir(parents=True)
        notices = OUT / (prefix + '-notices')
        inventory = []
        for row in lock['packages']:
            with zipfile.ZipFile(STAGING / row['filename']) as archive:
                helpers.safe_members(archive, destination)
                entries = [entry for entry in archive.infolist() if not entry.is_dir() and
                           ('.dist-info/licenses/' in entry.filename.lower() or '.dist-info/' in entry.filename.lower()
                            and any(word in entry.filename.rsplit('/', 1)[-1].lower() for word in ('license', 'notice', 'copying')))]
                for entry in entries:
                    target = notices / row['name'] / entry.filename
                    assert target.resolve().is_relative_to(notices.resolve())
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
                inventory.append(dict(name=row['name'], version=row['version'], notice_files=[entry.filename for entry in entries]))
        (notices / 'inventory.json').write_text(json.dumps(inventory, indent=2))
        lines = [f"{row['name']} @ {(STAGING / row['filename']).as_uri()} --hash=sha256:{row['sha256']}" for row in lock['packages']]
        local_lock = STAGING / 'install.lock.txt'
        local_lock.write_text('\n'.join(lines) + '\n')
        command = [sys.executable, '-B', '-X', 'utf8', '-m', 'pip', '--isolated', 'install', '--no-index',
                   '--no-deps', '--no-cache-dir', '--no-compile', '--ignore-installed', '--only-binary=:all:',
                   '--python-version', '3.13', '--platform', 'win_amd64', '--implementation', 'cp', '--abi', 'cp313',
                   '--require-hashes', '--disable-pip-version-check', '--target', str(destination), '-r', str(local_lock)]
        with (OUT / (prefix + '-install.log')).open('wb') as log:
            result = subprocess.run(command, env={**os.environ, 'TEMP': str(STAGING), 'TMP': str(STAGING),
                                    'PIP_NO_INDEX': '1', 'PYTHONDONTWRITEBYTECODE': '1'}, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert result.returncode == 0, 'See retained install log'
        scripts = destination / 'bin'
        if scripts.exists():
            assert scripts.resolve().is_relative_to(PROFILE.resolve()) and not scripts.is_symlink()
            shutil.rmtree(scripts)
        receipt.update(completed=True, runtime_bytes=sum(path.stat().st_size for path in PROFILE.rglob('*') if path.is_file()))
        (PROFILE / 'profile.json').write_text(json.dumps(dict(profile=PROFILE.name, status='candidate-unverified',
            python='3.13.16', production_default=False, release_eligible=False), indent=2))
    finally:
        (OUT / (prefix + '-install.json')).write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
