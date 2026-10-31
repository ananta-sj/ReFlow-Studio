from core.render_context import current_job, check_cancelled, run_process, RenderCancelled
from core.python_runtime import worker_python
import os
import subprocess
import sys
import logging
import shutil
import uuid

# Ensure config is loaded from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logging.basicConfig(level=logging.INFO)

class LipSyncHandler:
    def __init__(self, model_path=None, device=None):
        self.device = device or config.DEVICE
        self.explicit_model = model_path is not None
        # [FIX] DYNAMIC PATHING
        self.root_dir = config.BASE_DIR
        self.wav2lip_dir = os.path.join(self.root_dir, "core", "Wav2Lip")
        self.checkpoints_dir = os.path.join(self.wav2lip_dir, "checkpoints")
        
        # Smart Search for GAN Model
        self.model_path = os.path.join(self.checkpoints_dir, "Wav2Lip_GAN.pth")
        if not os.path.exists(self.model_path):
            print(f"[LIPSYNC] GAN model not found. Falling back to standard.")
            self.model_path = os.path.join(self.checkpoints_dir, "wav2lip.pth")
        if model_path is not None:
            self.model_path = model_path

    def execute(self, video_path, audio_path, output_path):
        if not os.path.exists(self.model_path) and not getattr(self, "explicit_model", False):
            from core.model_assets import ensure_assets
            self.model_path = str(ensure_assets("wav2lip")[0])
        if not os.path.exists(self.model_path):
            print(f"[LIPSYNC] Model file is missing at {self.model_path}")
            raise RuntimeError("Lip-sync checkpoint is missing")

        print(f"[LIPSYNC] Loading engine using: {os.path.basename(self.model_path)}")
        
        # 1. SETUP LOCAL FILENAMES
        local_video = "temp_input.mp4"
        local_audio = "temp_input.wav"
        local_output = "temp_output.mp4"

        work_dir = os.path.join(str(current_job().workspace) if current_job() else config.TEMP_PATH, "wav2lip-" + uuid.uuid4().hex)
        os.makedirs(work_dir, exist_ok=True)
        full_video_path = os.path.join(work_dir, local_video)
        full_audio_path = os.path.join(work_dir, local_audio)
        full_output_path = os.path.join(work_dir, local_output)
        
        # Cleanup
        for f in [full_output_path, full_video_path, full_audio_path]:
            if os.path.exists(f): os.remove(f)

        # 2. COPY INPUTS
        shutil.copy(audio_path, full_audio_path)
        shutil.copy(video_path, full_video_path)

        # 3. RUN INFERENCE
        inference_script = "inference.py"
        
        cmd = [
            worker_python(), os.path.join(self.wav2lip_dir, inference_script),
            "--checkpoint_path", self.model_path,
            "--device", getattr(self, "device", config.DEVICE),
            "--face", full_video_path,
            "--audio", full_audio_path,
            "--outfile", full_output_path,
            "--work_dir", work_dir,
            "--nosmooth",
            "--resize_factor", "1",
            "--pads", "0", "20", "0", "0"
        ]

        try:
            print("[LIPSYNC] Starting processing...")
            
            # [IMPROVED DEBUGGING] Capture STDOUT and STDERR together
            # timeout: Wav2Lip inference can legitimately take a while on a
            # long video, especially CPU-only, but an unbounded call meant a
            # genuine hang here would block the render thread forever.
            log_path = os.path.join(work_dir, 'inference.log')
            with open(log_path, 'wb') as log:
                try:
                    process = run_process(cmd, cwd=self.wav2lip_dir, stdout=log,
                        stderr=subprocess.STDOUT, timeout=3600, check=True,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                except subprocess.CalledProcessError as exc:
                    log.flush()
                    with open(log_path, 'rb') as reader:
                        reader.seek(0, os.SEEK_END)
                        reader.seek(max(0, reader.tell() - 6000))
                        detail = reader.read().decode('utf-8', errors='replace')
                    raise RuntimeError('Wav2Lip worker failed: ' + detail) from exc
            
            # 4. CHECK RESULTS
            if os.path.exists(full_output_path) and os.path.getsize(full_output_path) > 1000:
                print("[LIPSYNC] Saving result...")
                from pipeline import _validate_media
                _validate_media(full_output_path, {"video"})
                check_cancelled()
                os.replace(full_output_path, output_path)
                return output_path
            else:
                print("\n" + "!"*40)
                print("[LIPSYNC] Engine failure")
                print("FULL LOGS (DEBUG):")
                print(process.stdout) # Now contains everything
                print("!"*40 + "\n")
                raise RuntimeError("Wav2Lip produced no valid video; " + (process.stdout or "")[-6000:])

        except RenderCancelled:
            raise
        except Exception as e:
            print(f"[LIPSYNC] Execution error: {str(e)}")
            raise RuntimeError(f"Wav2Lip execution failed: {e}") from e
