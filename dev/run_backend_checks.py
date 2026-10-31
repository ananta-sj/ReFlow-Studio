"""Offline unit checks with workspace-owned caches; installs nothing.

Run with the existing bundled Python. The two legacy standalone scripts are
excluded because importing them mutates application state or downloads models.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
    (ROOT / 'temp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='backend-checks-', dir=ROOT / 'temp') as folder:
        cache = Path(folder)
        os.environ.update(
            TEMP=folder, TMP=folder, HF_HOME=str(cache / 'hf'),
            MPLCONFIGDIR=str(cache / 'matplotlib'), TORCH_HOME=str(cache / 'torch'),
            NUMBA_CACHE_DIR=str(cache / 'numba'), REFLOW_OFFLINE='1',
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
            PATH=str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''),
        )
        tempfile.tempdir = folder
        excluded = {'test_model_download', 'test_pipeline_dryrun'}
        names = ['dev.' + path.stem for path in sorted((ROOT / 'dev').glob('test_*.py'))
                 if path.stem not in excluded]
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
