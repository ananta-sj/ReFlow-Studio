"""Build the approved hash-bound proxy-tools source; never install it."""
import argparse
import ast
import base64
import csv
from email.parser import Parser
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/2026-10-13-proxy-tools-helper'
URL = 'https://files.pythonhosted.org/packages/f2/cf/77d3e19b7fabd03895caca7857ef51e4c409e0ca6b37ee6e9f7daa50b642/proxy_tools-0.1.0.tar.gz'
SHA = 'ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010'


def unpack(archive, workspace):
    with tarfile.open(archive) as package:
        members = package.getmembers()
        assert len(members) < 100 and sum(member.size for member in members) < 1_000_000
        for member in members:
            target = (workspace / member.name).resolve()
            assert target.is_relative_to(workspace.resolve())
            assert not member.issym() and not member.islnk()
            assert member.isdir() or member.isfile()
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.extractfile(member) as stream:
                    target.write_bytes(stream.read())
    return workspace / 'proxy_tools-0.1.0'


def inspect(source):
    setup = (source / 'setup.py').read_text(encoding='utf-8')
    tree = ast.parse(setup)
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    assert values['required_modules'] == [] and values['packages'] == ['proxy_tools']
    assert 'ext_modules' not in setup and 'setup_requires' not in setup
    return setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch-only', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'proxy_tools-0.1.0.tar.gz'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(2979)
        assert len(data) == 2978 and hashlib.sha256(data).hexdigest() == SHA
        archive.write_bytes(data)
    assert archive.stat().st_size == 2978 and hashlib.sha256(archive.read_bytes()).hexdigest() == SHA
    parent = ROOT / 'temp'
    parent.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='proxy-approved-', dir=parent))
    receipt = dict(runtime_installed=False, source_url=URL, source_bytes=2978, source_sha256=SHA)
    try:
        source = unpack(archive, workspace)
        setup = inspect(source)
        for name in ['setup.py', 'proxy_tools/__init__.py']:
            destination = OUT / Path(name).name
            shutil.copy2(source / name, destination)
        if args.fetch_only:
            print(setup)
            print((source / 'proxy_tools/__init__.py').read_text(encoding='utf-8'))
            return
        assert not (OUT / 'receipt.json').exists(), 'Preserve completed build evidence'
        # The published archive omits its referenced license. Retain a pinned
        # upstream notice as supplemental packaging; do not rewrite MIT metadata
        # or the module's BSD attribution to conceal their disagreement.
        with urllib.request.urlopen('https://api.github.com/repos/jtushman/proxy_tools/commits/master', timeout=30) as response:
            commit = json.loads(response.read(100000))['sha']
        assert len(commit) == 40 and all(character in '0123456789abcdef' for character in commit)
        notice_url = 'https://raw.githubusercontent.com/jtushman/proxy_tools/' + commit + '/LICENSE.txt'
        with urllib.request.urlopen(notice_url, timeout=30) as response:
            notice = response.read(10001)
        assert len(notice) <= 10000 and b'2013 Armin Ronacher' in notice and b'2014 Jonathan Tushman' in notice
        (OUT / 'LICENSE.upstream.txt').write_bytes(notice)
        (source / 'LICENSE.upstream.txt').write_bytes(notice)
        with (source / 'setup.cfg').open('a', encoding='utf-8') as stream:
            stream.write('\n[metadata]\nlicense_files = LICENSE.upstream.txt\n')
        receipt.update(upstream_notice_url=notice_url, upstream_notice_sha256=hashlib.sha256(notice).hexdigest(),
                       original_archive_omits_license=True, license_label_conflict='setup/metadata MIT; module/upstream notice BSD',
                       distribution_notice_review_complete=False, packaging_addition='supplemental pinned upstream notice')
        import setuptools
        import wheel as wheel_library
        receipt['build_tools'] = dict(python=sys.version, setuptools=setuptools.__version__, wheel=wheel_library.__version__)
        environment = os.environ.copy()
        environment.update(TEMP=str(workspace), TMP=str(workspace), PYTHONDONTWRITEBYTECODE='1',
                           PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
        wrapper = """import setuptools,socket,runpy,sys
def denied(*args,**kwargs): raise RuntimeError('Helper build/test network blocked')
class OfflineSocket(socket.socket):
    connect=connect_ex=bind=sendto=denied
socket.socket=OfflineSocket
socket.create_connection=socket.getaddrinfo=denied
sys.argv=['setup.py','bdist_wheel','--dist-dir',sys.argv[1]]
runpy.run_path('setup.py',run_name='__main__')
"""
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', wrapper, str(OUT)],
                                cwd=source, env=environment, capture_output=True, text=True,
                                encoding='utf-8', timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (OUT / 'build.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        wheels = list(OUT.glob('proxy_tools-0.1.0-*.whl'))
        assert len(wheels) == 1
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as package:
            names = package.namelist()
            assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in names)
            assert package.read('proxy_tools/__init__.py') == (source / 'proxy_tools/__init__.py').read_bytes()
            headers = Parser().parsestr(package.read(next(name for name in names if name.endswith('/METADATA'))).decode())
            assert headers['Name'].replace('-', '_') == 'proxy_tools' and headers['Version'] == '0.1.0'
            assert not headers.get_all('Requires-Dist')
            assert any(name.endswith('/LICENSE.upstream.txt') and package.read(name) == notice for name in names)
            for name, digest, size in csv.reader(io.StringIO(package.read(next(name for name in names if name.endswith('/RECORD'))).decode())):
                if digest:
                    payload = package.read(name)
                    expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=')
                    assert digest == expected and int(size) == len(payload)
        smoke_code = """import sys,socket
def denied(*args,**kwargs): raise RuntimeError('Helper test network blocked')
socket.create_connection=socket.getaddrinfo=denied
sys.path.insert(0,sys.argv[1])
from proxy_tools import Proxy,module_property
target={'answer':42}
p=Proxy(lambda:target)
assert p['answer']==42
p['answer']=43
assert target['answer']==43 and len(p)==1
print('proxy smoke passed; module='+__import__('proxy_tools').__file__)
"""
        python = ROOT / 'runtime_profiles/xtts-security-candidate/python.exe'
        smoke = subprocess.run([str(python), '-B', '-X', 'utf8', '-c', smoke_code, str(wheel)],
                               env=environment, capture_output=True, text=True, encoding='utf-8', timeout=30)
        (OUT / 'python313-smoke.log').write_text(smoke.stdout + smoke.stderr, encoding='utf-8')
        assert smoke.returncode == 0, smoke.stdout + smoke.stderr
        assert str(wheel) in smoke.stdout
        receipt.update(build_passed=True, wheel=wheel.name, wheel_bytes=wheel.stat().st_size,
                       wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(), record_verified=True,
                       source_matches_wheel=True, notice_included=True, requires_dist=[],
                       python313_smoke_passed=True, smoke_python=str(python), network_blocked_during_build=True)
    finally:
        assert workspace.resolve().is_relative_to(parent.resolve()) and workspace.name.startswith('proxy-approved-')
        shutil.rmtree(workspace)
        if not args.fetch_only:
            receipt['temporary_workspace_removed'] = not workspace.exists()
            (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
