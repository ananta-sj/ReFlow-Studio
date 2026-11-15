"""Stage-owned GPU workers exposed through the existing provider interfaces."""
from pathlib import Path
import logging
import shutil
import uuid

from core.providers.base import STTProvider, require_translation_text
from core.providers.tts.xtts_local import XTTSLocalProvider
from core.providers.translation.nllb_local import NLLBLocalProvider
from core.python_runtime import project_root
from core.render_context import current_job, RenderContext, bind_job
from core.audio_utils import load_playable_audio, load_speech_audio
from core.transcription import normalize_transcription


class CudaCalls:
    def __init__(self, stage, model_path):
        self.stage, self.model_path = stage, str(model_path)
        self.session = None
        self.last_result = None
        self.device, self.runtime = 'cuda:0', 'cuda'
        self.reported = False

    def call(self, request):
        job = current_job()
        if job is None:
            owned = RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):
                    return self.call(request)
            finally:
                self.release()
                owned.cleanup()
        if self.session is not None and self.session.job is not job:
            raise RuntimeError('GPU worker belongs to a different job')
        if self.session is None:
            from core.cuda_runtime import validate
            from core.feature_session import FeatureSession
            route = validate(self.stage)
            self.runtime_identity, self.worker_interpreter = route['identity'], route['executable']
            self.session = FeatureSession(job, route['executable'],
                dict(stage=self.stage, model_path=self.model_path, session_label='CUDA '+self.stage),
                worker=project_root()/'core/cuda_worker.py', operation='cuda_session')
        self.last_result = self.session.call(request)
        if self.last_result.get('device') != 'cuda:0':
            raise RuntimeError('GPU worker did not confirm CUDA execution')
        if not self.reported:
            logging.info('[GPU] %s running on cuda:0 (%s)', self.stage,
                         self.last_result.get('gpu_name', 'NVIDIA'))
            self.reported = True
        return self.last_result

    def release(self):
        if self.session is not None:
            self.session.close()
            self.session = None
            self.reported = False


class CudaXTTSProvider(XTTSLocalProvider):
    engine_id = 'xtts_cuda'

    def __init__(self, model_path=None):
        self.device, self.runtime = 'cuda:0', 'cuda'
        self.model_path = str(model_path or project_root()/'models/xtts/default')
        self.calls = CudaCalls('speech', self.model_path)

    def synthesize_bounded(self,text,output_path,language,reference_audio,*,max_seconds,alternate_take=False):
        return self._synthesize(text,output_path,language,reference_audio,retry=alternate_take,max_seconds=max_seconds)

    def _synthesize(self, text, output_path, language, reference_audio, *, retry=False, max_seconds=None):
        from core.speech_language import require_xtts_language
        from core.pipeline import _staged_output
        if not isinstance(text, str):
            raise ValueError('Speech input must be text')
        if not text.strip():
            return None
        language = require_xtts_language(language, self.model_path)
        load_playable_audio(reference_audio)
        job = current_job()
        if job is None:
            owned = RenderContext(project_root()/'temp')
            try:
                with bind_job(owned):
                    return self._synthesize(text, output_path, language, reference_audio, retry=retry,max_seconds=max_seconds)
            finally:
                self.release()
                owned.cleanup()
        output = job.workspace/('cuda-speech-'+uuid.uuid4().hex+'.wav')
        try:
            result = self.calls.call(dict(text=text, language=language, reference_audio=str(Path(reference_audio).resolve()),
                                 output_path=str(output), alternate_take=retry,max_seconds=max_seconds))
            if result.get('speech_limit'):
                from core.speech_generation_budget import SpeechGenerationLimitExceeded
                raise SpeechGenerationLimitExceeded(result['speech_limit'])
            load_speech_audio(output)
            with _staged_output(output_path) as pending:
                shutil.copyfile(output, pending)
        finally:
            output.unlink(missing_ok=True)
        return output_path

    def release(self):
        self.calls.release()


class CudaNLLBProvider(NLLBLocalProvider):
    def __init__(self, model_path):
        super().__init__(model_path, device='cuda:0')
        self.runtime = 'cuda'
        self.calls = CudaCalls('translation', model_path)

    def translate(self, text, target_language, custom_instructions='', source_language=None):
        from core.languages import NLLB_LANG_MAP, require_fixed_translation
        from core.source_language import NLLB_SOURCE_MAP, require_fixed_source
        require_fixed_translation('NLLB-200', NLLB_LANG_MAP, target_language, custom_instructions)
        source = require_fixed_source('NLLB-200', NLLB_SOURCE_MAP, source_language)
        if not isinstance(text, str):
            raise ValueError('Translation input must be text')
        if not text.strip():
            return text
        return require_translation_text(self.calls.call(
            dict(text=text, target=target_language, source=source))['translation'])

    def release(self):
        self.calls.release()


class CudaWhisperProvider(STTProvider):
    engine_id, device, runtime = 'whisper_cuda', 'cuda:0', 'cuda'

    def __init__(self, model_size):
        self.model_size = model_size
        self.calls = CudaCalls('recognition', model_size)

    def transcribe(self, audio_path, source_language='auto'):
        return self._run([audio_path], source_language, takes=False)[0]

    def transcribe_takes(self, audio_paths, source_language):
        return self._run(audio_paths, source_language, takes=True)

    def _run(self, audio_paths, source_language, *, takes):
        try:
            result = self.calls.call(dict(audio_paths=[str(Path(path).resolve()) for path in audio_paths],
                                         source_language=source_language, takes=takes))
            return [normalize_transcription(item) for item in result['transcriptions']]
        finally:
            self.calls.release()


class CudaSeparator:
    engine_id, device, runtime = 'demucs', 'cuda:0', 'cuda'

    def __init__(self, device='cuda:0'):
        if device != 'cuda:0':
            raise ValueError('The CUDA separator requires the first NVIDIA GPU')
        from core.cuda_runtime import validate
        self.runtime_identity = validate('separate')['identity']
        self.models_dir = str(project_root()/'models/uvr')
        self.calls = CudaCalls('separate', self.models_dir)

    def separate(self, audio_path):
        job = current_job()
        if job is None:
            raise RuntimeError('GPU separation needs an owned render job')
        output = job.workspace/('cuda-separation-'+uuid.uuid4().hex)
        try:
            result = self.calls.call(dict(audio_path=str(Path(audio_path).resolve()), output_path=str(output)))
            vocals, background = result['vocals'], result['background']
            load_playable_audio(vocals)
            load_playable_audio(background)
            return vocals, background
        finally:
            self.calls.release()
