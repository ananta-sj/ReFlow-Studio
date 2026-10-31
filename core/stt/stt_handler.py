import os
import gc
from faster_whisper import WhisperModel
from core.transcription import TranscriptionResult, require_media_bounds

class STTHandler:
    def __init__(self, device="cpu", model_size="medium"):
        from core.recognition_compat import apply
        apply()
        # CPU is the only supported device: CUDA + OnnxRuntime is a known DLL
        # crash combo here, so a non-cpu request is honored as "acknowledged
        # but declined" rather than silently swapped out.
        if device != "cpu":
            print(f"[STT] ⚠️ device='{device}' requested, but only CPU is supported "
                  f"(avoids a known OnnxRuntime/CUDA DLL crash). Falling back to CPU.")
        self.device = "cpu"
        self.model_size = model_size
        self.compute_type = "int8"

        print(f"[STT] ⏳ Loading Whisper Model ({self.model_size}) on CPU [Safe Mode]...")
        try:
            # local_files_only=True when model_size is a real local
            # directory (a Marketplace-connected local_file STT model's
            # downloaded path - see core/providers/resolve.py) rather
            # than a named size ("medium", etc, which does need to hit
            # the network on first use) - avoids the same
            # from_pretrained()-style network freshness check other
            # local_file providers were found to hang on for 15+ minutes
            # on a slow connection (see core/providers/translation/
            # nllb_local.py's comment on the same issue).
            from pathlib import Path
            kwargs = {'local_files_only': os.path.isdir(self.model_size) or os.environ.get('REFLOW_OFFLINE') == '1',
                      'download_root': str(Path(__file__).resolve().parents[2] / 'models' / 'whisper' / 'cache')}
            self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type, **kwargs)
        except Exception as e:
            print(f"[STT] ❌ Critical Error loading Whisper: {e}")
            raise e

    def transcribe(self, audio_path, source_language='auto'):
        from core.recognition_language import whisper_language
        hint = whisper_language(source_language)
        if hint is not None and hint not in self.model.supported_languages:
            raise ValueError(f'This Whisper model does not support source language {source_language!r}.')
        # Beam size 5 gives better accuracy
        segments, info = self.model.transcribe(audio_path, beam_size=5, vad_filter=True,
                                               **({'language': hint} if hint else {}))
        
        result = []
        for segment in segments:
            result.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
        
        # Cleanup
        del self.model
        gc.collect()
        
        if getattr(info, 'duration', None) is not None:
            require_media_bounds(result, info.duration)
        return TranscriptionResult(result, hint or getattr(info, "language", None),
                                   getattr(info, "language_probability", None), 'hint' if hint else None)
