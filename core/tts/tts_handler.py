import os
import sys
import torch
import warnings
import logging
from core.audio_utils import load_playable_audio, load_speech_audio
from core.speech_language import require_xtts_language

# --- PYTORCH 2.6+ SECURITY PATCH ---
try:
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
    from TTS.config.shared_configs import BaseDatasetConfig
    torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig, XttsArgs])
except ImportError:
    pass
except Exception as e:
    print(f"[PATCH] ⚠️ Security Patch Warning: {e}")
# -----------------------------------

warnings.filterwarnings("ignore")
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

class TTSHandler:
    def __init__(self, device=None, model_path=None, warning_callback=None, language=None):
        if language is not None:
            require_xtts_language(language, model_path)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_gpu = self.device.startswith("cuda")
        self.tts = None
        self.model_path = model_path or os.path.join(config.MODELS_DIR, "xtts", "default")
        self.config_path = os.path.join(self.model_path, "config.json")
        if model_path is None:
            from core.model_assets import ensure_assets
            ensure_assets("xtts")
        if language is not None:
            require_xtts_language(language, self.model_path)
        if not os.path.isdir(self.model_path) or not os.path.isfile(self.config_path):
            raise RuntimeError(f"XTTS model/config files not found at {self.model_path}")
        try:
            from TTS.api import TTS
        except Exception as exc:
            raise RuntimeError(f"XTTS engine could not be imported: {exc}") from exc
        try:
            self.tts = TTS(model_path=self.model_path, config_path=self.config_path,
                           progress_bar=True, gpu=self.use_gpu)
            if self.use_gpu:
                self.tts.to(self.device)
        except Exception as gpu_error:
            self.tts = None
            if not self.use_gpu:
                raise RuntimeError(f"XTTS model loading failed: {gpu_error}") from gpu_error
            try:
                self.tts = TTS(model_path=self.model_path, config_path=self.config_path,
                               progress_bar=True, gpu=False)
            except Exception as cpu_error:
                self.tts = None
                raise RuntimeError(f"XTTS GPU loading failed: {gpu_error}; CPU recovery also failed: {cpu_error}") from cpu_error
            self.device, self.use_gpu = "cpu", False
            message = f"XTTS GPU loading failed ({gpu_error}); continuing on CPU."
            logging.warning(message)
            if warning_callback:
                try:
                    warning_callback(message)
                except Exception as exc:
                    logging.warning("Could not deliver XTTS recovery warning: %s", exc)
        # Coqui's checkpoint-loading branch uses the 22050 Hz conditioning
        # rate when saving XTTS's 24000 Hz decoder samples. Use the loaded
        # decoder's rate, including custom checkpoints and CPU recovery.
        synthesizer = self.tts.synthesizer
        output_rate = synthesizer.tts_model.hifigan_decoder.output_sample_rate
        if type(output_rate) is not int or not 8000 <= output_rate <= 192000:
            raise RuntimeError(f"XTTS decoder has an invalid output sample rate: {output_rate!r}")
        synthesizer.output_sample_rate = output_rate

    def generate_audio(self, text, output_path, language="en", reference_audio=None):
        if not getattr(self, 'tts', None):
            raise RuntimeError("XTTS model is not initialized.")
        if not text or not text.strip():
            return None
        if language == "source":
            raise ValueError("XTTS requires an explicit speech language; 'source' is not supported yet.")
        language = require_xtts_language(language, getattr(self, "model_path", None))
        # An explicit reference is authoritative; don't silently substitute it.
        if reference_audio is not None:
            speaker_wav = reference_audio
        else:
            candidates = [os.path.join(config.BASE_DIR, "assets", "reference.wav"),
                          os.path.join(config.TEMP_PATH, "original_audio.wav"),
                          os.path.join(self.model_path, "samples", "en_sample.wav")]
            speaker_wav = next((path for path in candidates if os.path.isfile(path)), None)
        if speaker_wav is None:
            raise RuntimeError("XTTS requires a playable voice reference. Select a reference clip or provide source audio.")
        load_playable_audio(speaker_wav)
        try:
            from pipeline import _staged_output
            from core.generation_control import generation_kwargs
            with _staged_output(output_path) as pending:
                # Random sampling produced foreign-language openings and
                # stutters in Hindi controls. Greedy Hindi takes passed the
                # corresponding varied-text listening checks on both voices.
                decoding = {'do_sample': False, 'num_beams': 1} if language == 'hi' else {}
                from core.xtts_text import should_split_sentences
                split = should_split_sentences(text, language, self.tts.synthesizer.tts_model)
                self.tts.tts_to_file(text=text, file_path=pending, speaker_wav=speaker_wav,
                                     language=language, split_sentences=split, temperature=0.75, speed=1.0,
                                     **decoding, **generation_kwargs())
                load_speech_audio(pending)
        except Exception as exc:
            from core.render_context import RenderCancelled
            if isinstance(exc, RenderCancelled):
                raise
            raise RuntimeError(f"XTTS speech generation failed: {exc}") from exc
        return output_path


if __name__ == "__main__":
    handler = TTSHandler()
