from core.render_context import current_job, check_cancelled, run_process, RenderCancelled
from core.audio_utils import load_playable_audio
from core.python_runtime import project_root, worker_python
import os
import sys
import subprocess
import uuid
from pathlib import Path

DEMUCS_SHA256 = '8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4'

class AudioSeparator:
    def __init__(self, device='cpu', runtime='legacy'):
        if runtime not in ('legacy', 'isolated'):
            raise ValueError('Unknown separation runtime')
        if runtime == 'isolated' and device != 'cpu':
            raise ValueError('The isolated separation runtime supports CPU only')
        self.runtime = runtime
        self.engine_id = 'demucs'
        if runtime == 'isolated':
            from core.separation_runtime import validate, model_contract
            route = validate()
            self.worker_interpreter = route['executable']
            self.runtime_identity = route['identity']
            self.model_path = model_contract()['model_path']
        self.device = device
        # [PATCH v0.5.3] DYNAMIC PATHING & MISSING TEMP_DIR FIX
        self.root_dir = str(project_root())
        
        self.models_dir = os.path.join(self.root_dir, "models", "uvr")
        self.temp_dir = str(current_job().workspace) if current_job() else os.path.join(self.root_dir, "temp")
        
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.work_dir = os.path.join(self.temp_dir, 'demucs-' + uuid.uuid4().hex)
        os.makedirs(self.work_dir)
        
        print(f"[INFO] AudioSeparator initialized at: {self.root_dir}")

    def separate(self, input_audio_path):
        print(f"[SEPARATOR] Splitting audio: {os.path.basename(input_audio_path)}")
        
        # [PATCH v0.5.3] MODULE EXECUTION FIX
        if self.runtime == 'isolated':
            from core.separation_runtime import validate, model_contract
            route = validate(); model_contract(verify_weights=True)
            python_exe = route['executable']
            self.worker_interpreter = python_exe
            self.runtime_identity = route['identity']
        else:
            python_exe = worker_python()
            self.worker_interpreter = python_exe
        
        # Use an explicit owned model repository. Demucs' remote default would
        # otherwise download into a machine-wide Torch cache, including offline.
        from core.downloader import download_with_progress
        import hashlib
        checkpoint = Path(self.models_dir) / '955717e8-8726e21a.th'
        if not checkpoint.is_file():
            for _ in download_with_progress(
                    'https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th',
                    str(checkpoint)):
                pass
        digest = hashlib.sha256()
        with checkpoint.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                check_cancelled()
                digest.update(chunk)
        if digest.hexdigest() != DEMUCS_SHA256:
            raise RuntimeError('Demucs checkpoint checksum mismatch; no separation will run')
        (Path(self.models_dir) / 'htdemucs.yaml').write_text("models: ['955717e8']\n", encoding='utf-8')
        cmd = [
            python_exe, os.path.join(self.root_dir, 'core', 'run_demucs.py'),
            "--two-stems=vocals", 
            "-n", "htdemucs",     
            "--repo", self.models_dir,
            "--device", self.device,
            "--out", self.work_dir,
            input_audio_path
        ]
        environment = os.environ
        if self.runtime == 'isolated':
            cmd.insert(2, '--reflow-isolated')
            environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'REFLOW_OFFLINE': '1',
                           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                           'PATH': str(Path(self.root_dir)/'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''),
                           'TEMP': self.work_dir, 'TMP': self.work_dir, 'TORCH_HOME': self.work_dir}
        
        try:
            # env=os.environ ensures it inherits system paths. Demucs can
            # legitimately take a while on a long file (especially CPU-only),
            # but an unbounded call previously meant a genuine hang here
            # would block the render thread forever with zero indication
            # anything was wrong - bridge/api.py's render loop already turns
            # any exception (including a timeout) into a visible render_error.
            log_path = Path(self.work_dir) / 'worker.log'
            try:
                with log_path.open('wb') as log:
                    run_process(cmd, check=True, env=environment, timeout=3600, stdout=log, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                with log_path.open('rb') as log:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 6000))
                    detail = log.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'Demucs worker failed: {detail}') from exc
            
            # File cleanup and moving logic
            filename = os.path.splitext(os.path.basename(input_audio_path))[0]
            output_folder = os.path.join(self.work_dir, "htdemucs", filename)
            
            generated_vocals = os.path.join(output_folder, "vocals.wav")
            generated_bg = os.path.join(output_folder, "no_vocals.wav")
            
            if os.path.isfile(generated_vocals) and os.path.isfile(generated_bg):
                load_playable_audio(generated_vocals)
                load_playable_audio(generated_bg)
                check_cancelled()
                print("[SEPARATOR] Split complete.")
                return generated_vocals, generated_bg
            else:
                print("[SEPARATOR] Extraction failed (files not found).")
                raise RuntimeError("Separation did not produce both required stems")

        except RenderCancelled:
            raise
        except Exception as e:
            print(f"[SEPARATOR] Error: {e}")
            raise RuntimeError(f"Audio separation failed: {e}") from e
