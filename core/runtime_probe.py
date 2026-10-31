"""Bounded, explicit smoke checks in existing isolated engine interpreters."""
import json
import os
from pathlib import Path
import subprocess
import threading

from core.python_runtime import project_root
from core.render_context import RenderContext, bind_job, run_process
from core.runtime_probe_contract import ROUTES, require_route

_gate = threading.BoundedSemaphore(1)
TIMEOUTS = {adapter: definition[0] for adapter, definition in ROUTES.items()}


def probe(adapter, executable, device):
    timeout = require_route(adapter, device)
    if not _gate.acquire(blocking=False):
        return dict(status='unverified', details=['Another runtime check is running. Try again when it finishes.'])
    job = None
    try:
        root = project_root()
        job = RenderContext(root / 'temp')
        folder = job.workspace
        report_path = folder / 'runtime.json'
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'REFLOW_OFFLINE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8',
               'TEMP': str(folder), 'TMP': str(folder), 'HF_HOME': str(folder / 'hf'),
               'TORCH_HOME': str(folder / 'torch'), 'XDG_CACHE_HOME': str(folder / 'cache'),
               'MPLCONFIGDIR': str(folder / 'matplotlib')}
        with bind_job(job), (folder / 'diagnostics.log').open('wb') as diagnostics:
            run_process([str(executable), '-B', str(root / 'core/runtime_probe_worker.py'),
                         adapter, device, str(report_path)], timeout=timeout, check=True,
                        stdout=diagnostics, stderr=diagnostics, env=env,
                        **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        if not report_path.is_file() or report_path.stat().st_size > 65536:
            raise ValueError('Runtime check returned no bounded report')
        result = json.loads(report_path.read_text(encoding='utf-8'))
        if (not isinstance(result, dict) or result.get('schema') != 'reflow.runtime-probe.v1' or
                result.get('adapter') != adapter or result.get('device') != device or
                result.get('model_loaded') is not False or result.get('status') not in ('passed', 'failed') or
                not isinstance(result.get('versions'), dict) or
                any(not isinstance(k, str) or not isinstance(v, str) for k, v in result['versions'].items()) or
                not isinstance(result.get('problems'), list) or
                any(not isinstance(problem, str) for problem in result['problems']) or
                (result['status'] == 'passed') != (not result['problems'])):
            raise ValueError('Runtime check returned an inconsistent report')
        return result
    except subprocess.TimeoutExpired:
        phase = 'startup'
        try:
            if report_path.is_file() and report_path.stat().st_size <= 65536:
                partial = json.loads(report_path.read_text(encoding='utf-8'))
                if isinstance(partial, dict) and isinstance(partial.get('phase'), str):
                    phase = partial['phase'][:100]
        except (OSError, ValueError):
            pass
        return dict(status='unverified', details=['Runtime check stopped after ' + str(timeout) + ' seconds during ' + phase + '. This timeout does not establish a broken installation.'], model_loaded=False)
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        return dict(status='failed', problems=[type(exc).__name__ + ': ' + str(exc)[:1500]], model_loaded=False)
    finally:
        try:
            if job:
                job.cleanup()
        finally:
            _gate.release()
