"""Local XTTS provider - thin wrapper around the existing TTSHandler."""

from core.providers.base import TTSProvider
from core.speech_language import require_xtts_language
import os
from pathlib import Path

def TTSHandler(*args,**kwargs):
    # Retain the existing test/adapter factory boundary while deferring heavy
    # legacy engine imports when an isolated worker has been explicitly chosen.
    from tts.tts_handler import TTSHandler as Handler
    return Handler(*args,**kwargs)


class XTTSLocalProvider(TTSProvider):
    def __init__(self, device=None, model_path=None, runtime=None):
        self.runtime = runtime or os.environ.get('REFLOW_XTTS_RUNTIME','legacy')
        if self.runtime not in {'legacy','isolated'}:
            raise ValueError('Choose legacy or isolated XTTS runtime')
        if self.runtime=='isolated' and device not in (None,'cpu'):
            raise ValueError('The isolated XTTS runtime is validated for CPU only')
        self.device = device
        if self.runtime == 'isolated':
            self.engine_id = 'xtts_isolated'
        self.model_path = model_path  # a Marketplace-connected local_file
        # entry's downloaded checkpoint dir, or None for the bundled default
        self._handler = None  # lazy + cached: synthesize() is called once
        # per subtitle segment in the real pipeline, and TTSHandler's
        # constructor loads the full XTTS model - that must happen once
        # per video, not once per segment.

    def synthesize(self, text, output_path, language="en", reference_audio=None):
        if language == "source":
            raise ValueError("XTTS requires an explicit speech language; 'source' is not supported yet.")
        language = require_xtts_language(language, self.model_path)
        if self.runtime=='isolated':
            return self._isolated(text,output_path,language,reference_audio)
        if self._handler is None:
            from bridge import push
            self._handler = TTSHandler(
                device=self.device, model_path=self.model_path, language=language,
                warning_callback=lambda message: push.emit("log", {"level": "warning", "message": message}),
            )
        return self._handler.generate_audio(text, output_path, language=language, reference_audio=reference_audio)

    def _isolated(self,text,output_path,language,reference_audio):
        from core.render_context import current_job,RenderContext,bind_job
        from core.python_runtime import project_root
        from core.xtts_runtime import validate,model_identity
        from core.feature_session import FeatureSession
        from core.pipeline import _staged_output
        from core.audio_utils import load_playable_audio,load_speech_audio
        if not isinstance(text,str) or not text.strip() or len(text)>4000:
            raise ValueError('XTTS needs 1–4000 characters of speech')
        if not reference_audio:raise ValueError('Isolated XTTS requires an explicit voice reference')
        load_playable_audio(reference_audio)
        job=current_job()
        if job is None:
            owned=RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):return self._isolated(text,output_path,language,reference_audio)
            finally:owned.cleanup()
        runtime=validate()
        model=Path(self.model_path or project_root()/'models/xtts/default').resolve()
        stat_key=tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino) for p in sorted(model.iterdir()) if p.suffix in {'.json','.pth'})
        with job.lock:
            identities=getattr(job,'_xtts_model_identities',None)
            if identities is None:identities=job._xtts_model_identities={}
            model_key=(str(model),stat_key)
            if model_key not in identities:identities[model_key]=model_identity(model)
            self.runtime_identity=runtime['identity']
            self.model_fingerprint=identities[model_key]
            self.worker_interpreter=runtime['executable']
            self.device='cpu'
            sessions=getattr(job,'_xtts_sessions',None)
            if sessions is None:sessions=job._xtts_sessions={}
            key=(self.runtime_identity,str(model),self.model_fingerprint)
            if key not in sessions:
                sessions[key]=FeatureSession(job,self.worker_interpreter,
                    dict(session_label='XTTS speech',model_path=str(model)),
                    worker=project_root()/'core/xtts_worker.py',operation='xtts_session')
            self.session=sessions[key]
        # The child writes only inside this job; the parent owns final publication.
        import uuid
        pending_worker=job.workspace/('xtts-'+uuid.uuid4().hex+'.wav')
        try:
            self.last_result=self.session.call(dict(text=text.strip(),output_path=str(pending_worker),
                language=language,reference_audio=str(Path(reference_audio).resolve())))
            load_speech_audio(str(pending_worker))
            with _staged_output(output_path) as pending:
                import shutil
                shutil.copyfile(pending_worker,pending)
                load_speech_audio(pending)
        finally:
            pending_worker.unlink(missing_ok=True)
        return output_path

    def release(self):
        from core.render_context import current_job
        job=current_job()
        if job is not None:
            for session in list(getattr(job,'_xtts_sessions',{}).values()):session.close()
            getattr(job,'_xtts_sessions',{}).clear()
