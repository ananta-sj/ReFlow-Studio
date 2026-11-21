"""Compile only the verified Windows candidate with an existing Inno compiler."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ReflowStudio-windows-x64-desktop-preview-setup.exe'


def sha(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_payload(root):
    manifest = json.loads((root/'candidate-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('target') != 'windows-x64':
        raise RuntimeError('Not a Windows candidate')
    expected = {'candidate-manifest.json'}
    for row in manifest['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.drive:
            raise RuntimeError('Unsafe candidate inventory')
        file = root/relative
        if file.is_symlink() or not file.is_file() or sha(file) != row['sha256']:
            raise RuntimeError('Candidate changed: ' + row['path'])
        expected.add(relative.as_posix())
    actual = set()
    for file in root.rglob('*'):
        if file.is_symlink() or getattr(file.lstat(), 'st_file_attributes', 0) & 0x400:
            raise RuntimeError('Candidate inventory contains a link')
        if file.is_file():
            actual.add(file.relative_to(root).as_posix())
    if actual != expected or 'ReflowStudio.exe' not in expected:
        raise RuntimeError('Candidate inventory contains missing or unexpected files')


def compiler():
    found = shutil.which('ISCC.exe')
    if found:
        return found
    for variable in ('ProgramFiles(x86)', 'ProgramFiles'):
        for version in ('6', '7'):
            path = Path(os.environ.get(variable, 'C:/Program Files'))/f'Inno Setup {version}/ISCC.exe'
            if path.is_file():
                return str(path)
    raise RuntimeError('Preinstalled Inno Setup compiler missing; no software was downloaded')


def main():
    if sys.platform != 'win32':
        raise RuntimeError('Windows installer must be built on Windows')
    payload = ROOT/'dist/ReflowStudio-windows-x64-desktop-preview'
    validate_payload(payload)
    output = ROOT/'release-assets'
    if (output/NAME).exists():
        raise RuntimeError('Refusing to overwrite an installer')
    subprocess.run([compiler(), '/Qp', f'/DPayloadDir={payload}', f'/DOutputDir={output}',
                    str(ROOT/'packaging/windows/desktop-preview.iss')], check=True, timeout=900)
    result = output/NAME
    if not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError('Compiler did not produce the installer')
    (output/(NAME+'.sha256')).write_text(sha(result)+'  '+NAME+'\n', encoding='ascii')
    print(result)


if __name__ == '__main__':
    main()
