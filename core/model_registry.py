"""Universal model registry - one entry per connected/installed model,
spanning every pluggable stage type (stt, translation, tts, voice,
enhancer, filter, lipsync, profanity_filter). Replaces the old RVC-only
voice model list.

Persisted as models.json next to config.py (gitignored, like
settings.json - this is user-local state, not source).
"""

import os
import uuid
from copy import deepcopy
from core.json_store import JsonStore, require

import config

REGISTRY_PATH = os.path.join(config.BASE_DIR, "models.json")

# "filter" (NudeNet-style frame scanning) and "profanity_filter" (text
# moderation) are deliberately separate stage types, not two kinds of one
# "filter" - they operate on completely different data (video frames vs
# transcript text) and are shown in the Marketplace as "Visual Filter" and
# "Profanity Filter" respectively (see frontend/src/pages/Marketplace.tsx).
# profanity_filter can be browsed/connected here like any other stage, but
# core/pipeline.py doesn't call through it yet - see core/providers/base.py.
STAGE_TYPES = ["stt", "translation", "tts", "voice", "enhancer", "filter", "lipsync", "profanity_filter"]
KINDS = ["local_file", "local_api", "cloud_api"]


def _validate(data):
    require(isinstance(data, dict), 'Registry must be an object')
    entries, active = data.get('entries'), data.get('active')
    require(isinstance(entries, list) and isinstance(active, dict), 'Invalid registry entries/active structure')
    ids = set()
    for entry in entries:
        require(isinstance(entry, dict), 'Model entry must be an object')
        identifier = entry.get('id')
        require(isinstance(identifier, str) and bool(identifier) and identifier not in ids, 'Invalid or duplicate model id')
        ids.add(identifier)
        require(entry.get('stage_type') in STAGE_TYPES and entry.get('kind') in KINDS, 'Invalid model stage/kind')
        require(isinstance(entry.get('display_name'), str), 'Invalid model display name')
        require(isinstance(entry.get('meta', {}), dict), 'Model metadata must be an object')
        for field in ('source_url', 'local_path', 'api_base_url', 'credential_ref', 'status', 'custom_instructions'):
            require(entry.get(field) is None or isinstance(entry[field], str), 'Invalid model field: ' + field)
        require(entry.get('request_preset') is None or isinstance(entry['request_preset'], (str, dict)), 'Invalid request preset')
    for stage, identifier in active.items():
        require(stage in STAGE_TYPES and (identifier is None or isinstance(identifier, str) and identifier in ids), 'Invalid active model reference')
    return data


class ModelRegistry:
    def __init__(self, warning=None):
        self._store = JsonStore(REGISTRY_PATH, {'entries': [], 'active': {}}, _validate, warning)
        self._load()

    def _load(self):
        with self._store.locked():
            data = self._store.read()
            self._entries, self._active = deepcopy(data['entries']), deepcopy(data['active'])
            return data

    def _mutate(self, change):
        with self._store.locked():
            data, result = self._store.mutate(change)
            self._entries, self._active = data['entries'], data['active']
            return result

    def list(self, stage_type=None):
        entries = self._load()['entries']
        return entries if stage_type is None else [e for e in entries if e['stage_type'] == stage_type]

    def get(self, model_id):
        return next((e for e in self._load()['entries'] if e['id'] == model_id), None)

    def add(self, stage_type, kind, display_name, **fields):
        if stage_type not in STAGE_TYPES:
            raise ValueError(f"Unknown stage_type: {stage_type}")
        if kind not in KINDS:
            raise ValueError(f"Unknown kind: {kind}")

        entry = {
            "id": str(uuid.uuid4()),
            "stage_type": stage_type,
            "kind": kind,
            "display_name": display_name,
            "source_url": fields.get("source_url"),
            "local_path": fields.get("local_path"),
            "api_base_url": fields.get("api_base_url"),
            "credential_ref": fields.get("credential_ref"),
            "request_preset": fields.get("request_preset"),
            "status": fields.get("status", "not_downloaded" if kind == "local_file" else "installed"),
            "meta": fields.get("meta", {}),
            # Free-text steering for stages backed by an instructable model
            # (translation's LLM prompt, profanity_filter's rewrite prompt) -
            # see core/providers/translation/*.py and
            # core/providers/profanity_filter/*.py for where it's actually
            # applied. Harmless to set on any stage type, but only those two
            # ever read it; fixed-function engines (Whisper, RVC, GFPGAN,
            # NudeNet, Wav2Lip) have no mechanism to honor it.
            "custom_instructions": fields.get("custom_instructions") or "",
        }
        def change(data):
            data['entries'].append(entry)
            if (stage_type not in data['active'] and entry['status'] == 'installed'
                    and (kind != 'local_file' or entry.get('local_path') and os.path.exists(entry['local_path']))):
                data['active'][stage_type] = entry['id']
            return entry
        return self._mutate(change)

    def update(self, model_id, **fields):
        def change(data):
            entry = next((e for e in data['entries'] if e['id'] == model_id), None)
            if entry is not None:
                entry.update(fields)
                if (not data['active'].get(entry['stage_type']) and entry.get('status') == 'installed'
                        and (entry['kind'] != 'local_file' or entry.get('local_path') and os.path.exists(entry['local_path']))):
                    data['active'][entry['stage_type']] = entry['id']
            return entry
        return self._mutate(change)

    def remove(self, model_id):
        def change(data):
            data['entries'] = [e for e in data['entries'] if e['id'] != model_id]
            data['active'] = {stage: identifier for stage, identifier in data['active'].items() if identifier != model_id}
        self._mutate(change)

    def set_active(self, stage_type, model_id):
        def change(data):
            if model_id is not None:
                entry = next((e for e in data['entries'] if e['id'] == model_id), None)
                if entry is None:
                    raise ValueError(f'No such model: {model_id}')
                if entry['stage_type'] != stage_type:
                    raise ValueError('Selected model belongs to a different pipeline stage')
                if entry.get('status') != 'installed':
                    raise ValueError('Selected model is not installed/ready')
                if entry['kind'] == 'local_file' and entry.get('request_preset') != 'airllm':
                    if not entry.get('local_path') or not os.path.exists(entry['local_path']):
                        raise ValueError('Selected model files are missing')
            data['active'][stage_type] = model_id
        self._mutate(change)

    def get_active(self, stage_type):
        data = self._load()
        identifier = data['active'].get(stage_type)
        return next((e for e in data['entries'] if e['id'] == identifier), None)

    def get_active_map(self):
        data = self._load()
        entries = {entry['id']: entry for entry in data['entries']}
        return {stage: entries.get(data['active'].get(stage)) for stage in STAGE_TYPES}

    def snapshot(self):
        """Freeze entries and selections together for one pipeline run."""
        from core.pipeline_contracts import RegistrySnapshot
        return RegistrySnapshot(self._load())
