"""Native hosted acceptance of the actual POSIX installation downloads."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def run(command,env,check=True):
    return subprocess.run([str(x) for x in command],env=env,check=check,timeout=420)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('target',choices=('linux-x64','macos-arm64','macos-x64'))
    target=parser.parse_args().target
    mac=target.startswith('macos-')
    report=ROOT/'build'/('ci-'+target+'-installer-smoke.json')
    result=dict(passed=False,model_inference_test=False,clean_machine_test=False)
    with tempfile.TemporaryDirectory(prefix='reflow-install-') as folder:
        home=Path(folder)/'Home With Spaces';home.mkdir()
        env={**os.environ,'HOME':str(home),'PYTHONDONTWRITEBYTECODE':'1','PYSTRAY_BACKEND':'dummy',
             'XDG_DATA_HOME':str(home/'.local/share'),'XDG_CONFIG_HOME':str(home/'.config'),
             'XDG_CACHE_HOME':str(home/'.cache')}
        mount=Path(folder)/'mounted';mounted=False
        try:
            package=ROOT/'release-assets'/f'ReflowStudio-{target}-desktop-preview-setup{(".dmg" if mac else ".run")}'
            if mac:
                mount.mkdir()
                run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',mount,package],env)
                mounted=True
                install=['/bin/bash',mount/'Install Reflow Studio.command']
                remove=['/bin/bash',mount/'Uninstall Reflow Studio.command']
                payload=home/'Library/Application Support/ReflowStudio/runtime'
                executable=home/'Applications/ReflowStudio.app/Contents/MacOS/ReflowStudio'
            else:
                install=['sh',package];remove=['sh',package,'--uninstall']
                payload=home/'.local/share/ReflowStudio'
                executable=payload/'ReflowStudio'
            run(install,env)
            if mac:
                run(['codesign','--verify','--deep','--strict',home/'Applications/ReflowStudio.app'],env)
            state=[payload/'settings.json',payload/'models/installer-test.keep',payload/'outputs/installer-test.keep']
            for file in state:
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text('{"installer_test": true}',encoding='utf-8')
            run(install,env)
            if any(file.read_text(encoding='utf-8')!='{"installer_test": true}' for file in state):
                raise RuntimeError('Upgrade changed user data')
            for mode,key in [('--verify-package','passed'),('--verify-desktop','acceptance')]:
                output=Path(folder)/(mode[2:]+'.json')
                command=[executable,mode,output]
                if not mac and mode=='--verify-desktop':
                    command=['xvfb-run','-a',*command]
                run(command,env)
                if json.loads(output.read_text(encoding='utf-8')).get(key) is not True:
                    raise RuntimeError('Installed startup failed: '+mode)
            if mac:
                # Desktop startup must not mutate the installed signed .app.
                run(['codesign','--verify','--deep','--strict',home/'Applications/ReflowStudio.app'],env)
            import fcntl
            with (payload/'.reflow-instance.lock').open('a+b') as stream:
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                try:
                    if run(install,env,check=False).returncode==0:
                        raise RuntimeError('Active app did not block upgrade')
                finally:
                    fcntl.flock(stream,fcntl.LOCK_UN)
            # Write an exact owned sentinel after the desktop has exercised settings.
            for file in state:
                file.write_text('preserve installer smoke data',encoding='utf-8')
            run(remove,env)
            if executable.exists():
                raise RuntimeError('Uninstall left the launcher')
            if any(file.read_text(encoding='utf-8')!='preserve installer smoke data' for file in state):
                raise RuntimeError('Uninstall changed user data')
            result.update(passed=True,install=True,overlay_upgrade=True,installed_launch=True,
                          active_application_block=True,uninstall_preserves_user_data=True,
                          immutable_macos_application=mac)
        finally:
            if mounted:
                run(['hdiutil','detach',mount],env)
            report.write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
