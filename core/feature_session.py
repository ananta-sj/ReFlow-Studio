"""Job-owned isolated speech session with bounded diagnostics and shutdown."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from core.render_context import bind_job, current_job, run_process
from core.optional_runtime import ROOT, interpreter


class FeatureSession:
    def __init__(self, job, executable, params, worker=None, operation='f5_session'):
        self.job = job
        self.label = params.get('session_label', 'F5 speech')
        self.folder = job.workspace / ('f5-session-' + uuid.uuid4().hex)
        self.folder.mkdir()
        self.log = self.folder / 'worker.log'
        self.request = self.folder / 'session.json'
        self.request.write_text(json.dumps({'operation': operation,
            'params': {**params, 'session_dir': str(self.folder)}}), encoding='utf-8')
        self.lock = threading.Lock()
        self.finished = threading.Event()
        self.failure = None
        self.closed = False
        self.sequence = 0
        self.executable = executable
        self.worker = worker or ROOT / 'core/feature_worker.py'
        self.thread = threading.Thread(target=self._run, daemon=True)
        job.on_cleanup(self.close)
        try:
            self.thread.start()
        except Exception as exc:
            self.failure = exc
            self.closed = True
            self.finished.set()
            raise

    def _run(self):
        try:
            with bind_job(self.job), self.log.open('wb') as log:
                run_process([self.executable, '-B', str(self.worker), str(self.request)],
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=24 * 3600,
                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'TEMP': str(self.folder), 'TMP': str(self.folder),
                         'HF_HOME': str(ROOT / 'models/f5/cache'), 'TORCH_HOME': str(ROOT / 'models/f5/torch-cache'),
                         'PATH': str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''),
                         **({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
                            if os.environ.get('REFLOW_OFFLINE') == '1' else {})})
        except Exception as exc:
            self.failure = exc
        finally:
            self.finished.set()

    def _diagnostic(self):
        if not self.log.exists():
            return str(self.failure or 'worker stopped')
        with self.log.open('rb') as log:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - 6000))
            return log.read().decode('utf-8', errors='replace')

    def call(self, params, timeout=3600):
        with self.lock:
            self.job.check()
            if self.closed:
                raise RuntimeError(self.label+' session is closed')
            self.sequence += 1
            request = self.folder / f'call-{self.sequence:08d}.json'
            pending = request.with_suffix('.tmp')
            pending.write_text(json.dumps(params, allow_nan=False), encoding='utf-8')
            os.replace(pending, request)
            response = request.with_suffix('.response.json')
            deadline = time.monotonic() + timeout
            while not response.exists():
                self.job.check()
                if not self.folder.is_dir() or not request.is_file():
                    self.job.request_stop()
                    raise RuntimeError(self.label+' request workspace was removed or changed; inference stopped.')
                if self.finished.is_set():
                    raise RuntimeError(self.label+' worker stopped: ' + self._diagnostic()) from self.failure
                if time.monotonic() >= deadline:
                    self.job.request_stop()
                    raise TimeoutError(self.label+' inference exceeded its time limit: ' + self._diagnostic())
                self.finished.wait(.05)
            result = json.loads(response.read_text(encoding='utf-8'))
            request.unlink()
            response.unlink()
            if not isinstance(result, dict):
                raise RuntimeError(self.label+' worker returned an invalid response')
            if not result.get('ok'):
                raise RuntimeError(self.label+' inference failed: ' + str(result.get('error', 'unknown failure')))
            self.job.check()
            return result

    def close(self):
        if self.closed and not self.thread.is_alive():
            return
        self.closed = True
        if self.folder.is_dir():
            (self.folder / 'stop').touch()
        else:
            self.job.request_stop()
        if self.thread.ident is None:
            return
        self.thread.join(10)
        if self.thread.is_alive():
            # A slow library shutdown must not cancel later render stages.
            # Match the owned Popen by its exact session invocation; never use
            # a PID supplied by worker responses or stop unrelated job workers.
            from core.render_context import _stop_process
            expected = [self.executable, '-B', str(self.worker), str(self.request)]
            with self.job.lock:
                owned = [process for process in self.job.processes if process.args == expected]
            for process in owned:
                _stop_process(process)
            self.thread.join(10)
        if self.thread.is_alive():
            raise RuntimeError(self.label+' session did not stop; its workspace is preserved')


def run_cached_f5(contract, params):
    job = current_job()
    executable = interpreter('f5')
    if not job or not executable:
        raise RuntimeError('Cached F5 speech requires a render job and its optional runtime')
    if not params.get('reference_text', '').strip():
        from core.model_assets import ensure_assets
        ensure_assets('f5_asr')
    checkpoint = Path(contract['checkpoint_path'])
    stat = checkpoint.stat()
    vocab = Path(contract['vocab_path'])
    vocab_stat = vocab.stat()
    key = (str(checkpoint.resolve()), stat.st_size, stat.st_mtime_ns, contract['recipe'],
           str(vocab.resolve()), vocab_stat.st_size, vocab_stat.st_mtime_ns)
    with job.lock:
        sessions = getattr(job, '_f5_sessions', None)
        if sessions is None:
            sessions = job._f5_sessions = {}
        if key not in sessions:
            sessions[key] = FeatureSession(job, executable, {**contract, 'device': 'cpu'})
        session = sessions[key]
    return session.call(params)
