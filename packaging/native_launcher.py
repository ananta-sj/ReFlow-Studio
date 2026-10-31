"""Frozen desktop entry point; run the included application Python unchanged.

Keep inference in its tested runtimes rather than importing AI engines into
PyInstaller. No downloads or installations are performed by this launcher.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def payload_root():
    executable = Path(sys.executable).resolve()
    if sys.platform == 'darwin' and executable.parent.name == 'MacOS':
        return executable.parent.parent/'Resources'/'ReflowStudio'
    return executable.parent


def child_environment(root, verify=False):
    env = dict(os.environ)
    # PyInstaller's library search paths belong to this launcher, not CPython.
    for key in ('PYTHONHOME','PYTHONPATH'):
        env.pop(key, None)
    if 'LD_LIBRARY_PATH_ORIG' in env:
        env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
    else:
        env.pop('LD_LIBRARY_PATH', None)
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    env['PATH'] = str(root/'ffmpeg/bin')+os.pathsep+env.get('PATH','')
    if sys.platform.startswith('linux'):
        env.setdefault('PYWEBVIEW_GUI','qt')
    if verify:
        env.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    return env


def main():
    root = payload_root()
    candidates = ('build/windows-portable/python.exe','python/python.exe','python/bin/python3')
    python = next((root/name for name in candidates if (root/name).is_file()), None)
    if not python or not (root/'main.py').is_file():
        raise RuntimeError('The application folder is incomplete. Extract the entire download before starting Reflow Studio.')
    flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    if len(sys.argv)==3 and sys.argv[1] in ('--verify-package','--verify-desktop'):
        helper = 'verify_payload.py' if sys.argv[1]=='--verify-package' else 'desktop_smoke.py'
        arguments = [str(root/'packaging'/helper)]
        if helper=='desktop_smoke.py':
            arguments.append(str(root))
        arguments.append(str(Path(sys.argv[2]).resolve()))
        return subprocess.run([str(python),'-B',*arguments],cwd=root,
            env=child_environment(root,verify=True),creationflags=flags,timeout=240).returncode
    if len(sys.argv)!=1:
        raise RuntimeError('Start ReflowStudio without command-line arguments.')
    log_folder = root/'logs'
    log_folder.mkdir(exist_ok=True)
    # Limit startup diagnostics retained between launches. Rendering uses the
    # application's own job state; the launcher never alters input/output media.
    log = log_folder/'launcher.log'
    if log.exists() and log.stat().st_size > 8*1024*1024:
        log.replace(log_folder/'launcher.previous.log')
    env = child_environment(root)
    with log.open('ab') as stream:
        result = subprocess.run([str(python),'-B',str(root/'core/integrity.py')],cwd=root,
            env=env,stdout=stream,stderr=stream,creationflags=flags,timeout=120)
        if result.returncode:
            raise RuntimeError('Runtime checks failed. See logs/launcher.log. Windows may require WebView2 and the Visual C++ runtime.')
        result = subprocess.run([str(python),'-B',str(root/'main.py')],cwd=root,
            env=env,stdout=stream,stderr=stream,creationflags=flags)
    if result.returncode:
        raise RuntimeError('Reflow Studio stopped with an error. See logs/launcher.log.')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        message = str(error)
        if sys.stderr is not None:
            print(message,file=sys.stderr)
        if os.name=='nt' and len(sys.argv)==1:
            ctypes.windll.user32.MessageBoxW(None,message,'Reflow Studio',0x10)
        raise SystemExit(1)
