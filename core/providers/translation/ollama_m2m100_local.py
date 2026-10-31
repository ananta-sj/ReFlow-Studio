"""Local translation provider - thin wrapper around the existing
LLMTranslator, with visible fallback warnings and explicit failures."""

from core.providers.base import TranslationProvider
from core.languages import require_known_target
from core.source_language import coerce_source_language
from llm_translator import LLMTranslator


class OllamaM2M100LocalProvider(TranslationProvider):
    engine_id = 'ollama_m2m100'
    def __init__(self, ollama_host="http://localhost:11434", ollama_model="llama3", runtime='legacy'):
        if runtime not in (None,'legacy','isolated'):raise ValueError('Unknown M2M100 runtime selection')
        self.runtime=runtime or 'legacy'
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model
        self._translator = None  # lazy + cached: translate() is called once
        # per subtitle segment, and LLMTranslator's constructor does Ollama
        # detection (up to 3 retries) and/or loads the M2M100 model - that
        # must happen once per video, not once per segment.

    def translate(self, text, target_language, custom_instructions="", source_language=None):
        if not text.strip():
            return text
        require_known_target(target_language)
        source_language = coerce_source_language(source_language)
        if self._translator is None:
            self.worker_interpreter=None;self.runtime_identity=None;self.last_result=None
            from bridge import push
            self._translator = LLMTranslator(
                ollama_host=self.ollama_host, ollama_model=self.ollama_model,
                warning_callback=lambda message: push.emit("log", {"level": "warning", "message": message}),
                **({'fallback_runtime':'isolated'} if self.runtime=='isolated' else {}),
            )
        try:
            return self._translator.translate(text, target_language, custom_instructions=custom_instructions,
                                              source_language=source_language)
        finally:
            fallback=getattr(self._translator,'_local_fallback',None)
            if fallback is not None:
                for name in ('worker_interpreter','runtime_identity','last_result','model_path'):
                    setattr(self,name,getattr(fallback,name,None))

    def release(self):
        if self._translator is not None:
            self._translator.release()
            self._translator = None
