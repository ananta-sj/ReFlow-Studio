"""Build only the explicitly approved Docopt archive; never install packages."""
import hashlib
import base64
import csv
import io
from email.parser import Parser
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
OUT = ROOT / 'docs/validation/2026-10-13-docopt-helper'
URL = 'https://files.pythonhosted.org/packages/a2/55/8f8cab2afd404cf578136ef2cc5dfb50baa1761b68c9da1fb1e4eed343c9/docopt-0.6.2.tar.gz'
SHA = '49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parent = ROOT / 'temp'
    parent.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix='docopt-approved-', dir=parent))
    receipt = dict(runtime_installed=False, model_downloaded=False,
                   source_url=URL, source_sha256=SHA, target_python_execution_verified=False)
    try:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read(25902)
        assert len(data) == 25901 and hashlib.sha256(data).hexdigest() == SHA
        archive = OUT / 'docopt-0.6.2.tar.gz'
        archive.write_bytes(data)
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            assert len(members) < 100 and sum(m.size for m in members) < 1000000
            for member in members:
                target = (workspace / member.name).resolve()
                assert target.is_relative_to(workspace.resolve())
                assert not member.issym() and not member.islnk()
                assert member.isdir() or member.isfile()
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as stream:
                        target.write_bytes(stream.read())
        source = workspace / 'docopt-0.6.2'
        setup = (source / 'setup.py').read_text()
        assert "py_modules=['docopt']" in setup or "py_modules = ['docopt']" in setup
        assert 'ext_modules' not in setup and 'install_requires' not in setup
        for name in ['setup.py', 'LICENSE-MIT']:
            shutil.copy2(source / name, OUT / name)
        env = os.environ.copy()
        env.update(TEMP=str(workspace), TMP=str(workspace), PYTHONDONTWRITEBYTECODE='1',
                   PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
        # setup.py uses existing setuptools/wheel only; no build isolation or pip installation.
        command = [sys.executable, '-B', '-X', 'utf8', 'setup.py', 'bdist_wheel', '--dist-dir', str(OUT)]
        result = subprocess.run(command, cwd=source, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (OUT / 'build.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stderr
        wheel = OUT / 'docopt-0.6.2-py3-none-any.whl'
        if not wheel.exists():
            candidates = list(OUT.glob('docopt-0.6.2-*.whl'))
            assert len(candidates) == 1
            wheel = candidates[0]
        with zipfile.ZipFile(wheel) as package:
            assert package.read('docopt.py') == (source / 'docopt.py').read_bytes()
            names = package.namelist()
            assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in names)
            metadata = package.read(next(n for n in names if n.endswith('/METADATA'))).decode()
            headers = Parser().parsestr(metadata)
            assert headers['Name'] == 'docopt' and headers['Version'] == '0.6.2'
            assert any('license' in n.lower() for n in names)
            record = package.read(next(n for n in names if n.endswith('/RECORD'))).decode()
            for name, digest, size in csv.reader(io.StringIO(record)):
                if digest:
                    payload = package.read(name)
                    expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip('=')
                    assert digest == expected and int(size) == len(payload)
        smoke = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c',
            "import sys; sys.path.insert(0, sys.argv[1]); from docopt import docopt; assert docopt('Usage: app [--quiet]', argv=['--quiet'])['--quiet'] is True; print('parser smoke passed')", str(wheel)],
            env=env, capture_output=True, text=True, timeout=30)
        assert smoke.returncode == 0, smoke.stderr
        receipt.update(build_passed=True, smoke_passed=True, smoke_python=sys.version,
                       wheel=wheel.name, wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                       command=command, source_matches_wheel=True)
    finally:
        assert workspace.resolve().is_relative_to(parent.resolve()) and workspace.name.startswith('docopt-approved-')
        shutil.rmtree(workspace)
        receipt['temporary_workspace_removed'] = not workspace.exists()
        (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
