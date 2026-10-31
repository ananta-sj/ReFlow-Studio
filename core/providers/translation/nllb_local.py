"""Local NLLB-200 translation provider - for a "local_file" Translation
Marketplace entry, distinct from the Ollama/M2M100 default (which never
actually loads a Marketplace-connected local_file model - see
core/providers/resolve.py). Uses transformers' AutoModelForSeq2SeqLM/
AutoTokenizer directly, since NLLB-200 is a plain seq2seq model, not an
instructable LLM - no prompt mechanism, same limitation the offline
M2M100 fallback already documents on TranslationProvider.translate()'s
custom_instructions parameter.
"""

from core.providers.base import TranslationProvider, require_translation_text
from core.languages import NLLB_LANG_MAP, require_fixed_translation
from core.source_language import NLLB_SOURCE_MAP, require_fixed_source


class NLLBLocalProvider(TranslationProvider):
    engine_id = 'nllb'

    def __init__(self, model_path, device=None, runtime='legacy'):
        if runtime not in (None, 'legacy', 'isolated'):
            raise ValueError('Unknown NLLB runtime selection')
        if runtime == 'isolated' and device not in (None, 'cpu'):
            raise ValueError('The isolated NLLB runtime supports CPU only')
        self.runtime = runtime or 'legacy'
        self.model_path = model_path
        self.device = device or "cpu"
        self._model = None
        self._tokenizer = None
        self.session = None
        self.last_result = None
        # lazy + cached: translate() runs once per subtitle segment, but
        # loading the model/tokenizer from disk must happen once per video,
        # not once per segment - same reasoning as every other *_local
        # provider that's called in a per-segment loop.

    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        # local_files_only=True: self.model_path is always a real,
        # already-downloaded local directory (never a bare HF repo id),
        # but from_pretrained() still attempts a network freshness/etag
        # check by default even for a local path - observed hanging for
        # 15+ minutes on a slow connection before this fix, confirmed by
        # timing each step directly. No reason to depend on the network
        # at all for a model that's already fully on disk.
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_path, local_files_only=True)
        if self.device.startswith("cuda") and torch.cuda.is_available():
            self._model = self._model.to(self.device)
        else:
            self.device = "cpu"
        self._model.eval()

    def translate(self, text, target_language, custom_instructions="", source_language=None):
        if not isinstance(text, str):
            raise ValueError('NLLB translation input must be text')
        if not text or not text.strip():
            return text
        target_code = require_fixed_translation("NLLB-200", NLLB_LANG_MAP, target_language, custom_instructions)
        source_code = require_fixed_source("NLLB-200", NLLB_SOURCE_MAP, source_language)
        if self.runtime == 'isolated':
            return self._isolated_call(text, target_language, source_code)
        self._ensure_loaded()
        source_token = self._tokenizer.convert_tokens_to_ids(source_code)
        if source_token is None or source_token == self._tokenizer.unk_token_id:
            raise ValueError(f"Loaded NLLB tokenizer has no real source token for '{source_code}'.")
        self._tokenizer.src_lang = source_code
        # Validated against the actually-loaded tokenizer, not just trusted
        # from the hardcoded table - a different NLLB checkpoint/tokenizer
        # revision could in principle rename/drop a special token.
        try:
            forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(target_code)
        except Exception as e:
            raise ValueError(
                f"Loaded NLLB tokenizer at {self.model_path} doesn't recognize "
                f"language code '{target_code}': {e}"
            )
        if forced_bos_token_id is None or forced_bos_token_id == self._tokenizer.unk_token_id:
            raise ValueError(
                f"Loaded NLLB tokenizer at {self.model_path} doesn't have a real "
                f"token for language code '{target_code}' (got unk/None)."
            )

        import torch

        inputs = self._tokenizer(text, return_tensors="pt", truncation=False).to(self.device)
        from core.translation_completion import require_input_window, require_finished
        require_input_window(inputs, self._model, 'NLLB-200')
        from core.generation_control import generation_kwargs
        with torch.no_grad():
            generated = self._model.generate(
                **inputs, forced_bos_token_id=forced_bos_token_id, max_new_tokens=512,
                num_beams=5, do_sample=False,
                **generation_kwargs(),
            )
        require_finished(generated, self._tokenizer, 'NLLB-200')
        return require_translation_text(self._tokenizer.batch_decode(generated, skip_special_tokens=True)[0])

    def _isolated_call(self, text, target, source):
        from core.render_context import current_job, RenderContext, bind_job
        from core.python_runtime import project_root
        job = current_job()
        if job is None:
            owned = RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):
                    return self._isolated_call(text, target, source)
            finally:
                self.release()
                owned.cleanup()
        if self.session is not None and self.session.job is not job:
            raise RuntimeError('NLLB session belongs to a different render job')
        if self.session is None:
            from core.nllb_runtime import validate
            from core.feature_session import FeatureSession
            route = validate()
            self.worker_interpreter = route['executable']
            self.runtime_identity = route['identity']
            self.session = FeatureSession(job, self.worker_interpreter,
                dict(model_path=str(self.model_path), session_label='NLLB translation'),
                worker=project_root()/'core/nllb_worker.py', operation='nllb_session')
        self.last_result = self.session.call(dict(text=text, target=target, source=source))
        return require_translation_text(self.last_result.get('translation'))

    def release(self):
        if self.session is not None:
            self.session.close()
            self.session = None
        self._model = None
        self._tokenizer = None
