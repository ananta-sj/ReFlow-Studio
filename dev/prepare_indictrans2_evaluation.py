"""Prepare an isolated Windows compatibility evaluation, without model execution."""
import hashlib
import json
from pathlib import Path
import shutil
import requests

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT_REVISION = '0c607654e8b6cce897a32039df79018a1daff4e2'


def main():
    vendor = ROOT / 'dev/vendor/indictrans2-toolkit-review'
    vendor.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for name in ('LICENSE', 'setup.py', 'requirements.txt'):
        response = requests.get('https://raw.githubusercontent.com/VarunGumma/IndicTransToolkit/'
                                + TOOLKIT_REVISION + '/' + name, timeout=(10, 30))
        if response.status_code == 404 and name == 'requirements.txt':
            continue
        response.raise_for_status()
        path = vendor / (TOOLKIT_REVISION + '-' + name)
        path.write_bytes(response.content)
        artifacts.append(dict(name=name, sha256=hashlib.sha256(response.content).hexdigest()))
    source = ROOT / 'runtime_profiles/indicf5-gpu-evaluation'
    destination = ROOT / 'runtime_profiles/indictrans2-evaluation'
    if destination.exists():
        raise FileExistsError('Preserve existing translation evaluation profile')
    destination.mkdir()
    for item in source.iterdir():
        if item.is_file() and (item.suffix.lower() in {'.dll', '.pyd'} or
                             item.name in {'python.exe', 'pythonw.exe', 'python310.zip'}):
            shutil.copy2(item, destination / item.name)
    (destination / 'Lib/site-packages').mkdir(parents=True)
    (destination / 'python310._pth').write_text(
        'python310.zip\n.\nLib/site-packages\n../indicf5-gpu-evaluation/Lib/site-packages\n'
        '../indicf5-evaluation/Lib/site-packages\nimport site\n', encoding='utf-8')
    report = dict(profile='indictrans2-evaluation', status='prepared-not-ready',
                  python='3.10.11', toolkit_revision=TOOLKIT_REVISION, upstream_files=artifacts,
                  shared_profiles=['indicf5-gpu-evaluation', 'indicf5-evaluation'],
                  core_runtime_changed=False, existing_profiles_changed=False,
                  model_weights_downloaded=False, model_code_executed=False,
                  windows_support='Historical pure-Python processor compatibility evaluation only')
    (destination / 'profile.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
