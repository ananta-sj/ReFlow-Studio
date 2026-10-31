"""Isolate Demucs with restricted checkpoint deserialization on current Torch."""
import os
import sys
from pathlib import Path
isolated = '--reflow-isolated' in sys.argv
if isolated:
    sys.argv.remove('--reflow-isolated')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from core.separation_runtime import validate, model_contract
    route = validate()
    if Path(sys.executable).resolve() != Path(route['executable']).resolve():
        raise RuntimeError('Separation worker started in the wrong interpreter')
    model_contract(verify_weights=True)
    _ffmpeg_handle = os.add_dll_directory(str(root/'ffmpeg/shared_libs')) if os.name == 'nt' else None
    def offline(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('Network is disabled in the isolated separation worker')
    sys.addaudithook(offline)
import random
import runpy
from fractions import Fraction
import numpy as np
import torch
from demucs.htdemucs import HTDemucs

# Demucs' default stabilization uses Python's random time shift. Keep the
# existing one-shift recipe reproducible so the same input produces the same
# separated PCM and can match verified recognition checkpoints on restart.
random.seed(0)
np.random.seed(0)
torch.manual_seed(0)

# Demucs' upstream loader omits weights_only. Force restricted loading in
# this worker only, and admit the exact classes used by htdemucs' checkpoint.
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '1'
allowed = [HTDemucs, Fraction, np.dtype, np.core.multiarray.scalar,
           type(np.dtype(np.float64)), type(np.dtype(np.float32))]
if isolated:
    # NumPy 2 moved this callable to numpy._core. The hash-pinned existing
    # checkpoint records its old name; admit only that exact alias.
    allowed.append((np.core.multiarray.scalar, 'numpy.core.multiarray.scalar'))
with torch.serialization.safe_globals(allowed):
    runpy.run_module('demucs', run_name='__main__')
