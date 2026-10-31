"""Durable observations of real execution and explicit checkpoint reuse."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import threading
import time
import uuid
import wave

from core.json_store import atomic_bytes
from core.render_context import RenderCancelled, check_cancelled

_current = ContextVar('reflow_run_manifest', default=None)


def _publish_bytes(path, content):
    """Bound transient Windows sharing/rename denials; never skip persistence."""
    for attempt in range(4):
        try:
            atomic_bytes(str(path), content)
            return
        except PermissionError as error:
            if os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32) or attempt == 3:
                raise
            time.sleep(.05 * (2 ** attempt))


def current_manifest():
    return _current.get()


@contextmanager
def bind_manifest(manifest):
    token = _current.set(manifest)
    try:
        yield
    finally:
        _current.reset(token)


def file_identity(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check_cancelled()
            digest.update(block)
    result = dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())
    if path.suffix.lower() == '.wav':
        try:
            with wave.open(str(path), 'rb') as audio:
                result.update(sample_rate=audio.getframerate(), channels=audio.getnchannels(),
                    frames=audio.getnframes(), duration_seconds=audio.getnframes()/audio.getframerate())
        except (wave.Error, EOFError):
            pass  # Float/compressed WAV needs the engine's own media validation.
    return result


def _public_entry(entry):
    if not entry:
        return None
    # Do not serialize endpoints, credentials, custom headers or arbitrary metadata.
    result = {key: deepcopy(entry.get(key)) for key in
              ('id', 'stage_type', 'kind', 'display_name', 'local_path', 'status')}
    preset = entry.get('request_preset')
    result['request_preset'] = preset if isinstance(preset, str) else 'custom' if preset else None
    result['meta'] = {key: deepcopy(entry.get('meta', {}).get(key)) for key in
                      ('reference_profile', 'speech_device', 'compression', 'voice_id')}
    instructions = entry.get('custom_instructions') or ''
    result['instructions_sha256'] = hashlib.sha256(instructions.encode('utf-8')).hexdigest()
    result['configuration_sha256'] = hashlib.sha256(json.dumps(entry, sort_keys=True,
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
    return result


def provider_identity(provider):
    result = {'adapter': type(provider).__module__ + '.' + type(provider).__name__}
    for key in ('engine_id', 'device', 'model_path', 'model_size', 'reference_profile', 'profile_path', 'worker_interpreter', 'runtime', 'runtime_identity', 'model_fingerprint', 'service_model', 'service_endpoint'):
        value = getattr(provider, key, None)
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
    contract = getattr(provider, 'contract', None)
    if isinstance(contract, dict):
        result['contract'] = {key: contract[key] for key in
            ('model_path', 'checkpoint_path', 'vocab_path', 'device') if key in contract}
    translator = getattr(provider, '_translator', None)
    if translator is not None:
        for key in ('mode', 'model_name', 'device'):
            value = getattr(translator, key, None)
            if isinstance(value, str):
                result['translation_' + key] = value
    profile = getattr(provider, 'profile', None)
    if isinstance(profile, dict):
        result['reference_recipe'] = {key: profile[key] for key in
            ('reference_sha256', 'seed', 'steps', 'guidance', 'sentence_gap_seconds', 'calibration_seconds')
            if key in profile}
    session = getattr(provider, 'session', None)
    if session is not None and isinstance(getattr(session, 'executable', None), (str, Path)):
        result['worker_interpreter'] = str(session.executable)
    return result


class RunManifest:
    def __init__(self, folder, spec, source, registry, settings):
        self.lock = threading.RLock()
        self.folder = Path(folder) / uuid.uuid4().hex
        self.folder.mkdir(parents=True)
        self.path = self.folder / 'manifest.json'
        self.data = dict(schema='reflow.run-manifest.v1', run_id=self.folder.name,
            created_at=datetime.now(timezone.utc).isoformat(), status='running', plan=spec.to_payload(),
            core_runtime=dict(python_version=platform.python_version(), executable=sys.executable, platform=sys.platform),
            source={'path': str(Path(source).resolve())},
            selected_engines={stage: _public_entry(entry) for stage, entry in registry.get_active_map().items()},
            selected_voices=[_public_entry(entry) for entry in registry.list('voice')
                if entry['id'] in spec.parameters.get('cast_list', [])
                or entry['display_name'] in spec.parameters.get('cast_list', [])],
            settings={key: value for key, value in settings.all().items() if key != 'ollama_host'},
            settings_sha256=hashlib.sha256(json.dumps(settings.all(), sort_keys=True,
                ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest(),
            operations=[], cue_artifacts=[], quality_reports=[], output=None, error=None,
            checkpoint_support=True, checkpoint_stages=['stt', 'translation'], checkpoints=[])
        self.save()

    def save(self):
        with self.lock:
            _publish_bytes(self.path, json.dumps(self.data, ensure_ascii=False,
                allow_nan=False, indent=2).encode('utf-8'))

    def capture_source(self, source):
        with self.lock:
            self.data['source'] = file_identity(source)
            self.save()

    def cues(self, phase, transcript):
        """Retain JSON evidence outside temporary job workspaces."""
        with self.lock:
            payload = (transcript.to_payload() if hasattr(transcript, 'to_payload')
                else deepcopy(transcript) if isinstance(transcript, dict) and 'segments' in transcript
                else {'segments': deepcopy(transcript)})
            name = f'cues-{len(self.data["cue_artifacts"]):03d}-{phase}.json'
            path = self.folder / name
            _publish_bytes(path, json.dumps(payload, ensure_ascii=False, allow_nan=False,
                indent=2).encode('utf-8'))
            self.data['cue_artifacts'].append({'phase': phase, **file_identity(path)})
            self.save()

    def report(self, kind, payload):
        with self.lock:
            path = self.folder / f'{kind}-report-{len(self.data["quality_reports"]):03d}.json'
            _publish_bytes(path, json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8'))
            self.data['quality_reports'].append(dict(kind=kind, status=payload['status'], **file_identity(path)))
            self.data['review_required'] = any(item['status'] == 'needs_review' for item in self.data['quality_reports'])
            self.save()

    @contextmanager
    def operation(self, stage, provider=None, evidence=None):
        with self.lock:
            item = dict(operation_id=uuid.uuid4().hex, stage=stage, status='running',
                evidence=deepcopy(evidence or {}), engine=provider_identity(provider) if provider else None)
            self.data['operations'].append(deepcopy(item))
            self.save()
        started = time.monotonic()
        try:
            yield item
        except BaseException as error:
            item['status'] = 'cancelled' if isinstance(error, (GeneratorExit, RenderCancelled)) else 'failed'
            # Provider errors can contain URLs/tokens. Preserve type and operation
            # identity here; the existing UI owns the diagnostic message.
            item['error'] = {'type': type(error).__name__}
            raise
        else:
            item['status'] = 'completed'
        finally:
            with self.lock:
                item['elapsed_seconds'] = time.monotonic() - started
                if provider is not None:
                    item['engine'] = provider_identity(provider)
                position = next(index for index, saved in enumerate(self.data['operations'])
                                if saved['operation_id'] == item['operation_id'])
                self.data['operations'][position] = deepcopy(item)
                self.save()

    def finish(self, status, output=None, error=None):
        with self.lock:
            artifact = file_identity(output) if output else None
            if artifact is not None and artifact['bytes'] == 0:
                raise RuntimeError('Process returned an empty output.')
            self.data.update(status=status, finished_at=datetime.now(timezone.utc).isoformat(),
                output=artifact,
                error={'type': type(error).__name__} if error else None)
            self.save()


def observe_provider(manifest, stage, provider, method, *args, cue_id=None, **kwargs):
    if manifest is None:
        return getattr(provider, method)(*args, **kwargs)
    evidence = {'method': method, 'cue_id': cue_id}
    if method in ('translate', 'filter_text', 'synthesize') and args:
        evidence['text'] = args[0]
    if method == 'convert' and isinstance(kwargs.get('text'), str):
        evidence['text'] = kwargs['text']
    if method == 'translate':
        evidence['target_language'] = args[1] if len(args) > 1 else None
        source = kwargs.get('source_language')
        evidence['source_language'] = source if isinstance(source, str) else getattr(source, 'code', None)
    evidence['parameters'] = {key: value for key, value in kwargs.items()
                             if key in ('language', 'model_name', 'minimum_sentence_seconds', 'continuous_utterance')}
    reference = kwargs.get('reference_audio')
    if reference:
        evidence['reference'] = file_identity(reference)
    with manifest.operation(stage, provider, evidence) as item:
        try:
            result = getattr(provider, method)(*args, **kwargs)
        except Exception:
            raw = getattr(provider, 'last_result', None)
            if method == 'transcribe' and isinstance(raw, dict) and 'transcription' in raw:
                manifest.cues('recognition-worker-failed', raw['transcription'])
            raise
        if method in ('translate', 'filter_text'):
            item['result_text'] = result
        elif method == 'transcribe':
            item['recognition_runtime'] = provider_identity(provider)
            manifest.cues('recognition-raw', result)
        elif method == 'separate':
            item['artifacts'] = [{**file_identity(path), 'retention': 'temporary-unless-exported'}
                                 for path in result if path and Path(path).is_file()]
        elif method in ('synthesize', 'convert', 'execute', 'scan_and_blur', 'enhance'):
            output_index = 2 if method == 'execute' else 1
            output = result if isinstance(result, (str, Path)) else args[output_index] if len(args) > output_index else None
            if output and Path(output).is_file():
                item['artifact'] = file_identity(output)
                item['artifact']['retention'] = 'temporary-unless-exported'
        return result
