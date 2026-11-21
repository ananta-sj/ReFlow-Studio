"""Hosted Windows install/upgrade/launch/uninstall acceptance, no AI models."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    subprocess.run([str(x) for x in command], check=True, timeout=360,
                   env={**os.environ, 'PYSTRAY_BACKEND': 'dummy'})


def main():
    report = ROOT/'build/ci-windows-installer-smoke.json'
    result = dict(passed=False, model_inference_test=False, clean_machine_test=False)
    try:
        with tempfile.TemporaryDirectory(prefix='reflow-installed-') as folder:
            parent = Path(folder)
            target = parent/'Application With Spaces'
            setup = ROOT/'release-assets/ReflowStudio-windows-x64-desktop-preview-setup.exe'
            install = [setup, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
                       '/DIR='+str(target), '/LOG='+str(parent/'install.log')]
            run(install)
            # Test preservation across an overlay upgrade and uninstall.
            state = [target/'settings.json', target/'models/installer-test.keep',
                     target/'outputs/installer-test.keep']
            for file in state:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('owned installer smoke sentinel', encoding='utf-8')
            run(install)
            for file in state:
                if file.read_text(encoding='utf-8') != 'owned installer smoke sentinel':
                    raise RuntimeError('Upgrade changed user data')
            # Do not feed synthetic settings to the actual launcher.
            state[0].unlink()
            for mode in ('--verify-package', '--verify-desktop'):
                output = parent/(mode[2:]+'.json')
                run([target/'ReflowStudio.exe', mode, output])
                key = 'acceptance' if mode == '--verify-desktop' else 'passed'
                if json.loads(output.read_text(encoding='utf-8')).get(key) is not True:
                    raise RuntimeError('Installed launcher check failed: '+mode)
            state[0].write_text('owned installer smoke sentinel', encoding='utf-8')
            # A held application lock must prevent an upgrade, not terminate it.
            import msvcrt
            with (target/'.reflow-instance.lock').open('a+b') as lock:
                lock.seek(0)
                lock.write(b'0')
                lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    blocked = subprocess.run([str(x) for x in install], timeout=120)
                    if blocked.returncode == 0:
                        raise RuntimeError('Installer updated a running application')
                finally:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            run([target/'unins000.exe', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                 '/LOG='+str(parent/'uninstall.log')])
            if (target/'ReflowStudio.exe').exists():
                raise RuntimeError('Uninstall left the program executable')
            if any(file.read_text(encoding='utf-8') != 'owned installer smoke sentinel' for file in state):
                raise RuntimeError('Uninstall changed user data')
            result.update(passed=True, install=True, overlay_upgrade=True, installed_launch=True,
                          active_application_block=True, uninstall_preserves_user_data=True)
    finally:
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
