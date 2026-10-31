"""Generic streaming model downloader with live speed/ETA metrics.

Deliberately has no dependency on bridge/ (core/ stays UI-agnostic, same
as core/pipeline.py's generator-based progress reporting) - this is a
generator yielding progress dicts; whoever calls it (bridge/api.py) is
responsible for pushing those onto the frontend via bridge/push.py, the
same pattern already used for render progress.

Replaces core/model_manager.py's RVC-only download logic with something
usable for any stage type's local_file models.
"""

import os
import re
import threading
import time
import zipfile
import tempfile
import json
import sys
import subprocess
import uuid
import hashlib
from pathlib import Path, PurePosixPath
import stat
from fnmatch import fnmatch
from filelock import FileLock
from core.render_context import check_cancelled, current_job, RenderContext, bind_job, run_process
from core.python_runtime import project_root, worker_python

import requests

# A bare Hugging Face repo URL (https://huggingface.co/<org>/<repo>, no
# /resolve/, /blob/, /tree/ suffix) is a repo *page*, not a downloadable
# file - a plain GET against it returns the HTML model card, not any
# model weights. Found by actually inspecting what got downloaded for a
# real Marketplace connection: every "installed" local_file entry whose
# source_url was a bare repo link had silently downloaded a ~150-350KB
# HTML page instead of real weights, all still marked "installed" since
# nothing checked the content. Real HF repos are usually many files
# (config.json, tokenizer files, sharded weights) - snapshot_download()
# is the correct way to fetch the whole thing, matching how every other
# HF-repo consumer in this codebase (transformers' from_pretrained,
# TTS's model loader) already expects a real local repo directory.
_HF_REPO_ROOT_RE = re.compile(r"^https://huggingface\.co/([^/\s?#]+/[^/\s?#]+)/?$")


def resolve_download_url(url: str) -> str:
    """Auto-fixes HuggingFace 'blob' (viewer) links to 'resolve' (raw)
    links - the same fix core/model_manager.py already had."""
    if "huggingface.co" in url and "/blob/" in url:
        return url.replace("/blob/", "/resolve/")
    return url


def hf_repo_id_for_url(url: str):
    """Returns the "org/repo" id if url is a bare HF repo-root link,
    else None (a /resolve/ or /blob/ link to one specific file, or any
    non-HF URL, is left to the single-file download path below)."""
    m = _HF_REPO_ROOT_RE.match(url.split("?")[0].rstrip("/"))
    return m.group(1) if m else None


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        # HF can preallocate incomplete files to their full eventual length.
        # Counting those cache files would report completion before transfer.
        _dirs[:] = [name for name in _dirs if name not in ('.cache', '.hf-cache')]
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _snapshot_progress(repo_id: str, dest_dir: str, allow_patterns=None, revision=None):
    """An owned process performs HF transfer; progress counts finished files.

    File caches can be preallocated before transfer, so their length must not
    be presented as downloaded bytes. Speed and ETA remain unknown until
    completion. A controller thread uses existing process cancellation and
    timeout machinery, and always joins before staging cleanup.
    """
    if os.environ.get("REFLOW_OFFLINE") == "1":
        raise RuntimeError("Offline mode: model downloads are disabled")
    from huggingface_hub import HfApi

    os.makedirs(dest_dir, exist_ok=True)

    total = None
    try:
        info = HfApi().model_info(repo_id, files_metadata=True, revision=revision, timeout=10)
        sizes = [f.size for f in (info.siblings or []) if f.size and
                 (not allow_patterns or any(fnmatch(f.rfilename, pattern) for pattern in allow_patterns))]
        total = sum(sizes) if sizes else None
    except Exception:
        total = None  # repo metadata lookup failing isn't fatal - the
        # download itself still proceeds, just without a percent/ETA.

    result = {}
    parent_job = current_job()
    job = parent_job or RenderContext(project_root() / 'temp')
    request = job.workspace / ('hf-transfer-' + uuid.uuid4().hex + '.json')
    log_path = request.with_suffix('.log')
    request.write_text(json.dumps({'repo_id': repo_id, 'dest_dir': dest_dir,
        'cache_dir': os.path.join(os.path.dirname(dest_dir), '.hf-cache'),
        'allow_patterns': allow_patterns, 'revision': revision}), encoding='utf-8')

    def _run():
        try:
            with bind_job(job), log_path.open('wb') as log:
                run_process([worker_python(), '-B', str(project_root() / 'core/run_hf_download.py'), str(request)],
                            check=True, timeout=3600, stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            result['path'] = dest_dir
        except subprocess.CalledProcessError as exc:
            with log_path.open('rb') as log:
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 6000))
                detail = log.read().decode('utf-8', errors='replace')
            result['error'] = RuntimeError(f'Repository transfer failed: {detail}')
        except Exception as e:
            result["error"] = e

    worker = threading.Thread(target=_run, daemon=True)
    start_time = time.time()
    worker.start()

    try:
        while worker.is_alive():
            check_cancelled()
            worker.join(timeout=1.0)
            downloaded = _dir_size(dest_dir)
            percent = min(99, downloaded / total * 100) if total else None
            yield {
                "phase": "downloading", "downloaded": downloaded, "total": total,
                "percent": percent, "speed_bps": 0, "eta_seconds": None,
                "progress_basis": "completed files; the current file may still be transferring",
            }
    finally:
        if worker.is_alive():
            job.request_stop()
        worker.join()  # run_process terminates the owned transfer on stop.
        if not parent_job:
            job.cleanup()

    if "error" in result:
        raise result["error"]

    downloaded = _dir_size(dest_dir)
    total_elapsed = max(time.time() - start_time, 0.001)
    yield {
        "phase": "done", "downloaded": downloaded, "total": total or downloaded,
        "percent": 100.0, "speed_bps": downloaded / total_elapsed, "eta_seconds": 0,
    }


