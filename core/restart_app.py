"""Wait for this app instance to release its lock before reopening the app."""
import os
from pathlib import Path
import subprocess
import sys

import psutil


def main():
    root = Path(__file__).resolve().parents[1]
    executable = Path(sys.argv[3]).resolve()
    if not executable.is_relative_to(root):
        raise RuntimeError('Restart executable must belong to this application.')
    try:
        parent = psutil.Process(int(sys.argv[1]))
        if abs(parent.create_time()-float(sys.argv[2])) > .01:
            raise RuntimeError('The application process changed.')
        parent.wait(timeout=600)
    except psutil.NoSuchProcess:
        pass
    except psutil.TimeoutExpired:
        return
    command = [str(executable)]
    if executable.name.lower().startswith('python'):
        command += ['-B', str(root/'main.py')]
    subprocess.Popen(command, cwd=root,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


if __name__ == '__main__':
    main()
