"""Isolated IndicF5 speech with explicit, hash-bound reviewed reference pairs."""
import hashlib
import json
import math
import re
from pathlib import Path

from core.providers.base import TTSProvider
from core.python_runtime import project_root
from core.indicf5_duration import sentence_hops, validate_minimum_sentence_seconds,segment_text


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_supported_text(text, vocab_path, reference_text=''):
    """Reject unsupported glyphs before launching or invoking speech inference."""
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('IndicF5 needs 1–4000 characters of nonblank speech text.')
    # Match the pinned F5 custom tokenizer: universal-newline text iteration,
    # removing the trailing newline from each vocabulary entry.
    with Path(vocab_path).open('r', encoding='utf-8') as stream:
        allowed = {line[:-1] for line in stream}
    for role, value in (('speech', text.strip()), ('reference', reference_text)):
        unsupported = sorted(set(value)-allowed)
        if unsupported:
            points = ', '.join(f'U+{ord(char):04X} ({char!r})' for char in unsupported[:12])
            raise ValueError(f'IndicF5 {role} text contains unsupported characters: {points}. '
                             'Edit the punctuation or wording; no characters were removed automatically.')


def estimate_native_duration_seconds(text, profile, minimum_sentence_seconds=None, *, continuous_utterance=False):
    """Predict fixed native waveform duration, not inference time or quality."""
    import soundfile as sf
    sentences = segment_text(text,continuous_utterance)
    reference = sf.info(profile['reference_audio'])
    rate = 24000
    if reference.samplerate != rate or reference.channels != 1 or reference.frames <= 0:
        raise ValueError('Confirmed IndicF5 reference must be nonempty mono 24 kHz audio.')
    validate_minimum_sentence_seconds(minimum_sentence_seconds)
    frames = 0
    for sentence in sentences:
        hops = sentence_hops(sentence,profile,rate,minimum_sentence_seconds)
        if reference.frames // 256 + hops + 1 > 4096:
            raise ValueError('IndicF5 sentence exceeds its model limit; split or shorten the sentence.')
        frames += hops * 256
    frames += (len(sentences)-1) * round(profile['sentence_gap_seconds'] * rate)
    return frames / rate


def load_reference_profile(path):
    if not path:
        raise ValueError('IndicF5 requires a reviewed reference audio/transcript profile.')
    path = Path(path).resolve()
    profile = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(profile, dict) or profile.get('schema') != 'reflow.indicf5.reference.v1':
        raise ValueError('Invalid IndicF5 reference profile')
    if profile.get('language') != 'hi' or profile.get('human_reference_confirmed') is not True:
        raise ValueError('IndicF5 requires a confirmed Hindi reference pair.')
    for field in ('reference_sha256', 'original_source_sha256'):
        value = profile.get(field)
        if (field == 'reference_sha256' or value is not None) and (not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)):
            raise ValueError('Invalid IndicF5 reference identity: '+field)
    audio = Path(profile['reference_audio'])
    audio = audio.resolve() if audio.is_absolute() else (path.parent / audio).resolve()
    if digest(audio) != profile['reference_sha256']:
        raise ValueError('IndicF5 reference audio changed; confirm its matching transcript again.')
    text = profile.get('reference_text')
    calibration = profile.get('calibration_text')
    if not isinstance(text, str) or not text.strip() or not isinstance(calibration, str) or not calibration.strip():
        raise ValueError('IndicF5 reference and pace-calibration text are required.')
    for field, minimum, maximum in [('calibration_seconds', .1, 60), ('guidance', 0, 5), ('sentence_gap_seconds', 0, 1)]:
        value = profile.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError('Invalid IndicF5 profile field: '+field)
    if type(profile.get('steps')) is not int or not 16 <= profile['steps'] <= 64:
        raise ValueError('IndicF5 steps must be an integer from 16 to 64.')
    if type(profile.get('seed')) is not int or not 0 <= profile['seed'] < 2**32:
        raise ValueError('Invalid IndicF5 seed.')
    return {**profile, 'reference_audio': str(audio), 'profile_path': str(path)}


def isolated_interpreter(device):
    if device not in ('cpu', 'cuda', 'cuda:0'):
        raise ValueError('IndicF5 currently supports CPU or the first NVIDIA GPU.')
    root = project_root()
    gpu = str(device).startswith('cuda')
    folder = root / 'runtime_profiles' / ('indicf5-gpu-evaluation' if gpu else 'indicf5-evaluation')
    executable = folder / 'python.exe'
    metadata = json.loads((folder / 'profile.json').read_text(encoding='utf-8'))
    if not executable.is_file() or (gpu and metadata.get('status') != 'gpu-environment-verified'):
        raise RuntimeError('The isolated IndicF5 runtime is unavailable or unverified.')
    return str(executable)


