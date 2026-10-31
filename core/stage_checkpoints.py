"""Verified local recognition/translation reuse; never stores generated speech."""
from copy import deepcopy
import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
import stat
import wave

from core.render_context import check_cancelled, RenderCancelled
from core.run_manifest import _publish_bytes, file_identity, provider_identity
from core.transcription import normalize_transcription, require_media_bounds, require_spoken_transcription

MAX_BYTES = 32 * 1024 * 1024
SUPPORTED = {
    'stt': 'core.providers.stt.whisper_turbo_local.WhisperTurboLocalProvider',
    'translation': 'core.providers.translation.indictrans2_local.IndicTrans2LocalProvider',
}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def safe_path(path):
    """Reject links/junctions before resolving a cache or fingerprint path."""
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if part.exists():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Checkpoint paths must not contain links or junctions.')
    return path


def tree_identity(root, suffixes=None):
    root = safe_path(root)
    records = []
    def checked_stat(path):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Fingerprint artifacts must not contain links or junctions.')
        return info
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in ('.git', '.cache', '__pycache__'))
        # Each walked parent was already checked. Check its children once,
        # rather than walking every ancestor again for every runtime file.
        for name in dirs:
            checked_stat(Path(directory) / name)
        for name in sorted(files):
            path = Path(directory) / name
            if suffixes is None or path.suffix.lower() in suffixes or name in ('METADATA', 'RECORD'):
                before = checked_stat(path)
                value = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        check_cancelled()
                        value.update(block)
                after = checked_stat(path)
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Artifact changed during fingerprinting.')
                records.append([path.relative_to(root).as_posix(), after.st_size, value.hexdigest()])
    if not records:
        raise ValueError('No fingerprintable local artifacts.')
    return digest(records)


def validate_payload(payload, stage, inputs):
    result = normalize_transcription(payload)
    require_spoken_transcription(result)
    identifiers = set()
    for cue in result:
        if (cue.get('schema') != 'reflow.cue.v1' or not isinstance(cue.get('cue_id'), str)
                or not re.fullmatch('cue-[a-f0-9]{24}', cue['cue_id'])):
            raise ValueError('Checkpoint lacks canonical cue identities.')
        if cue['cue_id'] in identifiers:
            raise ValueError('Duplicate checkpoint cue identity.')
        identifiers.add(cue['cue_id'])
        for field in ('source_text', 'text'):
            if not isinstance(cue.get(field), str) or not cue[field].strip():
                raise ValueError('Checkpoint contains invalid cue text.')
        for field in ('start', 'end', 'source_start', 'source_end'):
            value = cue.get(field)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Checkpoint contains invalid timestamps.')
        if not 0 <= cue['start'] < cue['end'] or not 0 <= cue['source_start'] < cue['source_end']:
            raise ValueError('Checkpoint contains invalid cue windows.')
        if not isinstance(cue.get('parent_ids'), list) or type(cue.get('revision')) is not int:
            raise ValueError('Checkpoint contains invalid lineage.')
    if stage == 'stt':
        require_media_bounds(result, inputs['duration'])
        if any(cue['text'] != cue['source_text'] or cue.get('translated_text') is not None for cue in result):
            raise ValueError('Recognition checkpoint contains altered speech text.')
    else:
        original = inputs['transcript']['segments']
        if len(original) != len(result):
            raise ValueError('Translation changed the number of cues.')
        if (result.language, result.language_probability, result.language_origin) != (
                inputs['transcript'].get('language'), inputs['transcript'].get('language_probability'),
                inputs['transcript'].get('language_origin')):
            raise ValueError('Translation changed recognition metadata.')
        for before, after in zip(original, result):
            for field in ('cue_id', 'start', 'end', 'source_text', 'source_start', 'source_end', 'parent_ids'):
                if before.get(field) != after.get(field):
                    raise ValueError('Translation changed recognition provenance.')
            if not isinstance(after.get('translated_text'), str) or after['text'] != after['translated_text']:
                raise ValueError('Translation checkpoint must contain an unmodified translation.')
    return result


