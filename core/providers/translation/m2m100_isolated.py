"""Stage-owned fixed-model M2M100 provider; never discovers services."""
from core.providers.base import TranslationProvider,require_translation_text
from core.languages import M2M100_LANG_MAP,require_fixed_translation
from core.source_language import M2M100_SOURCE_MAP,require_fixed_source


class IsolatedM2M100Provider(TranslationProvider):
    engine_id='m2m100_isolated'
    runtime='isolated'
    device='cpu'

    def __init__(self):
        self.session=None
        self.last_result=None

    def translate(self,text,target_language,custom_instructions='',source_language=None):
        if not isinstance(text,str):raise ValueError('M2M100 input must be text')
        if not text.strip():return text
        require_fixed_translation('M2M100',M2M100_LANG_MAP,target_language,custom_instructions)
        require_fixed_source('M2M100',M2M100_SOURCE_MAP,source_language)
        from core.source_language import coerce_source_language
        return self._call(dict(text=text,target=target_language,source=coerce_source_language(source_language).code))

    def _call(self,params):
        from core.render_context import current_job,RenderContext,bind_job
        from core.python_runtime import project_root
        job=current_job()
        if job is None:
            owned=RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):return self._call(params)
            finally:
                self.release();owned.cleanup()
        if self.session is not None and self.session.job is not job:
            raise RuntimeError('M2M100 session belongs to another job')
        if self.session is None:
            from core.m2m100_runtime import validate,model_contract
            from core.feature_session import FeatureSession
            route=validate();contract=model_contract()
            self.worker_interpreter=route['executable'];self.runtime_identity=route['identity']
            self.model_path=contract['model_path']
            self.session=FeatureSession(job,self.worker_interpreter,
                {**contract,'session_label':'M2M100 translation'},
                worker=project_root()/'core/m2m100_worker.py',operation='m2m100_session')
        self.last_result=self.session.call(params)
        return require_translation_text(self.last_result.get('translation'))

    def release(self):
        if self.session is not None:
            self.session.close();self.session=None
