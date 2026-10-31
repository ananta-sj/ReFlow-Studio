"""XTTS language checks without imports of engines or model downloads."""
import json
from pathlib import Path
import config
from core.languages import LANGUAGE_NAMES
from core.source_language import coerce_source_language

DEFAULT_XTTS_LANGUAGES = frozenset("en es fr de it pt pl tr ru nl cs ar zh-cn hu ko ja hi".split())
XTTS_ALIASES = {"zh": "zh-cn", "zh-Hans": "zh-cn", "zh-Hant": "zh-cn"}


def resolve_speech_language(target, source=None):
    if target != "source":
        if target not in LANGUAGE_NAMES:
            raise ValueError(f"Unknown speech target language: {target}")
        return target
    source = coerce_source_language(source)
    if not source.resolved:
        raise ValueError("Keeping source speech requires a resolved source language. "
                         "Select the source language manually or use reliable automatic detection.")
    return source.code


def require_xtts_language(language, model_path=None):
    directory = Path(model_path) if model_path is not None else Path(config.MODELS_DIR) / "xtts" / "default"
    path = directory / "config.json"
    if not path.is_file() and model_path is None:
        # Default checkpoint contract before its config is downloaded. Rechecked
        # against the actual config by TTSHandler before generation.
        languages = DEFAULT_XTTS_LANGUAGES
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read XTTS language configuration at {path}: {exc}") from exc
        if not isinstance(data, dict) or data.get("model") != "xtts":
            raise ValueError(f"Selected speech configuration is not XTTS: {path}")
        languages = data.get("languages")
        if (not isinstance(languages, list) or not languages or
                any(not isinstance(code, str) or not code.strip() or code != code.strip() for code in languages)):
            raise ValueError(f"Invalid XTTS languages in {path}")
    engine_code = XTTS_ALIASES.get(language, language)
    if engine_code not in languages:
        raise ValueError(f"XTTS does not support speech language '{language}' in this checkpoint. "
                         "Select a supported target or another speech generator.")
    return engine_code


def actor_uses_f5(registry, actor):
    if actor == 'CLONED_USER':
        return False
    from core.providers.resolve import voice_entry
    entry = voice_entry(registry, actor)
    return bool(actor != "CLONED_USER" and entry and entry.get("kind") not in
                ("cloud_api", "local_api") and entry.get("request_preset") == "f5tts")


def preflight_speech(registry, actors, language):
    from core.providers.resolve import voice_entry
    for actor in actors:
        if actor_uses_f5(registry, actor):
            entry = voice_entry(registry, actor)
            languages = (entry.get('meta') or {}).get('supported_languages', ['en', 'zh'])
            normalized = 'zh' if language in ('zh', 'zh-cn', 'zh-Hans', 'zh-Hant') else language
            if (not isinstance(languages, list) or not languages or
                    any(not isinstance(code, str) for code in languages) or normalized not in languages):
                raise ValueError(f"F5 checkpoint does not declare support for speech language '{language}'. "
                                 'The default F5 v1 Base checkpoint supports English and Chinese.')
    if not any(not actor_uses_f5(registry, actor) for actor in actors):
        return
    entry = registry.get_active("tts") if registry else None
    if entry and entry.get("kind") in ("cloud_api", "local_api"):
        return
    model_path = entry.get("local_path") if entry and entry.get("kind") == "local_file" else None
    if model_path:
        try:
            indicative = json.loads((Path(model_path) / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            indicative = {}
        if isinstance(indicative, dict) and indicative.get('model_type') == 'inf5':
            from core.model_contract import local_contract
            local_contract('tts', model_path, entry.get('request_preset'))
            if language != 'hi':
                raise ValueError('This IndicF5 route has been validated for Hindi only.')
            if any(actor != 'CLONED_USER' and not actor_uses_f5(registry, actor) for actor in actors):
                raise ValueError('IndicF5 currently uses a confirmed user reference, without RVC conversion.')
            from core.providers.tts.indicf5_local import load_reference_profile
            load_reference_profile((entry.get('meta') or {}).get('reference_profile'))
            return
    if entry and entry.get("kind") == "local_file" and not model_path:
        raise ValueError("Selected XTTS checkpoint has no local path.")
    require_xtts_language(language, model_path)
