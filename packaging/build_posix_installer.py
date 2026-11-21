"""Use native OS tools to wrap the exact verified candidate; no tool downloads."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'packaging/install_posix.py')
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def linux_header(name,digest):
    template='''#!/bin/sh
set -eu
if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != '--uninstall' ]; }; then
  echo 'Usage: sh this-file.run [--uninstall]' >&2; exit 2
fi
work=$(mktemp -d "${TMPDIR:-/tmp}/reflow-setup.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
tail -n +ARCHIVE_LINE "$0" > "$work/payload.tar.gz"
printf '%s  %s\n' 'DIGEST' "$work/payload.tar.gz" | sha256sum -c -
tar -xzf "$work/payload.tar.gz" -C "$work"
source="$work/NAME"
if [ "$#" -eq 1 ]; then
  "$source/python/bin/python3" -B "$source/packaging/install_posix.py" --target linux-x64 --uninstall
else
  "$source/python/bin/python3" -B "$source/packaging/install_posix.py" --target linux-x64 --source "$source"
fi
exit 0
'''
    header=template.replace('NAME',name).replace('DIGEST',digest)
    return header.replace('ARCHIVE_LINE',str(header.count('\n')+1)).encode('utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('target',choices=installer.TARGETS)
    args=parser.parse_args()
    target=args.target
    expected='macos-' if sys.platform=='darwin' else 'linux-' if sys.platform.startswith('linux') else ''
    if not expected or not target.startswith(expected):
        raise RuntimeError('Use the matching native runner')
    base=ROOT/'dist'/f'ReflowStudio-{target}-desktop-preview'
    installer.inventory(base,target)
    output=ROOT/'release-assets'/(base.name+'-setup'+('.dmg' if expected=='macos-' else '.run'))
    if output.exists():
        raise RuntimeError('Installer output already exists')
    if expected=='linux-':
        archive=ROOT/'release-assets'/(base.name+'.tar.gz')
        with output.open('xb') as stream, archive.open('rb') as payload:
            stream.write(linux_header(base.name,installer.sha(archive)))
            shutil.copyfileobj(payload,stream)
        output.chmod(0o755)
    else:
        with tempfile.TemporaryDirectory(prefix='reflow-dmg-') as folder:
            stage=Path(folder)/'image'
            shutil.copytree(base,stage,symlinks=True)
            for label,argument in [('Install Reflow Studio','--source "$here"'),('Uninstall Reflow Studio','--uninstall')]:
                script=stage/(label+'.command')
                script.write_text('#!/bin/bash\nset -euo pipefail\nhere="$(cd -- "$(dirname -- "$0")" && pwd)"\n'+
                    '"$here/ReflowStudio.app/Contents/Resources/ReflowStudio/python/bin/python3" -B '+
                    '"$here/ReflowStudio.app/Contents/Resources/ReflowStudio/packaging/install_posix.py" '+
                    '--target '+target+' '+argument+'\n',encoding='utf-8')
                script.chmod(0o755)
            (stage/'INSTALL_FIRST.txt').write_text('DESKTOP PREVIEW — TESTING REQUIRED\n\nOpen Install Reflow Studio.command to install for your user.\nThen open ~/Applications/ReflowStudio.app. Do not launch from this disk image.\nThe app is not Developer ID signed or notarized. macOS may require explicit user approval.\nRuntime/state live in ~/Library/Application Support/ReflowStudio/runtime.\nUse Uninstall Reflow Studio.command to remove unchanged program files and keep user data.\nAI engines/models and FFmpeg are not bundled.\n',encoding='utf-8')
            subprocess.run(['hdiutil','create','-volname','Reflow Studio Preview','-srcfolder',str(stage),
                            '-format','UDZO','-fs','HFS+',str(output)],check=True,timeout=900)
    output.with_name(output.name+'.sha256').write_text(installer.sha(output)+'  '+output.name+'\n',encoding='ascii')
    print(output)


if __name__=='__main__':
    main()
