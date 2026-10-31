"""Base classes for pluggable stage providers - one ABC per stage type,
since each stage's real inputs/outputs genuinely differ (a single generic
run() would just be a dict-in/dict-out escape hatch, less useful than a
typed method per stage). Every provider - local wrapper, cloud REST
adapter, or local-API adapter - implements exactly one of these, and
core/pipeline.py calls through whichever is active for each stage
(core/model_registry.py) instead of instantiating a handler directly.
"""

from abc import ABC, abstractmethod
from core.transcription import TranscriptionResult


def require_translation_text(value):
    """Nonblank input requires actual translated text, not arbitrary JSON."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Translation response must contain a nonempty string.")
    return value.strip()


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, source_language='auto') -> TranscriptionResult:
        """Returns list-compatible segments plus optional language/probability.

        Explicit source_language guides recognition; unsupported hints must
        fail clearly. Forced language labels use language_origin='hint' and
        have no detection confidence. Missing source metadata is None. Legacy providers returning plain
        lists remain accepted through normalize_transcription(). Use the
        result's to_payload() when serializing metadata across JSON boundaries.
        """


class TranslationProvider(ABC):
    @abstractmethod
    def translate(self, text: str, target_language: str, custom_instructions: str = "", source_language=None) -> str:
        """Returns the translated text. custom_instructions is free text the
        user set on the active model in the Marketplace (e.g. "avoid
        profanity, keep it formal"). Prompt-based providers send these to
        the model; compliance depends on that model. Fixed-vocabulary
        providers reject nonblank instructions, including during fallback.
        Custom REST templates must explicitly transmit the instructions.
        source_language is a SourceLanguage context, manual code/name, or
        None/auto. Fixed-vocabulary engines require a resolved exact source;
        prompt-based engines may infer it when unresolved."""


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: str, language: str = "en", reference_audio=None) -> str:
        """Writes synthesized audio to output_path, returns the path actually written."""


class VoiceProvider(ABC):
    @abstractmethod
    def convert(
        self, input_audio: str, output_audio: str, model_name: str, pitch_change: int = 0,
        text: str = None, reference_audio: str = None,
    ) -> str:
        """Voice-converts input_audio, returns the output path actually written.

        text/reference_audio are optional and exist for zero-shot cloning
        engines (e.g. F5-TTS) that are architecturally a text-to-cloned-
        speech generator, not an audio-to-audio timbre converter like RVC -
        such a provider ignores input_audio entirely and instead
        re-synthesizes text directly in reference_audio's voice. RVC-style
        providers ignore both and keep converting input_audio as before -
        this is additive, not a behavior change for them."""


class EnhancerProvider(ABC):
    @abstractmethod
    def enhance(self, video_path: str, output_path: str) -> str:
        """Face-enhances every frame, returns the output path (or the
        original video_path if enhancement wasn't possible)."""


class FilterProvider(ABC):
    @abstractmethod
    def scan_and_blur(self, video_path: str, output_path: str) -> str:
        """Content-filters every frame, returns the output path (or the
        original video_path if filtering wasn't possible/needed)."""


class LipSyncProvider(ABC):
    @abstractmethod
    def execute(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Syncs video_path's mouth movement to audio_path, returns the
        output path actually written."""


class ProfanityFilterProvider(ABC):
    @abstractmethod
    def filter_text(self, text: str, custom_instructions: str = "") -> str:
        """Rewrites/censors text, returns the filtered text. Runs on
        already-translated dialogue, after the translation stage - see
        core/pipeline.py. Like TranslationProvider.custom_instructions, this
        is free text from the active model's Marketplace entry (e.g. "also
        flag slurs in Hindi", "replace with ***" ) appended to whatever
        default moderation instruction the implementation uses."""


def release_speech(provider):
    """Release stage-owned workers before another model family starts."""
    if getattr(provider, 'engine_id', None) in ('indicf5', 'xtts_isolated'):
        provider.release()
