"""Merge the evaluated packages together so shared Python namespaces survive."""
from importlib.metadata import distributions
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT/'runtime_profiles/speaker-diarization'
if (folder/'.owner').read_text() != 'reflow.speaker-evaluation.v1':
    raise RuntimeError('Unowned speaker environment')
packages = folder/'Lib/site-packages'
requirements = sorted({dist.metadata['Name']+'=='+dist.version for dist in distributions(path=[str(packages)])})
with tempfile.TemporaryDirectory(prefix='speaker-merge-', dir=ROOT/'build') as stage:
    subprocess.run([str(ROOT/'build/windows-portable/python.exe'), '-m', 'pip', '--isolated',
        'install', '--index-url', 'https://pypi.org/simple', '--no-deps', '--no-compile',
        '--only-binary=:all:', '--python-version', '3.13', '--platform', 'win_amd64',
        '--implementation', 'cp', '--abi', 'cp313', '--target', stage, *requirements], check=True)
    shutil.copytree(stage, packages, dirs_exist_ok=True)
if not (packages/'pyannote/audio/core/pipeline.py').is_file():
    raise RuntimeError('Speaker namespace merge did not restore pyannote.audio')
print('Speaker package namespaces merged; shared runtimes unchanged.', flush=True)
