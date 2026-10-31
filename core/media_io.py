"""Lightweight media publication/validation shared with isolated visual workers."""
import json,logging,math,os,subprocess,sys,tempfile
from contextlib import contextmanager
from core.render_context import current_job,run_process
from core.run_manifest import current_manifest
_LOW_PRIORITY_FLAGS=subprocess.BELOW_NORMAL_PRIORITY_CLASS if sys.platform=='win32' else 0
_FFPROBE_TIMEOUT_SEC=60
_DIAGNOSTIC_TAIL_BYTES=6000

def _run_media_command(cmd, timeout, **kwargs):
    """Keep diagnostics on disk, exposing only a bounded tail on failure."""
    with tempfile.TemporaryFile() as diagnostics:
        # Older callers suppressed stderr. Always retain it for failures.
        kwargs.pop("stderr", None)
        kwargs.pop("check", None)
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stdin", subprocess.DEVNULL)
        try:
            return run_process(cmd, timeout=timeout, creationflags=_LOW_PRIORITY_FLAGS,
                                  stderr=diagnostics, check=True, **kwargs)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, diagnostics.tell() - _DIAGNOSTIC_TAIL_BYTES))
            detail = diagnostics.read().decode("utf-8", errors="replace").strip()
            tool = os.path.basename(str(cmd[0]))
            if isinstance(exc, subprocess.TimeoutExpired):
                reason = f"timed out after {timeout}s"
            elif isinstance(exc, subprocess.CalledProcessError):
                reason = f"failed with exit code {exc.returncode}"
            else:
                reason = f"could not start: {exc}"
            raise RuntimeError(f"{tool} {reason}" + (f":\n{detail}" if detail else "")) from exc


@contextmanager
def _staged_output(output_path):
    """Replace the destination only after its new sibling has been produced."""
    destination = os.path.abspath(output_path)
    fd, pending = tempfile.mkstemp(prefix=".reflow-", suffix=os.path.splitext(destination)[1],
                                   dir=os.path.dirname(destination))
    os.close(fd)
    try:
        yield pending
        if not os.path.isfile(pending) or os.path.getsize(pending) == 0:
            raise RuntimeError(f"No usable output was produced for {destination}")
        job = current_job()
        if job:
            job.publish(pending, destination)
        else:
            os.replace(pending, destination)
    finally:
        try:
            if os.path.exists(pending):
                os.remove(pending)
        except OSError as exc:
            logging.warning("Could not remove staged output %s: %s", pending, exc)


def _validate_media(file_path, expected_streams):
    manifest = current_manifest()
    if manifest is None:
        return _validate_media_inner(file_path, expected_streams)
    with manifest.operation('media-validation', evidence={'path': os.path.abspath(file_path),
                            'required_streams': sorted(expected_streams)}) as item:
        duration = _validate_media_inner(file_path, expected_streams)
        item['duration_seconds'] = duration
        return duration


def _validate_media_inner(file_path, expected_streams):
    return validate_media_inner(file_path,expected_streams,_run_media_command)


def validate_media_inner(file_path,expected_streams,runner):
    result = runner(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type',
         '-of', 'json', file_path], _FFPROBE_TIMEOUT_SEC, stdout=subprocess.PIPE,
    )
    try:
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        streams = {stream['codec_type'] for stream in info['streams']}
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be finite and positive")
        missing = set(expected_streams) - streams
        if missing:
            raise ValueError(f"missing required streams: {', '.join(sorted(missing))}")
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Invalid media output {file_path}: {exc}") from exc
    return duration

