"""Local F5-TTS voice provider - for a "voice" Marketplace entry backed
by F5-TTS (real zero-shot voice-cloning TTS, via the `f5-tts` PyPI
package's F5TTS class).

F5-TTS is architecturally a text-to-cloned-speech generator, not an
audio-to-audio timbre converter like RVC (VoiceProvider's other
implementations, core/providers/voice/rvc_local.py) - it needs the
target text and a reference clip of the voice to clone, not an
already-synthesized clip to reshape. It therefore ignores input_audio/
model_name/pitch_change entirely and requires text + reference_audio
(see base.py's VoiceProvider.convert() docstring) - core/pipeline.py's
_dub_segment() passes both through for exactly this reason.
"""

import os
from core.audio_utils import load_playable_audio, load_speech_audio

from core.providers.base import VoiceProvider


class F5TTSVoiceProvider(VoiceProvider):
    def __init__(self, device=None, model_path=None):
        self.device = device or "cpu"
        self.model_path = model_path
        self._f5tts = None
        # lazy + cached: convert() runs once per subtitle segment, but
        # loading F5-TTS's model/vocoder must happen once per video.

    def _ensure_loaded(self):
        if self._f5tts is not None:
            return
        from f5_tts.api import F5TTS

        if not self.model_path:
            raise ValueError("F5 requires an explicitly connected checkpoint")
        from core.model_contract import local_contract
        contract = local_contract('voice', self.model_path, 'f5tts')
        from core.model_assets import ensure_assets, ROOT
        ensure_assets('f5_asr')
        self._f5tts = F5TTS(device=self.device, ckpt_file=contract['checkpoint_path'],
                            vocab_file=contract['vocab_path'], model=contract['recipe'],
                            hf_cache_dir=str(ROOT / 'models/f5/cache'))
        self._references = {}

    def convert(self, input_audio, output_audio, model_name, pitch_change=0, text=None, reference_audio=None):
        if not text or not text.strip():
            raise ValueError(
                "F5TTSVoiceProvider.convert() requires `text` - F5-TTS re-synthesizes "
                "the line directly in the cloned voice, it doesn't reshape an existing "
                "clip's timbre like RVC. See VoiceProvider.convert()'s docstring."
            )
        if not reference_audio or not os.path.exists(reference_audio):
            raise ValueError(
                "F5TTSVoiceProvider.convert() requires a real `reference_audio` clip of "
                "the voice to clone - F5-TTS is zero-shot, it has no separate per-actor "
                "trained checkpoint the way RVC does."
            )
        load_playable_audio(reference_audio)
        from core.optional_runtime import interpreter, run_feature
        from pipeline import _staged_output
        if interpreter('f5'):
            from core.model_contract import local_contract
            contract = local_contract('voice', self.model_path, 'f5tts')
            with _staged_output(output_audio) as pending:
                params = {**contract, 'device': 'cpu',
                    'reference_audio': os.path.abspath(reference_audio), 'text': text,
                    'output_path': pending}
                from core.render_context import current_job
                if current_job():
                    from core.feature_session import run_cached_f5
                    run_cached_f5(contract, params)
                else:
                    run_feature('f5', 'f5_speech', params)
                load_speech_audio(pending)
            return output_audio
        self._ensure_loaded()

        # F5-TTS conditions on a transcript of the reference clip
        # (ref_text) as well as the clip itself - self._f5tts.transcribe()
        # runs Whisper over it automatically when ref_text is empty,
        # exactly like the upstream API's own basic usage example.
        with _staged_output(output_audio) as pending:
            from core.feature_worker import prepare_f5_reference
            reference, reference_text = prepare_f5_reference(
                {'reference_audio': reference_audio, 'device': self.device},
                getattr(self, '_references', None))
            self._f5tts.infer(ref_file=reference, ref_text=reference_text, gen_text=text, file_wave=pending)
            load_speech_audio(pending)
        return output_audio
