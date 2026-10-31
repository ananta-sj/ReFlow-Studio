"""Job-owned cancellation, process handles and temporary workspaces."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

import psutil

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


def run_process(args, timeout=None, check=False, **kwargs):
    job = current_job()
    if job is None:
        return subprocess.run(args, timeout=timeout, check=check, **kwargs)
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
