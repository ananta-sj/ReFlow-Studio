"""Remove only owned candidate bytecode; retain notices present outside dist-info."""
import csv
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'runtime_profiles/recognition-candidate'
OUT = ROOT / 'docs/validation'


def main():
    assert PROFILE.resolve().is_relative_to((ROOT / 'runtime_profiles').resolve())
    assert (PROFILE / '.owner').read_text() == 'reflow.recognition.candidate.2026-10-15'
    folders = list(PROFILE.rglob('__pycache__'))
    for folder in folders:
        assert folder.resolve().is_relative_to(PROFILE.resolve())
        assert not folder.is_symlink() and not any(p.is_symlink() or p.stat().st_file_attributes & 1024 for p in folder.rglob('*'))
    size = sum(p.stat().st_size for folder in folders for p in folder.rglob('*') if p.is_file())
    for folder in folders:
        shutil.rmtree(folder)
    notices = OUT / '2026-10-15-recognition-candidate-notices'
    inventory = json.loads((notices / 'inventory.json').read_text())
    site = PROFILE / 'Lib/site-packages'
    lock = json.loads((OUT / '2026-10-15-recognition-candidate-lock-review.json').read_text())
    from packaging.utils import canonicalize_name
    by_name = {row['name']: row for row in inventory}
    for record in site.glob('*.dist-info/RECORD'):
        name = canonicalize_name(record.parent.name.rsplit('.dist-info', 1)[0].rsplit('-', 1)[0])
        if name not in by_name:
            continue
        for path, digest, length in csv.reader(record.open(encoding='utf-8', newline='')):
            basename = Path(path).name.lower()
            if not basename.startswith(('license', 'copying', 'notice', 'thirdpartynotice')):
                continue
            source = (site / path).resolve()
            assert source.is_relative_to(PROFILE.resolve()) and source.is_file()
            target = notices / name / path
            assert target.resolve().is_relative_to(notices.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if path not in by_name[name]['notice_files']:
                by_name[name]['notice_files'].append(path)
    (notices / 'inventory.json').write_text(json.dumps(inventory, indent=2))
    receipt = dict(owned_bytecode_folders_removed=len(folders), owned_bytecode_bytes_removed=size,
                   packages_with_notices=sum(bool(row['notice_files']) for row in inventory),
                   missing_package_notices=[row['name'] for row in inventory if not row['notice_files']])
    (OUT / '2026-10-15-recognition-candidate-cache-notice-cleanup.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
