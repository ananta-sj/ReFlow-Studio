import os
import sys
import logging
import inspect
import tempfile
from core.audio_utils import load_playable_audio, load_speech_audio
from core.render_context import RenderCancelled

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

logging.basicConfig(level=logging.INFO)

class RVCHandler:
    def __init__(self, device="cuda"):
        self.device = device
        self.ready = False
        print(f"[RVC] Initializing RVC Engine ({self.device})...")
        
        try:
            from rvc_python.infer import RVCInference
            from core.model_assets import ensure_assets
            ensure_assets("rvc")
            self.inference = RVCInference(device=self.device)
            self.ready = True
            print("[RVC] RVC System Online.")
        except RenderCancelled:
            raise
        except Exception as e:
            raise RuntimeError(f"RVC engine initialization failed: {e}") from e

    def preprocess_audio(self, input_path):
        """
        Converts audio to 16k mono to prevent Tensor Mismatch errors.
        Returns path to the temp file.
        """
        from core.render_context import current_job
        load_playable_audio(input_path)
        job = current_job()
        parent = str(job.workspace) if job else config.TEMP_PATH
        os.makedirs(parent, exist_ok=True)
        fd, temp_16k = tempfile.mkstemp(prefix='reflow-rvc-', suffix='_16k.wav', dir=parent)
        os.close(fd)
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-ar', '16000',  # Force 16k Sample Rate (Hubert Native)
            '-ac', '1',      # Force Mono
            temp_16k
        ]
        from pipeline import _run_ffmpeg
        try:
            _run_ffmpeg(cmd)
            load_playable_audio(temp_16k)
            return temp_16k
        except Exception:
            if os.path.exists(temp_16k):
                try:
                    os.remove(temp_16k)
                except OSError as exc:
                    logging.warning("Could not remove RVC preprocessing audio %s: %s", temp_16k, exc)
            raise

    def infer(self, input_audio, output_audio, model_name, pitch_change=0, model_path=None, index_path=None, version=None):
        if not self.ready:
            raise RuntimeError("RVC engine is not initialized.")

        weights_dir = os.path.join(config.MODELS_DIR, "rvc", "weights")
        model_path = model_path or os.path.join(weights_dir, f"{model_name}.pth")
        if not os.path.isfile(model_path):
            raise RuntimeError(f"Selected RVC checkpoint is missing: {model_path}")

        from core.model_contract import local_contract
        stat = os.stat(model_path)
        identity = (os.path.realpath(model_path), stat.st_size, stat.st_mtime_ns, stat.st_ino)
        cached = getattr(self, '_validated_checkpoint', None)
        if not cached or cached[0] != identity:
            self._validated_checkpoint = (identity, local_contract('voice', model_path))
        contract = self._validated_checkpoint[1]
        if version and version != contract['rvc_version']:
            raise RuntimeError('Configured RVC version does not match the checkpoint')
        version = contract['rvc_version']
        if index_path and not os.path.isfile(index_path):
            raise RuntimeError('Configured RVC index is missing: ' + index_path)
        index_identity = None
        if index_path:
            index_stat = os.stat(index_path)
            index_identity = (os.path.realpath(index_path), index_stat.st_size, index_stat.st_mtime_ns, index_stat.st_ino)
        selection = (identity, version, index_identity)

        print(f"[RVC] Morphing: {os.path.basename(input_audio)} -> {model_name}")

        # --- FIX: STANDARDIZE INPUT AUDIO ---
        clean_input = None
        try:
            clean_input = self.preprocess_audio(input_audio)
            # 2. Load Model
            if getattr(self, '_loaded_selection', None) == selection:
                pass
            elif hasattr(self.inference, "load_model"):
                parameters = inspect.signature(self.inference.load_model).parameters
                flexible = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())
                options = {}
                if 'version' in parameters or flexible:
                    options['version'] = version
                elif version != 'v2':
                    raise RuntimeError('Installed RVC loader cannot select a V1 model')
                if index_path:
                    if 'index_path' not in parameters and not flexible:
                        raise RuntimeError('Installed RVC loader cannot bind the selected index')
                    options['index_path'] = index_path
                self.inference.load_model(model_path, **options)
            elif hasattr(self.inference, "set_model"):
                if version != "v2" or index_path:
                    raise RuntimeError("Installed RVC set_model API cannot bind this version/index")
                self.inference.set_model(model_path)
            else:
                raise RuntimeError("Installed RVC engine has no supported model-loading method.")
            self._loaded_selection = selection

            # 3. RUN INFERENCE (Using clean 16k audio)
            # Based on your logs, 'infer_file' only wants input_path and output_path
            # The library likely handles pitch/f0 internally or via config now.
            
            # Select the supported API before calling it. An internal TypeError
            # is an inference failure, not a reason to retry the same operation.
            kwargs = {"input_path": clean_input}
            if "f0_up_key" in inspect.signature(self.inference.infer_file).parameters:
                kwargs["f0_up_key"] = pitch_change
            elif hasattr(self.inference, "set_params"):
                self.inference.set_params(f0up_key=pitch_change)
            elif pitch_change:
                raise RuntimeError("Installed RVC engine cannot apply the requested pitch change.")
            from pipeline import _staged_output
            with _staged_output(output_audio) as pending:
                self.inference.infer_file(output_path=pending, **kwargs)
                load_speech_audio(pending)
            return output_audio
        except RenderCancelled:
            raise
        except Exception as e:
            raise RuntimeError(f"Selected RVC voice '{model_name}' failed: {e}") from e
        finally:
            for path in (clean_input,):
                if path and path != input_audio and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as exc:
                        logging.warning("Could not remove RVC temporary audio %s: %s", path, exc)
