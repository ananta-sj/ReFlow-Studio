"""Selected stronger ASR; frees its GPU worker before translation."""
from pathlib import Path
from core.providers.base import STTProvider
from core.transcription import normalize_transcription, require_media_bounds, require_spoken_transcription
from core.whisper_turbo_assets import validate_assets, isolated_interpreter
from core.python_runtime import project_root
from core.render_context import current_job, RenderContext, bind_job


class WhisperTurboLocalProvider(STTProvider):
    engine_id = 'whisper_turbo'
    prefers_sentence_groups = True

    def __init__(self, model_path):
        self.contract = validate_assets(model_path)
        self.last_result = None
        self.worker_released = False

    def transcribe(self, audio_path, source_language='auto'):
        result, = self._transcribe_many([audio_path], source_language)
        return require_spoken_transcription(result)

    def transcribe_takes(self, audio_paths, source_language):
        return self._transcribe_many(audio_paths, source_language)

    def _transcribe_many(self, audio_paths, source_language):
        from core.source_language import normalize_source_selection
        selected = normalize_source_selection(source_language)
        paths = [Path(path).resolve() for path in audio_paths]
        if not paths or not all(path.is_file() for path in paths):
            raise ValueError('Recognition audio is missing.')
        job = current_job()
        if job is None:
            owned = RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):
                    return self._transcribe_many(paths, selected)
            finally:
                owned.cleanup()
        from core.feature_session import FeatureSession
        session = FeatureSession(job, isolated_interpreter(),
            {**self.contract,'session_label':'Whisper recognition'},
            worker=project_root()/'core/whisper_turbo_worker.py',operation='whisper_turbo_session')
        self.worker_interpreter = session.executable
        self.worker_released = False
        try:
            results = []
            for path in paths:
                call = dict(audio_path=str(path))
                if selected != 'auto':
                    call['source_language'] = selected
                self.last_result = session.call(call)
                result = normalize_transcription(self.last_result['transcription'])
                require_media_bounds(result, self.last_result['duration_seconds'])
                results.append(result)
            return results
        finally:
            session.close()
            self.worker_released = session.finished.is_set()
