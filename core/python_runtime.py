"""Resolve a real Python worker rather than relaunching a frozen app."""
from pathlib import Path
import os
import sys


def project_root():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]


def worker_python():
    explicit = os.environ.get('REFLOW_WORKER_PYTHON')
    if explicit:
        path = Path(explicit)
        if not path.is_absolute() or not path.is_file() or path.resolve() == Path(sys.executable).resolve() and getattr(sys, 'frozen', False):
            raise RuntimeError('REFLOW_WORKER_PYTHON must point to a real, absolute Python interpreter')
        return str(path.resolve())
    if not getattr(sys, 'frozen', False):
        return sys.executable
    root = project_root()
    for relative in ('build/windows-portable/python.exe', 'python/python.exe', 'python/bin/python3'):
        candidate = root / relative
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError('This executable lacks its Python worker runtime. Use the portable setup or provide REFLOW_WORKER_PYTHON.')


def inprocess_python():
    """A worker override cannot prove packages used by the main application.

    Source/portable execution can spawn its own interpreter. A frozen app has
    different bundled imports and cannot be measured by a standalone worker.
    """
    return None if getattr(sys, 'frozen', False) else sys.executable