class StageCheckpoints:
    def __init__(self, root, manifest, registry, project_root):
        self.root, self.manifest, self.registry = Path(root), manifest, registry
        self.project_root = Path(project_root)
        self.fingerprints = {}

    def event(self, stage, status, key=None, **evidence):
        with self.manifest.lock:
            self.manifest.data['checkpoints'].append(dict(stage=stage, status=status, key=key, **evidence))
            self.manifest.save()

    def key(self, stage, provider, inputs, disabled=False):
        entry = self.registry.get_active(stage)
        if disabled or not entry or entry.get('kind') != 'local_file' or provider_identity(provider)['adapter'] != SUPPORTED.get(stage):
            self.event(stage, 'disabled', reason='unsupported-provider-or-moderation')
            return None
        try:
            model = Path(entry['local_path'])
            if stage == 'stt':
                from core.whisper_turbo_assets import isolated_interpreter
            else:
                from core.indictrans2_assets import isolated_interpreter
            runtime = Path(isolated_interpreter()).parent
            def fingerprint(path, suffixes=None):
                cache_key = (str(path), tuple(sorted(suffixes or [])))
                if cache_key not in self.fingerprints:
                    self.fingerprints[cache_key] = tree_identity(path, suffixes)
                return self.fingerprints[cache_key]
            return digest(dict(schema='reflow.checkpoint-key.v1', stage=stage, inputs=inputs,
                source_sha256=self.manifest.data['source']['sha256'], entry=digest(entry),
                adapter=SUPPORTED[stage], model=fingerprint(model),
                runtime=fingerprint(runtime),
                code=fingerprint(self.project_root / 'core', {'.py'}),
                configuration_code=file_identity(self.project_root / 'config.py')['sha256']))
        except RenderCancelled:
            raise
        except (OSError, ValueError, KeyError) as error:
            self.event(stage, 'disabled', reason='fingerprint-unavailable', error_type=type(error).__name__)
            return None

    def path(self, stage, key):
        if stage not in SUPPORTED or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid checkpoint identity.')
        return safe_path(self.root / stage / (key + '.json'))

    def load(self, stage, key, inputs):
        if key is None:
            return None
        try:
            check_cancelled()
            path = self.path(stage, key)
            if path.stat().st_size > MAX_BYTES:
                raise ValueError('Checkpoint exceeds size limit.')
            with path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Checkpoint exceeds size limit.')
            item = json.loads(raw)
            if (item['schema'] != 'reflow.stage-checkpoint.v1' or item['stage'] != stage
                    or item['key'] != key or digest(item['payload']) != item['payload_sha256']):
                raise ValueError('Checkpoint integrity mismatch.')
            result = validate_payload(item['payload'], stage, inputs)
            self.event(stage, 'hit', key, origin_run_id=item['origin_run_id'],
                       payload_sha256=item['payload_sha256'], producer=item['producer'])
            self.manifest.cues(stage + '-reused', result)
            logging.info('[CHECKPOINT] Reused verified %s results.', stage)
            return result
        except FileNotFoundError:
            self.event(stage, 'miss', key)
        except RenderCancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.event(stage, 'invalid', key, error_type=type(error).__name__)
        return None

    def store(self, stage, key, inputs, transcript, provider):
        if key is None:
            return
        check_cancelled()
        payload = deepcopy(transcript.to_payload())
        validate_payload(payload, stage, inputs)
        item = dict(schema='reflow.stage-checkpoint.v1', stage=stage, key=key, payload=payload,
                    payload_sha256=digest(payload), origin_run_id=self.manifest.data['run_id'],
                    producer=provider_identity(provider))
        content = encoded(item)
        if len(content) > MAX_BYTES:
            self.event(stage, 'not-stored', key, reason='size-limit')
            return
        try:
            path = self.path(stage, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            safe_path(path)
            _publish_bytes(path, content)
        except OSError as error:
            self.event(stage, 'not-stored', key, error_type=type(error).__name__)
            return
        self.event(stage, 'stored', key, payload_sha256=item['payload_sha256'])


def recognition_inputs(audio, continuations, provider, source_language='auto'):
    from core.source_language import normalize_source_selection
    selected = normalize_source_selection(source_language)
    identity = file_identity(audio)
    with wave.open(str(audio), 'rb') as stream:
        duration = stream.getnframes() / stream.getframerate()
    return dict(audio_sha256=identity['sha256'], duration=duration, source_language=selected,
                sentence_continuations=continuations,
                prefers_sentence_groups=getattr(provider, 'prefers_sentence_groups', False) is True)