class IndicF5TTSProvider(TTSProvider):
    engine_id = 'indicf5'
    preserves_native_delivery = True
    requires_exact_reference = True

    def __init__(self, model_path, reference_profile, device='cpu'):
        from core.model_contract import local_contract
        self.contract = local_contract('tts', model_path, 'indicf5')
        if self.contract['adapter'] != 'indicf5':
            raise ValueError('IndicF5 requires its own checkpoint contract.')
        self.profile_path = reference_profile
        self.profile = load_reference_profile(reference_profile)
        self.device = device or 'cpu'
        if self.device not in ('cpu', 'cuda', 'cuda:0'):
            raise ValueError('Invalid IndicF5 speech device.')
        self.last_result = None

    def estimate_duration_seconds(self, text, minimum_sentence_seconds=None, *, continuous_utterance=False):
        profile = load_reference_profile(self.profile_path)
        require_supported_text(text, self.contract['vocab_path'], profile['reference_text'])
        self.profile = profile
        return estimate_native_duration_seconds(text, profile,minimum_sentence_seconds,continuous_utterance=continuous_utterance)

    def synthesize(self, text, output_path, language='hi', reference_audio=None, *, minimum_sentence_seconds=None,continuous_utterance=False):
        validate_minimum_sentence_seconds(minimum_sentence_seconds)
        segment_text(text,continuous_utterance)
        if language != 'hi':
            raise ValueError('This IndicF5 route is validated for Hindi only.')
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError('IndicF5 needs 1–4000 characters of nonblank speech text.')
        profile = load_reference_profile(self.profile_path)
        if not reference_audio:
            raise ValueError('Select the original or confirmed reference audio for IndicF5.')
        supplied = digest(reference_audio)
        if supplied not in {profile['reference_sha256'], profile.get('original_source_sha256')}:
            raise ValueError('Selected voice audio does not match this confirmed IndicF5 profile.')
        require_supported_text(text, self.contract['vocab_path'], profile['reference_text'])
        self.profile = profile
        from core.render_context import current_job, RenderContext, bind_job
        job = current_job()
        if job is None:
            owned = RenderContext(project_root() / 'temp')
            try:
                with bind_job(owned):
                    return self.synthesize(text, output_path, language, reference_audio,minimum_sentence_seconds=minimum_sentence_seconds,continuous_utterance=continuous_utterance)
            finally:
                owned.cleanup()
        from core.feature_session import FeatureSession
        executable = isolated_interpreter(self.device)
        self.worker_interpreter = executable
        checkpoint = Path(self.contract['checkpoint_path'])
        vocab = Path(self.contract['vocab_path'])
        checkpoint_stat, vocab_stat = checkpoint.stat(), vocab.stat()
        key = (executable, self.device, str(checkpoint.resolve()), checkpoint_stat.st_size,
               checkpoint_stat.st_mtime_ns, checkpoint_stat.st_ino, str(vocab.resolve()),
               vocab_stat.st_size, vocab_stat.st_mtime_ns, vocab_stat.st_ino)
        with job.lock:
            sessions = getattr(job, '_indicf5_sessions', None)
            if sessions is None:
                sessions = job._indicf5_sessions = {}
            if key not in sessions:
                sessions[key] = FeatureSession(job, executable, {**self.contract, 'device': self.device},
                    worker=project_root() / 'core/indicf5_worker.py', operation='indicf5_session')
            session = sessions[key]
        from core.pipeline import _staged_output
        from core.audio_utils import load_speech_audio
        with _staged_output(output_path) as pending:
            request=dict(text=text.strip(), output_path=str(Path(pending).resolve()), profile=profile)
            if minimum_sentence_seconds is not None:
                request['minimum_sentence_seconds']=minimum_sentence_seconds
            if continuous_utterance:
                request['continuous_utterance']=True
            self.last_result = session.call(request)
            load_speech_audio(pending)
        return output_path

    def release(self):
        from core.render_context import current_job
        job = current_job()
        if job is None:
            return
        with job.lock:
            sessions = list(getattr(job, '_indicf5_sessions', {}).values())
            getattr(job, '_indicf5_sessions', {}).clear()
        for session in sessions:
            session.close()