def _download_hf_snapshot(repo_id, dest_dir, allow_patterns=None, revision=None):
    destination = os.path.abspath(dest_dir)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with FileLock(destination + '.lock', timeout=30):
        if os.path.exists(destination):
            raise RuntimeError('Repository destination already exists; retain it and use a new managed download')
        with tempfile.TemporaryDirectory(prefix='.repo-download-', dir=os.path.dirname(destination)) as directory:
            staging = os.path.join(directory, 'snapshot')
            done = None
            producer = (_snapshot_progress(repo_id, staging, allow_patterns=allow_patterns, revision=revision)
                        if allow_patterns or revision else _snapshot_progress(repo_id, staging))
            try:
                for progress in producer:
                    if progress['phase'] == 'done':
                        done = progress
                    else:
                        yield progress
            finally:
                producer.close()
            files = [path for path in Path(staging).rglob('*')
                     if path.is_file() and '.cache' not in path.relative_to(staging).parts]
            if not files or not any(path.stat().st_size for path in files):
                raise RuntimeError('Repository contains no nonempty model artifacts')
            check_cancelled()
            os.replace(staging, destination)
            yield done


def download_with_progress(url: str, dest_path: str, chunk_size: int = 256 * 1024, *, allow_patterns=None, revision=None, expected_size=None, expected_sha256=None):
    """Generator yielding progress dicts as the download proceeds:
    {"phase": "downloading"|"done", "downloaded": int, "total": int|None,
     "percent": float|None, "speed_bps": float, "eta_seconds": float|None}

    Metrics are computed over a rolling ~0.5s window (not per-chunk) so
    speed/ETA are stable numbers, not noisy per-packet jitter.

    dest_path is a *file* path for a direct single-file URL, but is
    treated as a *directory* when url is a bare HF repo root - see
    hf_repo_id_for_url() - since a whole repo is many files, not one.
    """
    repo_id = hf_repo_id_for_url(url)
    if repo_id:
        if expected_size is not None or expected_sha256 is not None:
            raise ValueError('File size/checksum validation requires a single-file URL')
        if allow_patterns or revision:
            yield from _download_hf_snapshot(repo_id, dest_path, allow_patterns, revision)
        else:
            yield from _download_hf_snapshot(repo_id, dest_path)
        return

    url = resolve_download_url(url)
    if expected_sha256 is not None and not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected SHA-256 must be 64 lowercase hexadecimal characters')
    digest = hashlib.sha256()
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    if os.environ.get('REFLOW_OFFLINE') == '1':
        raise RuntimeError('Offline mode: model downloads are disabled')
    start_time = time.monotonic()
    downloaded = 0
    window_start_time = start_time
    window_start_bytes = 0
    destination = os.path.abspath(dest_path)
    with FileLock(destination + '.lock', timeout=30):
        fd, partial = tempfile.mkstemp(prefix='.model-download-', suffix='.tmp', dir=os.path.dirname(destination))
        try:
            with os.fdopen(fd, 'wb') as stream:
                with requests.get(url, stream=True, headers={'Accept-Encoding': 'identity'}, timeout=(15, 120)) as response:
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'text/html' in content_type or 'application/xhtml' in content_type:
                        raise RuntimeError('Model server returned an HTML page')
                    encoding = response.headers.get('Content-Encoding', '').lower()
                    total = int(response.headers.get('Content-Length', 0)) or None
                    if total is not None and total < 0:
                        raise RuntimeError('Invalid model Content-Length')
                    first = True
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        check_cancelled()
                        if not chunk:
                            continue
                        if first:
                            prefix = chunk[:512].lstrip().lower()
                            if prefix.startswith((b'<!doctype html', b'<html')):
                                raise RuntimeError('Model server returned an HTML page')
                            first = False
                        stream.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        interval = now - window_start_time
                        if interval >= 0.5:
                            speed = (downloaded - window_start_bytes) / max(interval, .001)
                            yield {'phase': 'downloading', 'downloaded': downloaded, 'total': total,
                                   'percent': min(100, downloaded / total * 100) if total else None,
                                   'speed_bps': speed,
                                   'eta_seconds': max(0, (total - downloaded) / speed) if total and speed > 0 else None}
                            window_start_time, window_start_bytes = now, downloaded
                    if not downloaded or (total and encoding in ('', 'identity') and downloaded != total):
                        raise RuntimeError(f'Incomplete model download: {downloaded} bytes, expected {total}')
                    if expected_size is not None and downloaded != expected_size:
                        raise RuntimeError(f'Incomplete model download: {downloaded} bytes, expected asset size {expected_size}')
                    if expected_sha256 is not None and digest.hexdigest() != expected_sha256:
                        raise RuntimeError('Model download checksum mismatch')
                    if encoding not in ('', 'identity'):
                        raise RuntimeError('Compressed model response cannot be verified against Content-Length')
                stream.flush()
                os.fsync(stream.fileno())
            check_cancelled()
            os.replace(partial, destination)
        finally:
            if os.path.exists(partial):
                os.unlink(partial)
    elapsed = max(time.monotonic() - start_time, .001)
    yield {'phase': 'done', 'downloaded': downloaded, 'total': total or downloaded,
           'percent': 100.0, 'speed_bps': downloaded / elapsed, 'eta_seconds': 0}


