"""Read-only import diagnostics; no model loading, GUI launch, or downloads."""
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
os.environ["PYTHONIOENCODING"] = "utf-8"
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

results = {"python": sys.version, "executable": sys.executable, "imports": {}}
for name in ("torch", "torchaudio", "cv2", "webview", "TTS.api", "rvc_python",
             "faster_whisper", "f5_tts", "diffusers", "face_alignment", "torchcodec", "bridge.api"):
    try:
        module = importlib.import_module(name)
        results["imports"][name] = {"status": "ok", "version": getattr(module, "__version__", None)}
    except Exception as exc:
        results["imports"][name] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
print(json.dumps(results, indent=2))
