"""Versioned fixed-template plans and cue provenance; no engine dependencies."""
from copy import deepcopy
import hashlib
import json

TEMPLATES = {
    'video_dub': {'label': 'Video -> Dubbed Video', 'input_kind': 'video'},
    'video_dub_lipsync': {'label': 'Video -> Dubbed Video + Lip Sync', 'input_kind': 'video'},
    'audio_dub': {'label': 'Audio -> Dubbed Audio', 'input_kind': 'audio'},
    'subtitle_translate': {'label': 'Subtitles -> Translated Subtitles', 'input_kind': 'subtitle'},
}
_COMMON = dict(target_lang='en', source_language='auto')
_AUDIO = dict(cast_list=['CLONED_USER'], user_voice_path=None, keep_background=True,
              compute_device=None, parallel_workers=1, sub_style=None, export_stems=False)
_VIDEO = dict(blur_strength=15, pitch_shift=0, lip_sync_active=False, enhance_active=False,
              burn_subtitles=False, content_filter_active=False, task_priority=75,
              texture_quality=1, include_subtitles=True)
PROVIDER_STAGES = ('stt', 'translation', 'tts', 'voice', 'enhancer', 'filter', 'lipsync', 'profanity_filter')


def template_kwargs(template_id, params, resolve_cast):
    """One frontend mapping for dashboard, nodes and future manager operations."""
    if template_id not in TEMPLATES:
        raise ValueError(f'Unknown pipeline template: {template_id}')
    result = dict(target_lang=params['lang'], source_language=params.get('source_language', 'auto'))
    if template_id == 'subtitle_translate':
        return result
    result.update(cast_list=params.get('cast_list') or resolve_cast(params),
        user_voice_path=params.get('ref_audio'), keep_background=params.get('keep_bg', True),
        compute_device=params.get('device_id'), parallel_workers=params.get('parallel_workers', 1),
        sub_style=params.get('sub_style'), export_stems=params.get('export_stems', False))
    if TEMPLATES[template_id]['input_kind'] == 'video':
        result.update(lip_sync_active=params.get('lipsync', False),
            enhance_active=params.get('enhance', False), burn_subtitles=params.get('burn_subs', False),
            include_subtitles=params.get('include_subtitles', True),
            content_filter_active=params.get('content_filter', False),
            task_priority=params.get('task_priority', 75), texture_quality=params.get('texture_quality', 1))
    return deepcopy(result)


class PipelineSpec:
    """Own the plan; callers receive copies and cannot mutate a running job."""
    def __init__(self, template_id, params=None, default_device='cpu'):
        if template_id not in TEMPLATES:
            raise ValueError(f'Unknown pipeline template: {template_id}')
        defaults = deepcopy(_COMMON)
        kind = TEMPLATES[template_id]['input_kind']
        if kind != 'subtitle':
            defaults.update(deepcopy(_AUDIO))
        if kind == 'video':
            defaults.update(_VIDEO)
        unknown = set(params or {}) - defaults.keys()
        if unknown:
            raise TypeError('Unsupported pipeline parameters: ' + ', '.join(sorted(unknown)))
        defaults.update(deepcopy(params or {}))
        warnings = []
        if kind != 'subtitle':
            defaults['cast_list'] = defaults['cast_list'] or ['CLONED_USER']
            device = defaults['compute_device'] or default_device
            defaults['compute_device'] = 'cpu' if device.startswith('other:') else device
            if device.startswith('other:'):
                warnings.append(f"'{device}' isn't a torch-accelerated device; using CPU instead.")
        if template_id == 'video_dub_lipsync':
            defaults['lip_sync_active'] = True
        stages = ['parse_subtitles'] if kind == 'subtitle' else ['preprocess']
        if kind != 'subtitle':
            if defaults['keep_background']:
                stages.append('separate')
            stages.append('stt')
        if defaults['target_lang'] != 'source':
            stages.append('translation')
        stages.append('moderation_if_selected')
        if kind != 'subtitle':
            stages += ['dialogue', 'speech', 'timing', 'mix']
            for flag, stage in [('lip_sync_active', 'lipsync'), ('enhance_active', 'enhancer'),
                                ('content_filter_active', 'filter')]:
                if defaults.get(flag):
                    stages.append(stage)
        stages.append('export')
        self._payload = dict(schema='reflow.pipeline-spec.v1', template_id=template_id,
            input_kind=kind, requested_parameters=deepcopy(params or {}),
            parameters=defaults, stages=stages, warnings=warnings,
            fallback_policy='existing-provider-policy-observed', retry_limit=0)

    def to_payload(self):
        return deepcopy(self._payload)

    @property
    def parameters(self):
        return deepcopy(self._payload['parameters'])


def _identity(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()[:24]


def identify_cues(segments, namespace='recognition'):
    """Assign identity before grouping, keeping legacy start/end/text consumers."""
    result = []
    identifiers = set()
    for index, original in enumerate(segments):
        cue = deepcopy(original)
        if cue.get('schema') != 'reflow.cue.v1':
            if 'cue_id' in cue:
                cue['provider_cue_id'] = cue['cue_id']
            cue['cue_id'] = 'cue-' + _identity([namespace, index, cue['start'], cue['end'], cue['text']])
            cue.update(source_text=cue['text'], source_start=cue['start'], source_end=cue['end'],
                       parent_ids=[], translated_text=None, adapted_text=None, revision=0)
        if not isinstance(cue.get('cue_id'), str) or not cue['cue_id'] or cue['cue_id'] in identifiers:
            raise ValueError('Cue identities must be nonempty and unique.')
        identifiers.add(cue['cue_id'])
        cue.setdefault('schema', 'reflow.cue.v1')
        cue.setdefault('parent_ids', [])
        cue.setdefault('source_text', cue['text'])
        cue.setdefault('source_start', cue['start'])
        cue.setdefault('source_end', cue['end'])
        cue.setdefault('translated_text', None)
        cue.setdefault('adapted_text', None)
        cue.setdefault('revision', 0)
        result.append(cue)
    return result


def finalize_grouped_cues(segments):
    """A merge creates a child identity and retains all original fragments."""
    result = []
    for original in segments:
        cue = deepcopy(original)
        fragments = cue.get('source_fragments') or [cue]
        parents = [part['cue_id'] for part in fragments if part.get('cue_id')]
        if len(parents) > 1:
            cue['cue_id'] = 'cue-' + _identity(['group', parents])
            cue['parent_ids'] = parents
            cue['source_text'] = cue['text']
            cue['source_start'], cue['source_end'] = cue['start'], cue['end']
        result.append(cue)
    return result


class RegistrySnapshot:
    """Read-only adapter-compatible registry; never writes user state."""
    def __init__(self, data):
        self._data = deepcopy(data)

    def list(self, stage_type=None):
        entries = self._data['entries']
        return deepcopy(entries if stage_type is None else [e for e in entries if e['stage_type'] == stage_type])

    def get(self, identifier):
        return next((entry for entry in self.list() if entry['id'] == identifier), None)

    def get_active(self, stage):
        return self.get(self._data['active'].get(stage))

    def get_active_map(self):
        return {stage: self.get_active(stage) for stage in PROVIDER_STAGES}

    def snapshot(self):
        return RegistrySnapshot(self._data)


class SettingsSnapshot:
    def __init__(self, values):
        self._values = deepcopy(values)

    def get(self, key):
        return deepcopy(self._values.get(key))

    def all(self):
        return deepcopy(self._values)
