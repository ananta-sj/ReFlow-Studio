from core.render_context import check_cancelled, wait_or_cancel
import os
import requests
import time
import logging
from core.languages import M2M100_LANG_MAP, require_known_target, require_fixed_translation
from core.providers.base import require_translation_text
from core.source_language import M2M100_SOURCE_MAP, require_fixed_source, coerce_source_language, source_prompt


class LLMTranslator:
    def __init__(self, ollama_host="http://localhost:11434", ollama_model="llama3", warning_callback=None, fallback_runtime='legacy'):
        if fallback_runtime not in (None,'legacy','isolated'):raise ValueError('Unknown M2M100 fallback runtime')
        self.fallback_runtime=fallback_runtime or 'legacy'
        self._local_fallback=None
        from core.network_policy import require_network_allowed
        require_network_allowed(ollama_host)
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model
        self.warning_callback = warning_callback
        self.mode = "uninitialized"
        last_error = None
        for attempt in range(3):
            check_cancelled()
            try:
                response = requests.get(f"{self.ollama_host}/api/tags", timeout=(3, 3))
                check_cancelled()
                response.raise_for_status()
                payload = response.json()
                models = payload.get('models') if isinstance(payload, dict) else None
                if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get('name'), str) for m in models):
                    raise RuntimeError("Ollama returned an invalid model inventory.")
                names = [m['name'] for m in models]
                requested = ollama_model if ':' in ollama_model else ollama_model + ':latest'
                match = next((name for name in names if name == requested or name == ollama_model), None)
                if match is None:
                    raise RuntimeError(f"Requested Ollama model '{ollama_model}' is not installed. Install it or select an available model.")
                self.ollama_model = match
                self.mode = "ollama"
                return
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_error = exc
                if attempt < 2:
                    wait_or_cancel(1)
            except Exception as exc:
                check_cancelled()
                raise RuntimeError(f"Ollama discovery failed: {exc}") from exc
        # The target/instructions are only known at translate(). Defer model
        # loading so an incompatible fallback cannot download weights first.
        self.mode = "fallback_pending"
        self.fallback_reason = f"Ollama is unreachable: {last_error}"

    def _fallback(self, reason, target_language, custom_instructions="", source_language=None):
        try:
            require_fixed_translation("M2M100", M2M100_LANG_MAP, target_language, custom_instructions)
            require_fixed_source("M2M100", M2M100_SOURCE_MAP, source_language)
        except ValueError as exc:
            raise ValueError(f"{reason}; M2M100 fallback rejected: {exc}") from exc
        isolated=getattr(self,'fallback_runtime','legacy')=='isolated'
        message = (f"{reason}; switching translation to isolated CPU M2M100 using existing local weights."
                   if isolated else f"{reason}; switching translation to M2M100. Missing weights may download on first use.")
        logging.warning(message)
        if self.warning_callback:
            try:
                self.warning_callback(message)
            except Exception as exc:
                check_cancelled()
                logging.warning("Could not deliver translation fallback warning: %s", exc)
        try:
            if isolated:
                from core.providers.translation.m2m100_isolated import IsolatedM2M100Provider
                self._local_fallback=IsolatedM2M100Provider()
                self.mode='m2m100_isolated'
            else:
                self.init_m2m100()
        except Exception as exc:
            raise RuntimeError(f"{reason}; M2M100 fallback also failed: {exc}") from exc

    def init_m2m100(self):
        self.mode = "uninitialized"
        self.model_name = "facebook/m2m100_418M"
        self.device = "cpu"
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = os.path.join(self.root_dir, "models", "translation")
        try:
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
            from core.model_assets import ensure_assets, RECOVERY_SOURCES, ROOT
            ensure_assets('m2m100')
            model_path = str(ROOT / RECOVERY_SOURCES['m2m100']['folder'])
            self.tokenizer = M2M100Tokenizer.from_pretrained(model_path, local_files_only=True)
            self.model = M2M100ForConditionalGeneration.from_pretrained(model_path, local_files_only=True).to(self.device)
            self.model.eval()
        except Exception as exc:
            self.model = None
            self.tokenizer = None
            self.mode = "broken"
            raise RuntimeError(f"M2M100 initialization failed: {exc}") from exc
        self.mode = "m2m100"

    def translate(self, text, target_language="English", custom_instructions="", source_language=None):
        if not isinstance(text, str):
            raise ValueError("Translation input must be a string.")
        if not text.strip():
            return text
        require_known_target(target_language)
        source_language = coerce_source_language(source_language)
        if self.mode == "fallback_pending":
            self._fallback(self.fallback_reason, target_language, custom_instructions, source_language)
        if self.mode == "ollama":
            instruction = f"\nAdditional instructions: {custom_instructions.strip()}" if custom_instructions and custom_instructions.strip() else ""
            prompt = (f"Translate this text to {target_language}. Do not explain. Do not add notes. Just the translation."
                      f"{source_prompt(source_language)}{instruction}\n\nOriginal: {text}\nTranslation:")
            try:
                response = requests.post(f"{self.ollama_host}/api/generate", json={
                    "model": self.ollama_model, "prompt": prompt, "stream": False,
                    "options": {"temperature": 0.3},
                }, timeout=(5, 120))
                response.raise_for_status()
            except requests.exceptions.RequestException as exc:
                self._fallback(f"Ollama translation request failed: {exc}", target_language, custom_instructions, source_language)
            else:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise RuntimeError("Ollama translation returned invalid JSON.") from exc
                if not isinstance(payload, dict) or payload.get('error'):
                    raise RuntimeError("Ollama translation returned an invalid or error response.")
                output = require_translation_text(payload.get('response'))
                prefix = "Here is the translation:"
                if output.casefold().startswith(prefix.casefold()):
                    output = output[len(prefix):].lstrip()
                return require_translation_text(output)
        if self.mode == 'm2m100_isolated':
            return self._local_fallback.translate(text,target_language,custom_instructions=custom_instructions,
                                                  source_language=source_language)
        if self.mode == "m2m100":
            target_code = require_fixed_translation("M2M100", M2M100_LANG_MAP, target_language, custom_instructions)
            source_code = require_fixed_source("M2M100", M2M100_SOURCE_MAP, source_language)
            try:
                source_id = self.tokenizer.get_lang_id(source_code)
                if (not isinstance(source_id, int) or isinstance(source_id, bool) or source_id < 0
                        or source_id == getattr(self.tokenizer, "unk_token_id", None)):
                    raise ValueError(f"Loaded M2M100 tokenizer has no real source token for '{source_code}'.")
                target_id = self.tokenizer.get_lang_id(target_code)
                if (not isinstance(target_id, int) or isinstance(target_id, bool) or target_id < 0
                        or target_id == getattr(self.tokenizer, "unk_token_id", None)):
                    raise ValueError(f"Loaded M2M100 tokenizer has no real target token for '{target_code}'.")
                self.tokenizer.src_lang = source_code
                encoded = self.tokenizer(text, return_tensors="pt", truncation=False).to(self.device)
                from core.translation_completion import require_input_window, require_finished
                require_input_window(encoded, self.model, 'M2M100')
                from core.generation_control import generation_kwargs
                tokens = self.model.generate(**encoded, forced_bos_token_id=target_id,
                                             max_new_tokens=512, **generation_kwargs())
                require_finished(tokens, self.tokenizer, 'M2M100')
                output = self.tokenizer.batch_decode(tokens, skip_special_tokens=True)
                if not isinstance(output, list) or not output:
                    raise RuntimeError("M2M100 returned no decoded translation.")
                return require_translation_text(output[0])
            except Exception as exc:
                check_cancelled()
                raise RuntimeError(f"M2M100 translation failed: {exc}") from exc
        raise RuntimeError(f"Translation engine is not ready (state: {self.mode}).")

    def release(self):
        """Drop only this translator's local weights after its translation stage."""
        fallback=getattr(self,'_local_fallback',None)
        if fallback is not None:
            fallback.release()
            self._local_fallback=None
        self.model = None
        self.tokenizer = None
        self.mode = 'released'
