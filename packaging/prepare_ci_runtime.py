"""Fetch a pinned relocatable Python on CI, outside working app runtimes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('target',choices=('windows-x64','linux-x64','macos-arm64','macos-x64'))
    args=parser.parse_args()
    actual_os='windows' if sys.platform=='win32' else 'macos' if sys.platform=='darwin' else 'linux'
    actual_arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    if args.target!=actual_os+'-'+actual_arch:
        raise RuntimeError('Runtime target does not match the native runner')
    base=ROOT/'build/ci-runtime'
    if base.exists():
        raise RuntimeError('CI runtime already exists; refusing replacement')
    recipe=json.loads((ROOT/'packaging/ci_runtime_sources.json').read_text())
    row=recipe['targets'][args.target]
    name='cpython-%s+%s-%s-install_only.tar.gz' % (recipe['python'],recipe['release'],row['triple'])
    url='https://github.com/astral-sh/python-build-standalone/releases/download/%s/%s' % (recipe['release'],name)
    archive=ROOT/'build'/name
    archive.parent.mkdir(exist_ok=True)
    checksum=hashlib.sha256()
    request=urllib.request.Request(url,headers={'User-Agent':'ReflowStudio-CI'})
    with urllib.request.urlopen(request,timeout=120) as response, archive.open('xb') as output:
        for block in iter(lambda: response.read(1024*1024),b''):
            checksum.update(block)
            output.write(block)
    if checksum.hexdigest()!=row['sha256']:
        raise RuntimeError('Python runtime checksum differs from pinned upstream identity')
    base.mkdir()
    with tarfile.open(archive,'r:gz') as bundle:
        bundle.extractall(base,filter='data')
    executable=base/'python'/('python.exe' if sys.platform=='win32' else 'bin/python3')
    if not executable.is_file():
        raise RuntimeError('Downloaded runtime has an unexpected layout')
    print(str(executable),flush=True)


if __name__=='__main__':
    main()
