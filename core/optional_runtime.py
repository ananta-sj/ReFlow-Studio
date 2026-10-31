"""Explicit isolated feature workers; no installation during a render."""
import json
import os
from pathlib import Path
import tempfile

from core.render_context import current_job, run_process, check_cancelled
from core.python_runtime import project_root

ROOT = project_root()


def interpreter(profile):
    if profile not in {"vision", "f5", "musetalk"}:
        raise ValueError("Unknown optional runtime profile")
    executable = ROOT / "runtime_profiles" / profile / "python.exe"
    try:
        metadata = json.loads((executable.parent / "profile.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return str(executable) if executable.is_file() and metadata.get("status") == "ready" else None


def run_feature(profile, operation, params, timeout=3600):
    executable = interpreter(profile)
    if not executable:
        raise RuntimeError(f"Optional {profile} runtime is not installed")
    if profile == 'f5' and operation == 'f5_speech' and not params.get('reference_text', '').strip():
        from core.model_assets import ensure_assets
        ensure_assets('f5_asr')
    job = current_job()
    parent = str(job.workspace) if job else str(ROOT / "temp")
    os.makedirs(parent, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="feature-", dir=parent) as folder:
        request = Path(folder) / "request.json"
        request.write_text(json.dumps({"operation": operation, "params": params},
                                      allow_nan=False), encoding="utf-8")
        # File-backed diagnostics avoid buffering a whole video's worker log.
        log = Path(folder) / "worker.log"
        try:
            with log.open("w", encoding="utf-8") as stream:
                run_process([executable, "-B", str(ROOT / "core" / "feature_worker.py"),
                             str(request)], timeout=timeout, check=True,
                            stdout=stream, stderr=stream,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "TEMP": folder,
                                 "TMP": folder, "HF_HOME": str(ROOT / "models" / profile / "cache"),
                                 "TORCH_HOME": str(ROOT / "models" / profile / "torch-cache"),
                                 "PATH": str(ROOT / "ffmpeg" / "bin") + os.pathsep + os.environ.get("PATH", ""),
                                 **({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
                                    if os.environ.get("REFLOW_OFFLINE") == "1" else {})})
        except Exception as exc:
            from core.render_context import RenderCancelled
            if isinstance(exc, RenderCancelled):
                raise
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 6000))
                detail = stream.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{profile} worker failed: {detail}") from exc
        check_cancelled()

