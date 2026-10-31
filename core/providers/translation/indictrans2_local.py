"""Selected, isolated English-to-Hindi IndicTrans2 with explicit stage release."""
from pathlib import Path
from core.providers.base import TranslationProvider, require_translation_text
from core.source_language import require_fixed_source
from core.languages import require_fixed_translation
from core.indictrans2_assets import validate_assets, isolated_interpreter


class IndicTrans2LocalProvider(TranslationProvider):
    engine_id = 'indictrans2'

    def __init__(self, model_path):
        self.contract = validate_assets(model_path)
        self.session = None
        self.last_result = None

    def translate(self, text, target_language, custom_instructions='', source_language=None):
        if not isinstance(text, str):
            raise ValueError('IndicTrans2 translation input must be text.')
        if not text.strip():
            return text
        target = require_fixed_translation('IndicTrans2', {'Hindi':'hin_Deva'}, target_language, custom_instructions)
        source = require_fixed_source('IndicTrans2', {'en':'eng_Latn'}, source_language)
        return require_translation_text(self._call({'text':text.strip(), 'source':source, 'target':target}).get('translation'))

    def suggest_dialogue(self, text, target_language, source_language=None, max_candidates=3):
        if type(max_candidates) is not int or not 1 <= max_candidates <= 3:
            raise ValueError('Request one to three dialogue alternatives.')
        text = require_translation_text(text)
        target = require_fixed_translation('IndicTrans2', {'Hindi':'hin_Deva'}, target_language, '')
        source = require_fixed_source('IndicTrans2', {'en':'eng_Latn'}, source_language)
        result = self._call(dict(text=text.strip(), source=source, target=target,
                                mode='dialogue_options', max_candidates=max_candidates), timeout=180)
        candidates = result.get('candidates')
        if not isinstance(candidates, list) or len(candidates)>max_candidates:
            raise RuntimeError('IndicTrans2 returned invalid dialogue alternatives.')
        return [require_translation_text(item) for item in candidates]

    def _call(self, params, timeout=None):
        from core.render_context import current_job, RenderContext, bind_job
        job = current_job()
        if job is None:
            from core.python_runtime import project_root
            owned = RenderContext(project_root() / 'temp')
            try:
                with bind_job(owned):
                    return self._call(params, timeout)
            finally:
                self.release()
                owned.cleanup()
        if self.session is not None and self.session.job is not job:
            raise RuntimeError('IndicTrans2 session belongs to a different render job.')
        if self.session is None:
            from core.feature_session import FeatureSession
            from core.python_runtime import project_root
            self.session = FeatureSession(job, isolated_interpreter(),
                {**self.contract, 'session_label':'IndicTrans2 translation'},
                worker=project_root() / 'core/indictrans2_worker.py', operation='indictrans2_session')
        self.last_result = self.session.call(params) if timeout is None else self.session.call(params, timeout=timeout)
        return self.last_result

    def release(self):
        if self.session is not None:
            self.session.close()
            self.session = None
