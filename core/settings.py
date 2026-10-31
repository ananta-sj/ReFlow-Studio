"""Persisted user settings - a single JSON file next to config.py.

Only holds settings that affect Python-side behavior (translation host,
STT model size, render defaults, cleanup behavior). Purely cosmetic
frontend preferences (theme, experience level) live in ui_preferences.json
instead - keeping two different kinds of "settings" in two
different stores avoids the two-sources-of-truth bugs the earlier PyQt6
build ran into when the same fact was owned by two widgets at once.
"""

import os
from core.json_store import JsonStore, require

import config

SETTINGS_PATH = os.path.join(config.BASE_DIR, "settings.json")

WHISPER_MODEL_SIZES = ["tiny", "base", "small", "medium", "large"]

DEFAULTS = {
    "default_language": "en",
    "default_voice": "CLONED_USER",
    "default_task_priority": 75,
    "default_texture_quality": 1,
    "keep_bg_default": True,
    "content_filter_default": False,
    "auto_cleanup_temp": True,
    "ollama_host": "http://localhost:11434",
    "whisper_model_size": "medium",
    "xtts_runtime": "legacy",
    "recognition_runtime": "legacy",
    "nllb_runtime": "legacy",
    "m2m100_runtime": "legacy",
    "separation_runtime": "legacy",
    "enhancement_runtime": "legacy",
    "auto_detect_model_type": True,
    "search_provider": "none",
    "search_engine_id": "",
    "onboarding_complete": False,
    "dialogue_mode": "off",
    "dialogue_writer_id": "",
    "dialogue_reviewer_id": "",
    "dialogue_text_consent": False,
    "dialogue_consent_fingerprint": "",
}


def _validate(stored):
    require(isinstance(stored, dict), 'Settings must be an object')
    for key, default in DEFAULTS.items():
        if key not in stored:
            continue
        value = stored[key]
        require(type(value) is type(default), 'Invalid setting type: ' + key)
        if key == 'default_task_priority':
            require(0 <= value <= 100, 'Task priority must be between 0 and 100')
        elif key == 'default_texture_quality':
            require(value in (1, 2, 4), 'Texture quality must be 1, 2 or 4')
        elif key == 'whisper_model_size':
            require(value in WHISPER_MODEL_SIZES, 'Unknown Whisper model size')
        elif key == 'xtts_runtime':
            require(value in ('legacy', 'isolated'), 'Unknown XTTS runtime')
        elif key == 'recognition_runtime':
            require(value in ('legacy', 'isolated'), 'Unknown recognition runtime')
        elif key == 'nllb_runtime':
            require(value in ('legacy', 'isolated'), 'Unknown NLLB runtime')
        elif key == 'm2m100_runtime':
            require(value in ('legacy', 'isolated'), 'Unknown M2M100 runtime')
        elif key == 'enhancement_runtime':
            require(value in ('legacy','isolated'), 'Unknown face enhancement runtime')
        elif key == 'separation_runtime':
            require(value in ('legacy', 'isolated'), 'Unknown separation runtime')
        elif key == 'search_provider':
            require(value in ('none', 'google_cse'), 'Unknown search provider')
        elif key == 'dialogue_mode':
            require(value in ('off', 'local', 'hybrid'), 'Unknown dialogue mode')
        elif key.startswith('dialogue_') and isinstance(value, str):
            require(len(value) <= 200, 'Dialogue setting is too long')
        elif key in ('default_language', 'default_voice', 'ollama_host'):
            require(bool(value.strip()), 'Setting cannot be empty: ' + key)
    return stored


class Settings:
    def __init__(self, warning=None):
        self._store = JsonStore(SETTINGS_PATH, dict(DEFAULTS), _validate, warning)
        self._load()

    def _load(self):
        with self._store.locked():
            stored = self._store.read()
            self._values = {key: stored.get(key, default) for key, default in DEFAULTS.items()}
            return dict(self._values)

    def all(self):
        return self._load()

    def get(self, key):
        return self._load().get(key, DEFAULTS.get(key))

    def update(self, partial):
        require(isinstance(partial, dict), 'Settings update must be an object')
        with self._store.locked():
            def change(data):
                if any(key in partial and partial[key] != data.get(key, DEFAULTS[key])
                       for key in ('dialogue_mode', 'dialogue_writer_id', 'dialogue_reviewer_id')):
                    data.update(dialogue_text_consent=False, dialogue_consent_fingerprint='')
                data.update({key: value for key, value in partial.items() if key in DEFAULTS})
            stored, _ = self._store.mutate(change)
            self._values = {key: stored.get(key, default) for key, default in DEFAULTS.items()}
            return dict(self._values)

    def reset(self):
        with self._store.locked():
            def change(data):
                data.clear()
                data.update(DEFAULTS)
            stored, _ = self._store.mutate(change)
            self._values = stored
            return dict(self._values)
