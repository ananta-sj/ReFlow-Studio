from core.render_context import current_job, check_cancelled, run_process
from core.python_runtime import project_root, worker_python
"""Local MuseTalk lip-sync provider - for a "local_file" Lipsync
Marketplace entry, distinct from the Wav2Lip default
(core/providers/lipsync/wav2lip_local.py), which never actually loads a
Marketplace-connected local_file model - see core/providers/resolve.py.

Shells out to core/MuseTalk/scripts/inference.py in a fresh subprocess,
matching LipSyncHandler's existing pattern for Wav2Lip (core/
lipsync_handler.py) - isolates MuseTalk's real, vendored third-party
inference code (see core/MuseTalk/ - a genuine port of TMElyralab's
MuseTalk repo, DWPose swapped for the `face-alignment` package since
mmcv doesn't support this project's torch version, see
core/MuseTalk/musetalk/utils/preprocessing.py's patch note) from this
process, and reuses the timeout/crash-isolation reasoning already
established for Wav2Lip.
"""

import os
import subprocess
import sys
import uuid
import config

from core.providers.base import LipSyncProvider

_MUSETALK_DIR = str(project_root() / 'core/MuseTalk')


class MuseTalkLocalProvider(LipSyncProvider):
    def __init__(self, device=None, models_dir=None):
        self.device = device
        self.explicit_models = models_dir is not None
        self.models_dir = models_dir or os.path.join(_MUSETALK_DIR, "models")
        self.unet_model_path = os.path.join(self.models_dir, "musetalkV15", "unet.pth")
        self.unet_config = os.path.join(self.models_dir, "musetalkV15", "musetalk.json")
        self.whisper_dir = os.path.join(self.models_dir, "whisper")
        self.vae_type = "sd-vae"

    def execute(self, video_path, audio_path, output_path):
        from core.model_assets import ensure_assets
        if not self.explicit_models:
            ensure_assets("musetalk")
        if not os.path.exists(self.unet_model_path):
            print(f"[MUSETALK] CRITICAL: UNet checkpoint missing at {self.unet_model_path}")
            raise RuntimeError("MuseTalk UNet checkpoint is missing")

        import yaml

        task_id = "reflow_job"
        result_name = "result.mp4"
        work_dir = os.path.join(str(current_job().workspace) if current_job() else config.TEMP_PATH, "musetalk-" + uuid.uuid4().hex)
        os.makedirs(work_dir, exist_ok=True)
        result_dir = os.path.join(work_dir, "results")
        os.makedirs(result_dir, exist_ok=True)

        config_path = os.path.join(work_dir, "_reflow_inference_config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                task_id: {
                    "video_path": os.path.abspath(video_path),
                    "audio_path": os.path.abspath(audio_path),
                    "result_name": result_name,
                }
            }, f)

        # -m scripts.inference (not a plain script path) - scripts/inference.py
        # lives one level below core/MuseTalk/ (where the `musetalk` package
        # actually sits), so running it as a plain script only puts
        # scripts/ itself on sys.path, not core/MuseTalk/ - `from
        # musetalk.utils.blending import get_image` then fails with
        # ModuleNotFoundError. -m imports it as a module instead, which
        # puts the CWD (core/MuseTalk/, via cwd= below) on sys.path -
        # confirmed by hitting the plain-script ModuleNotFoundError for
        # real first, not assumed.
        cmd = [
            worker_python(), "-m", "scripts.inference",
            "--unet_model_path", self.unet_model_path,
            "--unet_config", self.unet_config,
            "--whisper_dir", self.whisper_dir,
            "--vae_type", self.vae_type,
            "--models_dir", self.models_dir,
            "--device", self.device or config.DEVICE,
            "--inference_config", config_path,
            "--result_dir", result_dir,
            "--version", "v15",
        ]

        print("[MUSETALK] Starting processing...")
        try:
            # MuseTalk's own frame-by-frame face detection + UNet
            # inference over a whole video is legitimately slow on CPU -
            # same reasoning as Wav2Lip's own timeout (core/
            # lipsync_handler.py): an unbounded call would block the
            # render thread indefinitely on a genuine hang instead of
            # surfacing a real, actionable error.
            # encoding="utf-8" here decodes the *captured pipe bytes* on
            # this (parent) process's side - PYTHONIOENCODING in env=
            # below only controls how the child encodes its own output,
            # not how run_process() decodes what it captures. Without
            # this, text=True falls back to locale.getpreferredencoding()
            # (cp1252 on this machine), which can't decode real bytes
            # MuseTalk's own output produces - hit as a real
            # UnicodeDecodeError before this fix, not assumed.
            from core.optional_runtime import interpreter, run_feature
            if interpreter('musetalk'):
                cmd[cmd.index('--device') + 1] = 'cpu'
                run_feature('musetalk', 'musetalk', {'args': cmd[3:], 'device': 'cpu'})
                process = subprocess.CompletedProcess(cmd, 0, stdout='')
            else:
                process = run_process(
                cmd, cwd=_MUSETALK_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=3600, check=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            print("[MUSETALK] Execution timed out after 3600s")
            raise RuntimeError("MuseTalk timed out after 3600 seconds")
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

        result_path = os.path.join(result_dir, "v15", result_name)
        check_cancelled()
        if os.path.exists(result_path) and os.path.getsize(result_path) > 1000:
            print("[MUSETALK] Success! Saving result...")
            from pipeline import _validate_media
            _validate_media(result_path, {"video"})
            check_cancelled()
            os.replace(result_path, output_path)
            return output_path

        print("\n" + "!" * 40)
        print("[MUSETALK] ENGINE FAILURE")
        print("FULL LOGS (DEBUG):")
        print(process.stdout)
        print("!" * 40 + "\n")
        raise RuntimeError("MuseTalk produced no valid video; " + (process.stdout or "")[-6000:])
