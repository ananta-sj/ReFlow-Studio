"""Durable, revision-checked single-voice audio review using existing engines."""
import base64
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import uuid

from pydub import AudioSegment
from core.audio_utils import AudioEngineer, load_speech_audio
from core.render_context import check_cancelled, current_job
from core.source_language import resolve_source_language
from core.speech_language import resolve_speech_language
from core.transcription import require_media_bounds
from core.json_store import JsonStore, atomic_bytes
from core import review_cue_contracts as review_contracts


def validate_manifest(value):
    """Reject malformed timing/takes before a saved record reaches playback or mixing."""
    def require(condition, message):
        if not condition:
            raise ValueError('Invalid review record: ' + message)
    def number(item):
        return type(item) in (int, float) and math.isfinite(item)
    def sha(item):
        return isinstance(item, str) and re.fullmatch('[a-f0-9]{64}', item) is not None
    require(isinstance(value, dict), 'expected an object')
    require(type(value.get('version')) is int and value['version'] == 1, 'unsupported version')
    require(type(value.get('revision')) is int and value['revision'] > 0, 'invalid revision')
    require(number(value.get('duration')) and value['duration'] > 0, 'invalid duration')
    require(number(value.get('created_at')), 'invalid creation time')
    for key in ('name', 'target_lang', 'speech_language', 'actor', 'device'):
        require(isinstance(value.get(key), str) and bool(value[key].strip()), 'invalid ' + key)
    require(value.get('source_language') is None or isinstance(value['source_language'], str), 'invalid source language')
    require(sha(value.get('configuration')), 'invalid configuration digest')
    require(isinstance(value.get('assets'), dict) and all(isinstance(key, str) and sha(item)
            for key, item in value['assets'].items()), 'invalid asset digests')
    if value.get('video_asset') is not None:
        require(isinstance(value['video_asset'],str) and value['video_asset'] in value['assets'],
                'missing source video asset')
    cues = value.get('cues')
    require(isinstance(cues, list) and bool(cues), 'no cues')
    for index, cue in enumerate(cues):
        require(isinstance(cue, dict), f'cue {index+1} must be an object')
        start, end = cue.get('start'), cue.get('end')
        require(number(start) and number(end) and 0 <= start < end <= value['duration'], f'cue {index+1} timing')
        require(index == 0 or start >= cues[index-1]['end'], f'cue {index+1} overlaps')
        for field in ('source_text', 'text'):
            require(isinstance(cue.get(field), str) and 0 < len(cue[field]) <= 4000
                    and bool(cue[field].strip()), f'cue {index+1} {field}')
        following = cues[index+1].get('start') if index+1 < len(cues) and isinstance(cues[index+1], dict) else end
        available = cue.get('available_seconds')
        require(number(following) and number(available) and available > 0
                and abs(available-(following-start)) < 1e-6, f'cue {index+1} speech window')
        for field in ('candidate', 'accepted'):
            take = cue.get(field)
            if take is None:
                continue
            require(isinstance(take, dict) and isinstance(take.get('file'), str)
                    and sha(take.get('sha256')), f'cue {index+1} {field} file')
            require(number(take.get('seconds')) and take['seconds'] > 0
                    and type(take.get('fits')) is bool, f'cue {index+1} {field} duration')
            require(take['fits'] == (round(take['seconds']*1000) <= round(available*1000)),
                    f'cue {index+1} {field} fit flag')
            require(field != 'accepted' or take['fits'], f'cue {index+1} accepted overflow')
    from core.dialogue_adaptation import validate_options
    for cue in cues:
        validate_options(cue)
    review_contracts.validate(cues)
    from core.dialogue_supervision import validate_saved
    for cue in cues:
        validate_saved(cue, value['configuration'])
        report = cue.get('dialogue_supervision')
        if report and (report['source_language'] != value.get('source_language')
                       or report['target_language'] != value['speech_language']):
            raise ValueError('Dialogue supervision language changed.')
    return value


def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            check_cancelled()
            result.update(block)
    return result.hexdigest()