def extract_archive(archive_path: str, dest_dir: str) -> list[str]:
    """Extracts a .zip into dest_dir. Returns the list of extracted file
    paths. Deliberately doesn't hunt for specific extensions (.pth, etc.)
    - that convention-specific knowledge belongs to whichever provider
    actually loads the model (e.g. an RVC provider knowing to look for
    .pth + .index), not this generic downloader."""
    root = Path(dest_dir).resolve()
    with zipfile.ZipFile(archive_path, 'r') as archive:
        members = archive.infolist()
        if sum(member.file_size for member in members) > 8 * 1024 ** 3:
            raise RuntimeError('Model archive exceeds the 8 GiB unpacked limit')
        paths = []
        seen = set()
        for member in members:
            name = member.filename.replace('\\', '/')
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or ':' in name or stat.S_ISLNK(member.external_attr >> 16):
                raise RuntimeError('Unsafe model archive member: ' + name)
            target = (root / name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError('Model archive path escapes destination')
            key = os.path.normcase(str(target))
            if key in seen:
                raise RuntimeError('Duplicate model archive member: ' + name)
            seen.add(key)
            if target.exists() and not member.is_dir():
                raise RuntimeError('Model archive would overwrite an existing file: ' + name)
            paths.append((member, target))
        root.mkdir(parents=True, exist_ok=True)
        for member, target in paths:
            check_cancelled()
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open('xb') as output:
                    while True:
                        check_cancelled()
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
        return [str(target) for member, target in paths if not member.is_dir()]
