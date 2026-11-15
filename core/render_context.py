"""Job-owned cancellation, process handles and temporary workspaces."""
from contextlib import contextmanager
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

import psutil
from core.worker_lifetime import watch_parent

watch_parent()

_local = threading.local()


class RenderCancelled(RuntimeError):
    pass


def current_job():
    return getattr(_local, "job", None)


def check_cancelled():
    job = current_job()
    if job:
        job.check()


@contextmanager
def bind_job(job):
    previous = current_job()
    _local.job = job
    try:
        yield
    finally:
        _local.job = previous


class RenderContext:
    def __init__(self, temp_root):
        self.root = Path(temp_root).resolve()
        jobs = self.root / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        if jobs.is_symlink() or jobs.resolve() != jobs or getattr(jobs.lstat(), "st_file_attributes", 0) & 0x400:
            raise RuntimeError("Unsafe job workspace root.")
        self.workspace = Path(tempfile.mkdtemp(prefix="job-", dir=jobs))
        (self.workspace/'workspace-owner.json').write_text(json.dumps(dict(
            schema='reflow.workspace-owner.v1',workspace=self.workspace.name,pid=os.getpid(),
            process_created=psutil.Process().create_time(),created_at=time.time())),encoding='utf-8')
        self.cancelled = threading.Event()
        self.lock = threading.RLock()
        self.processes = set()
        self.cleanup_callbacks = []

    def on_cleanup(self, callback):
        with self.lock:
            self.check()
            self.cleanup_callbacks.append(callback)

    def check(self):
        if self.cancelled.is_set():
            raise RenderCancelled("Render cancellation requested.")

    def request_stop(self):
        with self.lock:
            self.cancelled.set()

    def publish(self, pending, destination):
        # Windows scanners/readers may briefly deny rename/delete sharing.
        # Keep each atomic replacement under the cancellation lock, but release
        # that lock during the bounded waits so Stop can prevent the next try.
        for attempt in range(4):
            with self.lock:
                self.check()
                try:
                    os.replace(pending, destination)
                    return
                except PermissionError as error:
                    if (os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32) or
                            attempt == 3 or os.path.isdir(destination) or
                            (os.path.isdir(pending) and os.path.exists(destination))):
                        raise
            self.cancelled.wait(.05 * (2 ** attempt))

    def cleanup(self):
        while self.cleanup_callbacks:
            callback = self.cleanup_callbacks[-1]
            callback()
            self.cleanup_callbacks.pop()
        if self.processes:
            raise RuntimeError("Cannot clean workspace while owned processes are registered.")
        path = self.workspace
        jobs = self.root / "jobs"
        if (self.root.resolve() != self.root or jobs.resolve() != jobs or
                path.parent != jobs or path.resolve() != path):
            raise RuntimeError(f"Unsafe cleanup path: {path}")
        if not path.exists():
            return
        # Refuse reparse points anywhere in the owned tree instead of following
        # junctions/symlinks supplied by an external actor.
        for directory, dirs, files in os.walk(path, followlinks=False):
            for entry in [Path(directory), *(Path(directory) / name for name in dirs + files)]:
                stat = entry.lstat()
                if entry.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
                    raise RuntimeError(f"Cleanup refused reparse point: {entry}")
        shutil.rmtree(path)


def _stop_process(process):
    """Snapshot only this Popen's descendants; psutil tracks PID identity."""
    try:
        parent = psutil.Process(process.pid)
        children = list({child: None for child in [*getattr(process, "_reflow_children", []), *parent.children(recursive=True)]})
    except psutil.NoSuchProcess:
        children = getattr(process, "_reflow_children", [])
    process._reflow_children = children
    process.terminate() if process.poll() is None else None
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(children, timeout=1)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
    process.wait(timeout=5)
    _, alive = psutil.wait_procs(children, timeout=5)
    if alive:
        raise RuntimeError("Owned subprocess descendants did not exit; workspace retained.")


def run_process(args, timeout=None, check=False, activity_path=None, idle_timeout=None, **kwargs):
    if isinstance(args,(list,tuple)) and args:
        stem=Path(str(args[0])).stem.lower()
        suffix=stem.removeprefix('python')
        if (stem in ('python','pythonw') or (stem.startswith('python') and suffix.replace('.','').isdigit())) and (len(args)<2 or args[1]!='-B'):
            args=[args[0],'-B',*args[1:]]
    job = current_job()
    if job is None:
        return subprocess.run(args, timeout=timeout, check=check, **kwargs)
    # Long video encodes must not be killed at the short command deadline
    # while FFmpeg is still reporting activity. Keep cancellation, an idle
    # deadline and an absolute upper bound. The diagnostic file belongs to
    # the caller and is retained for its normal bounded error reporting.
    activity_stream = None
    if (isinstance(args, (list, tuple)) and args
            and Path(str(args[0])).stem.lower() == 'ffmpeg'
            and '-c:v' in args and timeout == 1800
            and activity_path is None and idle_timeout is None):
        stream = kwargs.get('stderr')
        try:
            if stream is not None and os.fstat(stream.fileno()):
                activity_stream = stream
                timeout, idle_timeout = 24 * 3600, 1800
        except (AttributeError, OSError, ValueError):
            pass
    if kwargs.pop('capture_output', False):
        if kwargs.get('stdout') is not None or kwargs.get('stderr') is not None:
            raise ValueError('stdout and stderr arguments may not be used with capture_output.')
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    job.check()
    with job.lock:
        job.check()
        process = subprocess.Popen(args, **kwargs)
        job.processes.add(process)
    deadline = time.monotonic() + timeout if timeout is not None else None
    last_activity = time.monotonic()
    activity_stamp = None
    exited = False
    try:
        while True:
            try:
                process._reflow_children = list({child: None for child in [
                    *getattr(process, "_reflow_children", []),
                    *psutil.Process(process.pid).children(recursive=True)]})
            except psutil.NoSuchProcess:
                pass
            if job.cancelled.is_set():
                _stop_process(process)
                exited = True
                raise RenderCancelled("Owned subprocess stopped.")
            if (activity_path is not None or activity_stream is not None) and idle_timeout is not None:
                try:
                    info = (os.fstat(activity_stream.fileno()) if activity_stream is not None
                            else Path(activity_path).stat())
                    stamp = (info.st_size, info.st_mtime_ns)
                    if stamp != activity_stamp:
                        activity_stamp, last_activity = stamp, time.monotonic()
                except FileNotFoundError:
                    pass
                if time.monotonic()-last_activity >= idle_timeout:
                    _stop_process(process)
                    exited = True
                    raise TimeoutError(f'Processing stopped after {idle_timeout:g} seconds without reported activity.')
            if deadline is not None and time.monotonic() >= deadline:
                _stop_process(process)
                exited = True
                raise subprocess.TimeoutExpired(args, timeout)
            try:
                stdout, stderr = process.communicate(timeout=.1)
                if any(child.is_running() for child in getattr(process, "_reflow_children", [])):
                    _stop_process(process)
                exited = True
                break
            except subprocess.TimeoutExpired:
                continue
        job.check()
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    finally:
        if not exited:
            _stop_process(process)
            exited = True
        if exited:
            with job.lock:
                job.processes.discard(process)


def wait_or_cancel(seconds):
    job = current_job()
    if job:
        job.cancelled.wait(seconds)
        job.check()
    else:
        time.sleep(seconds)