def configuration(pipeline, settings):
    # Store a digest, never API keys/headers or complete provider records.
    values = settings.all()
    # Preserve saved legacy reviews when this new default is introduced;
    # opting into isolated execution must still invalidate their recipe.
    if values.get('xtts_runtime', 'legacy') == 'legacy':
        values.pop('xtts_runtime', None)
    if values.get('recognition_runtime', 'legacy') == 'legacy':
        values.pop('recognition_runtime', None)
    if values.get('nllb_runtime', 'legacy') == 'legacy':
        values.pop('nllb_runtime', None)
    if values.get('m2m100_runtime', 'legacy') == 'legacy':
        values.pop('m2m100_runtime', None)
    if values.get('enhancement_runtime','legacy')=='legacy':
        values.pop('enhancement_runtime',None)
    if values.get('separation_runtime', 'legacy') == 'legacy':
        values.pop('separation_runtime', None)
    value = {'models': pipeline.registry.list(), 'settings': values,
             'active': {stage: pipeline.registry.get_active(stage) for stage in
                        ('stt', 'translation', 'tts', 'voice', 'profanity_filter')}}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def clear_dialogue(cue):
    cue.pop('dialogue_options', None)
    cue.pop('dialogue_supervision', None)


def review_transcription_bounds(transcript, duration):
    """Clamp only the existing 50 ms end tolerance, recording its provenance."""
    require_media_bounds(transcript, duration)
    adjusted, changes = [], []
    for index, segment in enumerate(transcript):
        cue = dict(segment)
        if cue['end'] > duration:
            changes.append(dict(cue=index+1, original_end=cue['end'], end=duration,
                                reason='ASR end rounding within existing 50 ms media tolerance'))
            cue['end'] = duration
        if cue['start'] >= cue['end'] or (adjusted and cue['start'] < adjusted[-1]['end']):
            raise ValueError('Review cues must be non-overlapping and within the source')
        adjusted.append(cue)
    return transcript.with_segments(adjusted), changes


