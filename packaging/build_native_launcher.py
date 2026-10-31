"""Freeze only the launcher using the separately approved build tool."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    work=args.work.resolve()
    if not output.is_relative_to(ROOT/'build') or not work.is_relative_to(ROOT/'build'):
        raise ValueError('Launcher build directories must be inside build')
    if output.exists() or work.exists():
        raise ValueError('Refusing to replace an existing launcher build')
    work.mkdir(parents=True)
    command=[sys.executable,'-B','-m','PyInstaller','--onedir','--windowed','--noupx',
             '--name','ReflowStudio','--distpath',str(output),'--workpath',str(work/'work'),
             '--specpath',str(work/'spec')]
    if sys.platform=='win32':
        command += ['--icon',str(ROOT/'assets/icon.ico')]
    if sys.platform=='darwin':
        command += ['--osx-bundle-identifier','com.reflowstudio.desktop']
    command.append(str(ROOT/'packaging/native_launcher.py'))
    subprocess.run(command,cwd=ROOT,check=True)


if __name__=='__main__':
    main()
