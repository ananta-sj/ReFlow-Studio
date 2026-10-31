"""Existing optional/core dependencies only; no weights or model invocation."""
import hashlib
import json
from pathlib import Path
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core.runtime_probe import probe
from core.optional_runtime import interpreter
from core.python_runtime import worker_python, inprocess_python


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/validation/2026-10-09-optional-engines-installed.json')
    args = parser.parse_args()
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    state = {name: sha(ROOT / name) for name in ('models.json', 'settings.json')}
    code = {name: sha(ROOT / name) for name in ('core/runtime_probe.py', 'core/runtime_probe_worker.py', 'core/runtime_probe_contract.py', 'core/engine_readiness.py')}
    observations = []
    path = args.report
    for adapter, profile in (('nudenet', 'vision'), ('f5tts', 'f5'), ('musetalk', 'musetalk'), ('rvc', None), ('gfpgan', None), ('wav2lip', None)):
        started = time.monotonic()
        executable = interpreter(profile) if profile else (worker_python() if adapter == 'wav2lip' else inprocess_python())
        result = probe(adapter, executable, 'cpu') if executable else dict(status='failed', problems=['Optional runtime is not installed'], model_loaded=False)
        observations.append(dict(adapter=adapter, interpreter=executable, elapsed_seconds=time.monotonic()-started, result=result))
        report = dict(schema='reflow.optional-engine-observations.v1', observations=observations,
                      saved_state_unchanged=state == {name: sha(ROOT / name) for name in state},
                      source_unchanged=code == {name: sha(ROOT / name) for name in code}, source_sha256=code)
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(adapter, result['status'], result.get('problems', result.get('details', [])), flush=True)


if __name__ == '__main__':
    main()