class ReviewStore:
    def __init__(self, output_root):
        self.root = Path(output_root).absolute() / 'cue-reviews'
        self.root.mkdir(parents=True, exist_ok=True)
        self.safe(self.root)

    def safe(self, path):
        path = Path(path)
        resolved = path.resolve()
        if resolved != path or not path.is_relative_to(self.root):
            raise ValueError(f'Unsafe review storage path: {path} resolved to {resolved}')
        for item in (path, *path.parents):
            try:
                attributes = item.lstat()
            except FileNotFoundError:
                continue  # A cooperating FileLock can remove its lock file.
            if item.is_symlink() or getattr(attributes, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Review storage cannot contain links or reparse points')
            if item == self.root:
                break
        return path

    def folder(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            raise ValueError('Invalid review identifier')
        return self.safe(self.root / identifier)

    def asset(self, manifest, name):
        valid_name = isinstance(name,str) and (re.fullmatch('[A-Za-z0-9_-]+[.]wav',name)
            or (name == manifest.get('video_asset') and re.fullmatch('source-video[.](mp4|mkv|mov|webm|avi|m4v)',name)))
        if (not valid_name
                or re.fullmatch('(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', name.split('.')[0], re.I)):
            raise ValueError('Invalid review asset')
        return self.safe(self.folder(manifest['id']) / name)

    def _transaction(self, identifier):
        # A stable lock identity must not resolve the replaceable review.json
        # while another process is publishing it. Readers participate too.
        anchor = self.safe(self.folder(identifier) / 'review-transaction')
        self.safe(Path(str(anchor) + '.lock'))
        return JsonStore(str(anchor), None, lambda item: item).locked()

    def load(self, identifier, revision=None):
        with self._transaction(identifier):
            return self._load_unlocked(identifier, revision)

    def _load_unlocked(self, identifier, revision=None):
        path = self.safe(self.folder(identifier) / 'review.json')
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Review record exceeds the supported size')
        result = validate_manifest(json.loads(path.read_text(encoding='utf-8')))
        if result.get('id') != identifier:
            raise ValueError('Invalid review record')
        if revision is not None and (type(revision) is not int or result['revision'] != revision):
            raise ValueError('Review changed. Reload before editing or starting work.')
        return review_contracts.migrate(result)

    def save(self, manifest, expected_revision=None):
        # Explicit writes synchronize current fields; reads never modify disk.
        for cue in manifest.get('cues', []):
            contract = cue.get('cue_contract')
            if isinstance(contract, dict) and any(contract.get(field) != cue.get(field)
                    for field in ('start', 'end', 'text')):
                review_contracts.sync(cue)
        review_contracts.migrate(manifest)
        validate_manifest(manifest)
        folder = self.folder(manifest['id'])
        pending = self.safe(folder / ('pending-' + uuid.uuid4().hex + '.json'))
        target = folder / 'review.json'
        try:
            # Reuse the installed persistence lock; do not fall back from corrupt data.
            with self._transaction(manifest['id']):
                self.safe(target)
                check_cancelled()
                if expected_revision is None:
                    if target.exists():
                        raise ValueError('Review exists. Supply its current revision before saving.')
                else:
                    self._load_unlocked(manifest['id'], expected_revision)
                pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
                job = current_job()
                if job:
                    job.publish(pending, target)
                else:
                    atomic_bytes(str(target), pending.read_bytes())
        finally:
            if pending.exists():
                pending.unlink()

    def list(self):
        result = []
        for folder in self.root.iterdir():
            if re.fullmatch('[a-f0-9]{32}', folder.name):
                try:
                    manifest = self.load(folder.name)
                    result.append({'id': manifest['id'], 'name': manifest['name'],
                                   'created_at': manifest['created_at']})
                except (OSError, ValueError, KeyError):
                    continue
        return sorted(result, key=lambda entry: entry['created_at'], reverse=True)[:50]

    def public(self, identifier):
        manifest = self.load(identifier)
        result = {key: manifest[key] for key in ('id', 'name', 'revision', 'duration', 'target_lang', 'cues')}
        result['output_kind'] = 'video' if manifest.get('video_asset') else 'audio'
        result = deepcopy(result)
        for cue in result['cues']:
            for field in ('candidate', 'accepted'):
                if cue.get(field):
                    cue[field] = {key: cue[field][key] for key in ('seconds', 'fits')}
        return result

    @staticmethod
    def cue(manifest, index):
        if type(index) is not int or not 0 <= index < len(manifest['cues']):
            raise ValueError('Invalid cue index')
        return manifest['cues'][index]

    def edit(self, identifier, revision, index, source_text, text, start=None, end=None):
        manifest = self.load(identifier, revision)
        cue = self.cue(manifest, index)
        if any(not isinstance(value, str) or not value.strip() or len(value) > 4000
               for value in (source_text, text)):
            raise ValueError('Each text must contain between 1 and 4000 characters')
        changed_text = cue['source_text'] != source_text or cue['text'] != text
        changed_timing = False
        if start is not None or end is not None:
            if any(type(value) not in (int, float) or not math.isfinite(value) for value in (start, end)):
                raise ValueError('Line timing must contain finite start and end seconds.')
            if not 0 <= start < end <= manifest['duration']:
                raise ValueError('Line timing must be within the video or audio duration, with start before end.')
            changed_timing = start != cue['start'] or end != cue['end']
        if changed_text:
            cue.update(source_text=source_text, text=text, candidate=None, accepted=None)
        if changed_timing:
            original = dict(start=cue['start'], end=cue['end'])
            cue.update(start=start, end=end)
            for number, item in enumerate(manifest['cues']):
                following = manifest['cues'][number+1]['start'] if number+1 < len(manifest['cues']) else item['end']
                item['available_seconds'] = following-item['start']
                for field in ('dialogue_options', 'dialogue_supervision'):
                    if field in item and item[field]['available_seconds'] != item['available_seconds']:
                        item.pop(field, None)
                for field in ('candidate', 'accepted'):
                    take = item.get(field)
                    if take:
                        fits = round(take['seconds']*1000) <= round(item['available_seconds']*1000)
                        if field == 'accepted' and not fits:
                            raise ValueError(f'Line {number+1}: this timing would cut accepted speech. Leave more space or change its wording first.')
                        take['fits'] = fits
            manifest['last_timing_edit'] = dict(cue=index+1, previous=original,
                updated=dict(start=start,end=end), previous_revision=revision)
        if changed_text or changed_timing:
            clear_dialogue(cue)
            review_contracts.sync(cue)
            validate_manifest(manifest)
        if changed_text or changed_timing:
            manifest['revision'] += 1
            self.save(manifest, expected_revision=revision)
        return self.public(identifier)

    def checked_audio(self, manifest, take):
        path = self.asset(manifest, take['file'])
        if digest(path) != take['sha256']:
            raise ValueError('Saved audio changed. Regenerate this cue.')
        return load_speech_audio(path)

    def combine(self, identifier, revision, index):
        manifest = self.load(identifier, revision)
        left, right = self.cue(manifest, index), self.cue(manifest, index+1)
        if right['end']-left['start'] > 30:
            raise ValueError('Combined lines must fit within 30 seconds. Choose a shorter complete sentence.')
        text = {field: left[field].strip()+' '+right[field].strip() for field in ('source_text', 'text')}
        if any(len(value) > 4000 for value in text.values()):
            raise ValueError('Combined text exceeds the 4000-character review limit.')
        left.update(**text, end=right['end'],
            available_seconds=right['start']+right['available_seconds']-left['start'],
            candidate=None, accepted=None)
        clear_dialogue(left)
        review_contracts.combine(left, right)
        del manifest['cues'][index+1]
        manifest['revision'] += 1
        self.save(manifest, expected_revision=revision)
        return self.public(identifier)

    def accept(self, identifier, revision, index):
        manifest = self.load(identifier, revision)
        cue = self.cue(manifest, index)
        take = cue.get('candidate')
        if not take or not take['fits']:
            raise ValueError('Generate a take that fits before accepting it')
        clip = self.checked_audio(manifest, take)
        if len(clip) > round(cue['available_seconds'] * 1000):
            raise ValueError('Saved take exceeds its speech window')
        cue['accepted'] = deepcopy(take)
        manifest['revision'] += 1
        self.save(manifest, expected_revision=revision)
        return self.public(identifier)

    def audio(self, identifier, index, accepted=False):
        manifest = self.load(identifier)
        cue = self.cue(manifest, index)
        take = cue.get('accepted' if accepted else 'candidate')
        if not take:
            raise ValueError('No saved audio for this cue')
        path = self.asset(manifest, take['file'])
        if path.stat().st_size > 15 * 1024 * 1024:
            raise ValueError('Preview exceeds the supported size')
        self.checked_audio(manifest, take)
        return 'data:audio/wav;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')

    def source_audio(self, identifier, index):
        import io
        manifest = self.load(identifier)
        cue = self.cue(manifest, index)
        path = self.asset(manifest, 'source.wav')
        if digest(path) != manifest['assets']['source.wav']:
            raise ValueError('Saved source audio changed. Prepare a new review.')
        clip = AudioSegment.from_file(path, start_second=cue['start'], duration=cue['end']-cue['start'])
        buffer = io.BytesIO()
        clip.export(buffer, format='wav')
        data = buffer.getvalue()
        if len(data) > 15 * 1024 * 1024:
            raise ValueError('Source preview exceeds the supported size')
        return 'data:audio/wav;base64,' + base64.b64encode(data).decode('ascii')


def prepare(store, pipeline, input_path, params, settings, progress):
    """Publish only a complete prepared snapshot; owned job cleans partial work."""
    from core.providers import resolve as providers
    from core.audio_separator import AudioSeparator
    from core.pipeline import _run_ffmpeg
    import time
    actors = params.get('cast_list') or ['CLONED_USER']
    if len(actors) != 1:
        raise ValueError('Cue review currently supports a single voice')
    device = params.get('compute_device') or 'cpu'
    if device.startswith('other:'):
        device = 'cpu'
    job = current_job()
    if job is None:
        raise RuntimeError('Cue preparation requires an owned job')
    identifier = uuid.uuid4().hex
    work = job.workspace / ('review-' + identifier)
    work.mkdir()
    source = work / 'source.wav'
    progress(5, 'PREPARING REVIEW AUDIO')
    _run_ffmpeg(['ffmpeg', '-v', 'error', '-y', '-i', input_path, '-vn', '-ac', '1', '-ar', '24000', str(source)])
    duration = pipeline.get_duration(str(source))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Source must contain playable audio')
    vocals, background = str(source), None
    if params.get('keep_background', True):
        progress(10, 'SEPARATING REVIEW AUDIO')
        vocals, background = AudioSeparator(device=device).separate(str(source))
    shutil.copy2(vocals, work / 'vocals.wav')
    if background:
        shutil.copy2(background, work / 'background.wav')
    video_asset = None
    if params.get('review_video') is True:
        from core.render_context import run_process
        from core.python_runtime import project_root
        probe = project_root()/'ffmpeg/bin'/('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        streams = json.loads(run_process([str(probe),'-v','error','-show_streams','-of','json',input_path],
                                        capture_output=True,text=True,check=True,timeout=60).stdout)['streams']
        if not any(stream.get('codec_type') == 'video' for stream in streams):
            raise ValueError('Video review input has no video stream.')
        video_asset = 'source-video'+Path(input_path).suffix.lower()
        shutil.copy2(input_path,work/video_asset)
    engineer = AudioEngineer()
    reference = params.get('user_voice_path') or str(work / 'vocals.wav')
    if providers.uses_exact_reference(pipeline.registry):
        confirmed_audio = providers.confirmed_reference(pipeline.registry, params.get('user_voice_path'))
        shutil.copy2(confirmed_audio, work / 'reference.wav')
    else:
        engineer.clean_reference_audio(reference, str(work / 'reference.wav'))
    progress(25, 'TRANSCRIBING FOR REVIEW')
    stt = providers.resolve_stt(pipeline.registry, settings.get('whisper_model_size'))
    transcript = pipeline._transcribe_source(stt, str(work / 'vocals.wav'), True)
    transcript, timestamp_adjustments = review_transcription_bounds(transcript, duration)
    source_language = resolve_source_language(params.get('source_language', 'auto'),
                                              transcript.language, transcript.language_probability)
    pipeline._report_source_language(source_language, transcript)
    target = params.get('target_lang', 'hi')
    speech_language = resolve_speech_language(target, source_language)
    pipeline._check_speech_routes(actors, speech_language, transcript)
    cues = []
    translator = filter_provider = None
    if target != 'source':
        translator, instructions, filter_provider, filter_instructions = pipeline._resolve_translation_and_filter(settings)
    from core.pipeline import _translation_stage
    with _translation_stage(translator):
        for index, segment in enumerate(transcript):
            check_cancelled()
            if segment['start'] < 0 or segment['end'] > duration or (index and segment['start'] < transcript[index-1]['end']):
                raise ValueError('Review cues must be non-overlapping and within the source')
            text = segment['text']
            if target != 'source':
                text = pipeline._translate_line(text, pipeline._translation_target(target), translator,
                    instructions, filter_provider, filter_instructions,
                    context=f'Review cue {index+1}', source_language=source_language, cue=segment)
            else:
                filtered = pipeline._moderate_source([dict(segment)], settings)
                text = filtered[0]['text']
            next_start = transcript[index+1]['start'] if index+1 < len(transcript) else segment['end']
            cues.append(dict(start=segment['start'], end=segment['end'], source_text=segment['text'], text=text,
                             available_seconds=next_start-segment['start'], candidate=None, accepted=None))
            review_contracts.attach(cues[-1], identifier, index, recognized=segment)
            progress(30 + int(60 * (index+1)/len(transcript)), f'TRANSLATING REVIEW CUE {index+1}/{len(transcript)}')
    del translator, filter_provider
    pipeline.clear_vram()
    assets = {path.name: digest(path) for path in work.iterdir() if path.is_file()}
    manifest = dict(version=1, id=identifier, revision=1, created_at=time.time(), name=Path(input_path).name,
                    duration=duration, target_lang=target, speech_language=speech_language,
                    source_language=source_language.code, actor=actors[0], device=device,
                    configuration=configuration(pipeline, settings), assets=assets, cues=cues,
                    timestamp_adjustments=timestamp_adjustments,
                    recognition=transcript.to_payload())
    if video_asset:
        manifest['video_asset'] = video_asset
    validate_manifest(manifest)
    (work / 'review.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    job.publish(work, store.folder(identifier))
    progress(100, 'REVIEW READY — EDIT AND AUDITION CUES')
    return str(store.folder(identifier) / 'review.json')


def estimate_timing(store, pipeline, identifier, revision, index, settings):
    """Read-only native budget check; no worker, inference or take mutation."""
    from core.providers import resolve as providers
    manifest = store.load(identifier, revision)
    cue = store.cue(manifest, index)
    if configuration(pipeline, settings) != manifest['configuration']:
        raise ValueError('Model connections or settings changed. Prepare a new review with the current configuration.')
    reference = store.asset(manifest, 'reference.wav')
    if digest(reference) != manifest['assets']['reference.wav']:
        raise ValueError('Review reference audio changed. Prepare a new review.')
    if not providers.uses_exact_reference(pipeline.registry):
        return dict(supported=False, available_seconds=cue['available_seconds'],
                    message='This voice has no pre-generation estimate. Generate and audition a take.')
    providers.confirmed_reference(pipeline.registry, str(reference))
    tts = providers.resolve_tts(pipeline.registry, manifest['device'], runtime=settings.get('xtts_runtime'))
    seconds = tts.estimate_duration_seconds(cue['text'])
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('The voice returned an invalid speech duration estimate.')
    return dict(supported=True, estimated_seconds=seconds, available_seconds=cue['available_seconds'],
                fits=round(seconds*1000) <= round(cue['available_seconds']*1000))


def _supervise_review(store, pipeline, manifest, cue, settings, progress):
    from types import SimpleNamespace
    from core.pipeline_contracts import SettingsSnapshot, PipelineSpec
    from core.providers import resolve as providers
    from core import dialogue_connections
    from core.dialogue_supervision import supervise
    from core.run_manifest import RunManifest
    from core.render_context import RenderCancelled
    frozen_registry = pipeline.registry.snapshot()
    frozen_settings = SettingsSnapshot(settings.all())
    saved_configuration = manifest['configuration']
    if configuration(SimpleNamespace(registry=frozen_registry), frozen_settings) != saved_configuration:
        raise ValueError('Connections or settings changed. Prepare a new review.')
    measured = (manifest['source_language'] == 'en' and manifest['speech_language'] == 'en'
                and manifest['target_lang'] in ('source', 'en') and manifest['actor'] == 'CLONED_USER')
    if not measured and (manifest['target_lang'] != 'hi' or manifest['source_language'] != 'en' or manifest['actor'] != 'CLONED_USER'):
        raise ValueError('Assisted dialogue review currently supports English-to-Hindi with the confirmed native voice.')
    if frozen_registry.get_active('profanity_filter'):
        raise ValueError('Assisted rewriting is unavailable while a profanity filter is selected.')
    if (frozen_registry.get_active('translation') or {}).get('custom_instructions'):
        raise ValueError('Clear custom translation instructions before assisted rewriting.')
    if not measured and not providers.uses_exact_reference(frozen_registry):
        raise ValueError('Select the confirmed native Hindi voice for assisted dialogue review.')
    # Resolve configuration only; this performs no discovery or model query.
    writer, reviewer = dialogue_connections.resolve(frozen_settings.all(), frozen_registry)
    reference = store.asset(manifest, 'reference.wav')
    source = store.asset(manifest, 'source.wav')
    for name, path in (('reference.wav', reference), ('source.wav', source)):
        if name not in manifest['assets'] or digest(path) != manifest['assets'][name]:
            raise ValueError('Saved review audio changed. Prepare a new review.')
    if measured:
        from core.dialogue_supervision import _measured_take
        _measured_take(cue.get('candidate'), cue['available_seconds'])
        clip = store.checked_audio(manifest, cue['candidate'])
        if abs(len(clip)/1000-cue['candidate']['seconds']) > .001:
            raise ValueError('Saved take duration differs from its audio. Generate a new take.')
    else:
        providers.confirmed_reference(frozen_registry, str(reference))
    tts = providers.resolve_tts(frozen_registry, manifest['device'], runtime=frozen_settings.get('xtts_runtime'))
    record = RunManifest(Path(pipeline.output_dir)/'run_records',
        PipelineSpec('audio_dub', dict(target_lang=manifest['target_lang'])), source, frozen_registry, frozen_settings)
    record.data['review_action'] = dict(action='supervise', review_id=manifest['id'],
        cue_id=cue['cue_id'], input_revision=manifest['revision'], configuration=saved_configuration,
        generates_speech=False, renders_media=False)
    record.capture_source(source)
    def guard():
        check_cancelled()
        store.load(manifest['id'], manifest['revision'])
        if configuration(pipeline, settings) != saved_configuration:
            raise ValueError('Dialogue connections or consent changed; no further assistance requests will be made.')
        status = dialogue_connections.readiness(settings.all(), pipeline.registry)
        if not status['ready']:
            raise ValueError(status['message'])
        for name, path in (('reference.wav', reference), ('source.wav', source)):
            if digest(path) != manifest['assets'][name]:
                raise ValueError('Saved review audio changed; no further assistance requests will be made.')
        if measured:
            clip = store.checked_audio(manifest, cue['candidate'])
            if abs(len(clip)/1000-cue['candidate']['seconds']) > .001:
                raise ValueError('Saved take duration differs from its audio. Generate a new take.')
    try:
        guard()
        progress(10, 'REVIEWING DIALOGUE WORDING')
        report = supervise(tts, writer, reviewer, cue['source_text'], cue['text'], cue['available_seconds'],
            manifest=record, review_binding=dict(cue_id=cue['cue_id'], configuration=saved_configuration,
                input_revision=manifest['revision'], run_id=record.data['run_id']), before_request=guard,
            **(dict(target_language='en', measured_take=cue['candidate']) if measured else {}))
        guard()
        with record.operation('review-publication', evidence=dict(review_id=manifest['id'], cue_id=cue['cue_id'])):
            cue['dialogue_supervision'] = report
            cue.pop('dialogue_options', None)
            revision = manifest['revision']
            manifest['revision'] += 1
            store.save(manifest, expected_revision=revision)
        output = store.folder(manifest['id'])/'review.json'
        record.finish('needs_review' if report['status'] == 'needs_review' else 'review_ready', output=output)
        progress(100, 'WORDING READY FOR HUMAN REVIEW')
        return str(output)
    except BaseException as error:
        record.finish('cancelled' if isinstance(error, RenderCancelled) else 'failed', error=error)
        raise
    finally:
        if callable(getattr(tts, 'release', None)):
            tts.release()


def operate(store, pipeline, identifier, revision, action, index, settings, progress):
    """Long operations run under the bridge's existing cancellable worker lock."""
    from core.providers import resolve as providers
    from core.pipeline import _staged_output, _validate_media
    manifest = store.load(identifier, revision)
    if action != 'render' and configuration(pipeline, settings) != manifest['configuration']:
        raise ValueError('Model connections or settings changed. Prepare a new review with the current configuration.')
    if action in ('generate', 'translate', 'adapt', 'supervise'):
        cue = store.cue(manifest, index)
        if action == 'supervise':
            return _supervise_review(store, pipeline, manifest, cue, settings, progress)
        elif action == 'adapt':
            from core.dialogue_adaptation import propose
            from core.pipeline import _release_translation
            progress(10, 'FINDING WORDING ALTERNATIVES')
            if manifest['target_lang'] != 'hi' or manifest['source_language'] != 'en' or manifest['actor'] != 'CLONED_USER':
                raise ValueError('Wording alternatives currently support English-to-Hindi with the confirmed native voice.')
            entry = pipeline.registry.get_active('translation') or {}
            if entry.get('custom_instructions') or pipeline.registry.get_active('profanity_filter'):
                raise ValueError('Wording alternatives require an unmoderated translation without custom instructions.')
            if not providers.uses_exact_reference(pipeline.registry):
                raise ValueError('Select the confirmed native Hindi voice for wording alternatives.')
            reference = store.asset(manifest, 'reference.wav')
            if digest(reference) != manifest['assets']['reference.wav']:
                raise ValueError('Review reference audio changed. Prepare a new review.')
            providers.confirmed_reference(pipeline.registry, str(reference))
            tts = providers.resolve_tts(pipeline.registry, manifest['device'], runtime=settings.get('xtts_runtime'))
            translator = providers.resolve_translation(pipeline.registry, settings.get('ollama_host'),
                **({'runtime': settings.get('nllb_runtime')} if settings.get('nllb_runtime') == 'isolated' else {}),
                **({'fallback_runtime':'isolated'} if settings.get('m2m100_runtime') == 'isolated' else {}))
            try:
                cue['dialogue_options'] = propose(tts, translator, cue['source_text'], cue['text'],
                    pipeline._translation_target(manifest['target_lang']),
                    resolve_source_language(manifest['source_language']), cue['available_seconds'])
                cue.pop('dialogue_supervision', None)
            finally:
                _release_translation(translator)
                pipeline.clear_vram()
        elif action == 'translate':
            progress(10, 'TRANSLATING CORRECTED CUE')
            if manifest['target_lang'] == 'source':
                text = pipeline._moderate_source([dict(text=cue['source_text'])], settings)[0]['text']
            else:
                provider, instructions, filter_provider, filter_instructions = pipeline._resolve_translation_and_filter(settings)
                from core.pipeline import _translation_stage
                with _translation_stage(provider):
                    text = pipeline._translate_line(cue['source_text'], pipeline._translation_target(manifest['target_lang']),
                        provider, instructions, filter_provider, filter_instructions, context=f'Review cue {index+1}',
                        source_language=resolve_source_language(manifest['source_language']), cue=cue['cue_contract'])
                del provider, filter_provider
                pipeline.clear_vram()
            cue.update(text=text, candidate=None, accepted=None)
            clear_dialogue(cue)
            review_contracts.sync(cue)
        else:
            progress(10, f'GENERATING REVIEW CUE {index+1}')
            reference = store.asset(manifest, 'reference.wav')
            if digest(reference) != manifest['assets']['reference.wav']:
                raise ValueError('Review reference audio changed. Prepare a new review.')
            tts = providers.resolve_tts(pipeline.registry, manifest['device'], runtime=settings.get('xtts_runtime'))
            clip = pipeline._dub_segment(index, cue, [manifest['actor']], manifest['speech_language'],
                tts, {}, str(reference), str(reference), manifest['device'], AudioEngineer(),
                next_start=cue['start']+cue['available_seconds'], allow_overflow=True)
            if clip is None:
                raise ValueError('Cue contains no speech')
            filename = 'take-' + uuid.uuid4().hex + '.wav'
            pending = current_job().workspace / filename
            clip.export(pending, format='wav').close()
            destination = store.asset(manifest, filename)
            current_job().publish(pending, destination)
            cue['candidate'] = dict(file=filename, seconds=len(clip)/1000,
                fits=len(clip) <= round(cue['available_seconds']*1000), sha256=digest(destination))
            # A measured wording assessment is bound to this exact take.
            if (cue.get('dialogue_supervision') or {}).get('schema') in ('reflow.dialogue-supervision.v2', 'reflow.dialogue-supervision.v4'):
                cue.pop('dialogue_supervision', None)
            from core.providers.base import release_speech
            release_speech(tts)
            del tts
            pipeline.clear_vram()
            # Existing accepted take survives a successful or failed regeneration.
        manifest['revision'] += 1
        store.save(manifest, expected_revision=revision)
        progress(100, 'CUE READY FOR REVIEW')
        return str(store.folder(identifier) / 'review.json')
    if action != 'render':
        raise ValueError('Unknown cue review action')
    progress(10, 'ASSEMBLING ACCEPTED CUES')
    duration_ms = round(manifest['duration'] * 1000)
    voice = AudioSegment.silent(duration=duration_ms)
    for cue in manifest['cues']:
        check_cancelled()
        take = cue.get('accepted')
        if not take or not take['fits']:
            raise ValueError('Every cue needs an accepted take that fits before rendering')
        clip = store.checked_audio(manifest, take)
        if len(clip) > round(cue['available_seconds']*1000) or round(cue['start']*1000)+len(clip) > duration_ms:
            raise ValueError('Accepted cue exceeds its source window')
        voice = voice.overlay(clip, position=round(cue['start']*1000))
    mixed = voice
    if 'background.wav' in manifest['assets']:
        background = store.asset(manifest, 'background.wav')
        if digest(background) != manifest['assets']['background.wav']:
            raise ValueError('Saved background changed. Prepare a new review.')
        mixed = AudioEngineer().dynamic_mix(voice, AudioSegment.from_file(background), ducking_db=-12)
    if manifest.get('video_asset'):
        original_video = store.asset(manifest,manifest['video_asset'])
        if digest(original_video) != manifest['assets'][manifest['video_asset']]:
            raise ValueError('Saved source video changed. Prepare a new review.')
        work = current_job().workspace
        master, subtitles = work/'reviewed-master.wav',work/'reviewed-subtitles.srt'
        mixed.export(master,format='wav').close()
        pipeline.generate_srt(manifest['cues'],str(subtitles))
        output = Path(pipeline.output_dir)/('REVIEWED_VIDEO_'+uuid.uuid4().hex[:12]+'.mp4')
        with _staged_output(str(output)) as pending:
            pipeline.merge_av(str(original_video),str(master),str(subtitles),pending,
                ffmpeg_preset='veryfast',subtitle_language={'hi':'hin','en':'eng'}.get(manifest['speech_language'],'und'))
            _validate_media(pending,{'video','audio','subtitle'})
            if abs(pipeline.get_duration(pending)-manifest['duration']) > .15:
                raise ValueError('Reviewed video changed the source timeline')
        progress(100,'REVIEWED VIDEO COMPLETE')
        return str(output)
    output = Path(pipeline.output_dir) / ('REVIEWED_AUDIO_' + uuid.uuid4().hex[:12] + '.wav')
    with _staged_output(str(output)) as pending:
        mixed.export(pending, format='wav').close()
        _validate_media(pending, {'audio'})
        if abs(pipeline.get_duration(pending)-manifest['duration']) > .02:
            raise ValueError('Reviewed output changed the source timeline')
    progress(100, 'REVIEWED AUDIO COMPLETE')
    return str(output)
