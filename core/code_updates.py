"""Detect edited application code without replacing live Python objects."""
import hashlib
from pathlib import Path


def backend_version(root):
    root = Path(root)
    files = [root/'main.py', root/'config.py', *root.glob('bridge/*.py'), *root.glob('core/*.py'),
             *root.glob('core/providers/**/*.py'), *root.glob('core/tts/*.py'), *root.glob('core/stt/*.py')]
    records = []
    for path in sorted(set(files)):
        if not path.is_file():
            continue
        info = path.stat()
        records.append((str(path.relative_to(root)), info.st_size, info.st_mtime_ns))
    return hashlib.sha256(repr(records).encode()).hexdigest()


def interface_version(root):
    return hashlib.sha256((Path(root)/'frontend/dist/index.html').read_bytes()).hexdigest()
