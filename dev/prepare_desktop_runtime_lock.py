"""Metadata-only Windows desktop resolution; archive GETs/install/builds forbidden."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PREFIX = '2026-10-13-desktop-candidate'
ROOTS = {
    'pywebview': '6.2.1', 'pythonnet': '3.1.0', 'psutil': '7.2.2',
    'pydub': '0.25.1', 'audioop-lts': '0.2.2', 'soundfile': '0.13.1',
    'cffi': '2.0.0', 'requests': '2.32.5', 'filelock': '3.20.3',
    'packaging': '26.0', 'keyring': '25.7.0', 'pystray': '0.19.5',
    'pillow': '11.3.0', 'tqdm': '4.67.3',
}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='initial')
    parser.add_argument('--security-revised', action='store_true')
    parser.add_argument('--approved-helper', action='store_true')
    args = parser.parse_args()
    assert args.label.replace('-', '').isalnum()
    if args.security_revised:
        ROOTS.update(pillow='12.3.0', requests='2.34.2')
    from pip._internal.network.session import PipSession
    from pip._internal.cli.main import main as pip_main
    report_path = OUT / (PREFIX + '-' + args.label + '-resolution-report.json')
    receipt_path = OUT / (PREFIX + '-' + args.label + '-resolution-receipt.json')
    assert not report_path.exists() and not receipt_path.exists(), 'Preserve historical evidence'
    original = PipSession.send
    requests_seen = []
    local_artifacts = []
    helper_hash = None
    if args.approved_helper:
        import hashlib
        helper_dir = OUT / '2026-10-13-proxy-tools-helper'
        helper = json.loads((helper_dir / 'receipt.json').read_text(encoding='utf-8'))
        wheel = (helper_dir / helper['wheel']).resolve()
        assert wheel.is_relative_to(helper_dir.resolve())
        assert helper['build_passed'] and helper['python313_smoke_passed']
        helper_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert helper_hash == helper['wheel_sha256']
        local_artifacts.append(str(wheel))

    def guarded_send(session, request, **kwargs):
        parsed = urlsplit(request.url)
        path = parsed.path.lower()
        allowed = (request.method.upper() == 'GET' and parsed.scheme == 'https'
                   and not parsed.username and parsed.hostname in {'pypi.org', 'files.pythonhosted.org'}
                   and (path.endswith('.whl.metadata') or
                        parsed.hostname == 'pypi.org' and path.startswith('/simple/')))
        requests_seen.append(dict(method=request.method, url=request.url, allowed=allowed))
        if not allowed:
            raise RuntimeError('Desktop planning blocked non-metadata transfer: ' + request.url)
        return original(session, request, **kwargs)

    os.environ['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    PipSession.send = guarded_send
    try:
        code = pip_main(['--isolated', 'install', '--dry-run', '--ignore-installed', '--no-cache-dir',
                         '--only-binary=:all:', '--python-version', '3.13', '--platform', 'win_amd64',
                         '--implementation', 'cp', '--abi', 'cp313', '--disable-pip-version-check',
                         '--index-url', 'https://pypi.org/simple', '--timeout', '20', '--retries', '0',
                         '--report', str(report_path)] + local_artifacts + [name + '==' + version for name, version in ROOTS.items()])
    except Exception as error:
        code = 1
        print(type(error).__name__, str(error), flush=True)
    finally:
        PipSession.send = original
        receipt_path.write_text(json.dumps(dict(metadata_only=True, packages_installed=False,
            archives_allowed=False, builds_allowed=False, roots=ROOTS, requests=requests_seen,
            approved_local_helper_sha256=helper_hash,
            resolution_complete=report_path.exists(), exit_code=locals().get('code', 1)), indent=2), encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
