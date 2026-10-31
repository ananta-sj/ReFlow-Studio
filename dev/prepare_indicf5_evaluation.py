"""Create an isolated IndicF5 evaluation profile from approved F5 dependencies."""
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'runtime_profiles/f5'
    destination = ROOT / 'runtime_profiles/indicf5-evaluation'
    metadata = json.loads((source / 'profile.json').read_text(encoding='utf-8'))
    if metadata.get('status') != 'ready':
        raise ValueError('Existing F5 dependency runtime is not ready')
    if destination.exists():
        raise FileExistsError('Preserve existing IndicF5 evaluation profile')
    started = time.monotonic()
    destination.mkdir()
    for item in source.iterdir():
        if item.is_file() and (item.suffix.lower() in {'.dll', '.pyd'} or
                             item.name in {'python.exe', 'pythonw.exe', 'python310.zip', 'python310._pth'}):
            shutil.copy2(item, destination / item.name)
    def ignore(path, names):
        return [name for name in names if name == '__pycache__' or name.endswith('.pyc') or
                name == 'f5_tts' or (name.startswith('f5_tts-') and name.endswith('.dist-info'))]
    shutil.copytree(source / 'Lib/site-packages', destination / 'Lib/site-packages', ignore=ignore)
    shutil.copy2(source / 'requirements.lock.txt', destination / 'inherited-dependencies.txt')
    report = dict(profile='indicf5-evaluation', status='prepared', python='3.10.11', device='cpu',
                  source_dependencies=str(source), core_runtime_changed=False,
                  generic_f5_changed=False, copied_generic_f5_package=False,
                  elapsed_seconds=round(time.monotonic()-started, 3))
    (destination / 'profile.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
