"""Install the approved CUDA wheels in a separate Python 3.13 overlay."""
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
PACKAGES = {'torch': '2.14.1+cu130', 'torchaudio': '2.11.0+cu130'}
SHARED = ('xtts-security-candidate', 'separation-candidate', 'recognition-candidate')


def official_wheel(package, version):
    index = f'https://download.pytorch.org/whl/cu130/{package}/'
    with urllib.request.urlopen(index, timeout=60) as response:
        page = response.read().decode()
    expected = f'{package}-{version}-cp313-cp313-win_amd64.whl'
    for href in re.findall(r'href="([^"]+)"', page):
        url = urllib.parse.urljoin(index, html.unescape(href))
        parsed = urllib.parse.urlsplit(url)
        if urllib.parse.unquote(Path(parsed.path).name) == expected:
            if parsed.hostname not in ('download.pytorch.org', 'download-r2.pytorch.org'):
                raise ValueError('Unexpected wheel host')
            sha = urllib.parse.parse_qs(parsed.fragment).get('sha256', [None])[0]
            if not sha or len(sha) != 64:
                raise ValueError('Official wheel has no checksum')
            return url.split('#')[0], expected, sha
    raise ValueError('Compatible CUDA wheel not found: '+expected)


def download(url, path, expected):
    pending = path.with_suffix('.part')
    offset = pending.stat().st_size if pending.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
    with urllib.request.urlopen(request, timeout=120) as response:
        if offset and response.status != 206:
            offset = 0
        total = offset+int(response.headers.get('Content-Length', 0))
        with pending.open('ab' if offset else 'wb') as stream:
            last = offset
            while block := response.read(1024*1024):
                stream.write(block)
                offset += len(block)
                if offset-last >= 128*1024*1024:
                    print(path.name, round(offset/1024**2), '/', round(total/1024**2), 'MB', flush=True)
                    last = offset
    digest = hashlib.sha256()
    with pending.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        pending.unlink()
        raise ValueError('CUDA download checksum mismatch: '+path.name)
    pending.replace(path)


def main():
    from core.xtts_runtime import validate
    from core.runtime_integrity import sha
    validate()
    folder = ROOT/'runtime_profiles/cuda'
    if (folder/'profile.json').exists():
        raise RuntimeError('A CUDA profile already exists. Validate it before replacing it.')
    folder.mkdir(parents=True, exist_ok=True)
    for path in (ROOT/'runtime_profiles/xtts-security-candidate').iterdir():
        if path.is_file() and path.name not in ('profile.json', '.owner', 'python313._pth'):
            shutil.copyfile(path, folder/path.name)
    packages = folder/'Lib/site-packages'
    packages.mkdir(parents=True, exist_ok=True)
    pth = 'python313.zip\n.\nLib/site-packages\n'+''.join(
        f'../{name}/Lib/site-packages\n' for name in SHARED)+'import site\n'
    (folder/'python313._pth').write_text(pth, encoding='utf-8')
    (folder/'.owner').write_text('reflow.cuda.v1', encoding='utf-8')
    downloads = ROOT/'build/cuda-wheels'
    downloads.mkdir(parents=True, exist_ok=True)
    records = {}
    for package, version in PACKAGES.items():
        url, name, expected = official_wheel(package, version)
        target = downloads/name
        if not target.exists() or sha(target) != expected:
            download(url, target, expected)
        print('Verified', name, flush=True)
        records[package] = dict(version=version, wheel=name, sha256=expected, url=url)
    installer = ROOT/'build/windows-portable/python.exe'
    subprocess.run([str(installer), '-B', '-m', 'pip', 'install', '--upgrade', '--no-deps', '--no-compile',
        '--only-binary=:all:', '--python-version', '3.13', '--platform', 'win_amd64',
        '--implementation', 'cp', '--abi', 'cp313', '--target', str(packages),
        *[str(downloads/record['wheel']) for record in records.values()]], check=True)
    record = dict(schema='reflow.cuda-runtime.v1', status='installed-awaiting-gpu-validation',
                  packages=records, pth=pth, python='3.13.16',
                  bootstrap={name:sha(folder/name) for name in ('python.exe','python313.dll','python313.zip')})
    (folder/'profile.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print('CUDA packages installed. Model tests are still required.', flush=True)


if __name__ == '__main__':
    main()
