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
        if not interpreter('f5'):
            raise RuntimeError('Optional f5 runtime is unavailable or needs its reviewed security upgrade')
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
