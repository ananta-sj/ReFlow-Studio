"""Retain bounded, offline import timings/stacks without loading model weights."""
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def worker(adapter, destination):
    from core.runtime_probe_worker import inspect
    def offline(event, args):
        if event == 'socket.connect':
            raise RuntimeError('Network access is disabled during import diagnostics')
    sys.addaudithook(offline)
    faulthandler.dump_traceback_later(30, repeat=True)
    started = time.monotonic()
    events = []
    def progress(report):
        events.append(dict(phase=report['phase'], elapsed_seconds=time.monotonic()-started))
        Path(destination).write_text(json.dumps(dict(events=events, result=report)), encoding='utf-8')
        print(events[-1], flush=True)
    try:
        report = inspect(adapter, 'cpu', progress)
        Path(destination).write_text(json.dumps(dict(events=events, result=report)), encoding='utf-8')
        print('RESULT', report['status'], report['problems'], flush=True)
    finally:
        faulthandler.cancel_dump_traceback_later()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', choices=('optional-import', 'optional-workflow'), default='optional-import')
    label = parser.parse_args().label
    from core.optional_runtime import interpreter
    from core.render_context import RenderContext, bind_job, run_process
    def sha(name):
        return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    names = ('models.json', 'settings.json', 'core/runtime_probe_worker.py', 'core/runtime_probe_contract.py')
    before = {name: sha(name) for name in names}
    output = ROOT / ('docs/validation/2026-10-09-' + label + '-diagnostic.json')
    observations = []
    for adapter, profile in (('f5tts', 'f5'), ('musetalk', 'musetalk')):
        executable = interpreter(profile)
        if not executable:
            raise RuntimeError('Existing optional interpreter is unavailable: ' + profile)
        job = RenderContext(ROOT / 'temp')
        destination = job.workspace / 'progress.json'
        log = ROOT / ('docs/validation/2026-10-09-' + (label + '-' if label != 'optional-import' else '') + adapter + '-import-stacks.log')
        env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'REFLOW_OFFLINE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8',
               'TEMP': str(job.workspace), 'TMP': str(job.workspace),
               'HF_HOME': str(job.workspace / 'hf'), 'TORCH_HOME': str(job.workspace / 'torch'),
               'XDG_CACHE_HOME': str(job.workspace / 'cache'), 'MPLCONFIGDIR': str(job.workspace / 'matplotlib')}
        started = time.monotonic()
        timed_out = False
        try:
            with bind_job(job), log.open('wb') as stream:
                try:
                    run_process([executable, '-B', str(Path(__file__).resolve()), '--worker', adapter, str(destination)],
                                timeout=90, check=True, stdout=stream, stderr=stream, env=env,
                                **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
                except subprocess.TimeoutExpired:
                    timed_out = True
            payload = json.loads(destination.read_text(encoding='utf-8')) if destination.is_file() else {}
            observations.append(dict(adapter=adapter, interpreter=executable, timed_out=timed_out,
                                     elapsed_seconds=time.monotonic()-started, **payload))
            output.write_text(json.dumps(dict(observations=observations, source_sha256=before,
                              captured_files_unchanged=before == {name: sha(name) for name in names}), indent=2), encoding='utf-8')
            print(adapter, 'timeout' if timed_out else payload.get('result', {}).get('status'), flush=True)
        finally:
            job.cleanup()


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        worker(*sys.argv[2:])
    else:
        main()
