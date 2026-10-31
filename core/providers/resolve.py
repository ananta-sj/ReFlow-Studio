"""Resolves which provider instance a pipeline stage should actually use,
based on core/model_registry.py. Without this, the Marketplace's "Set
Active" control would be cosmetic - the registry would hold the user's
choice but pipeline.py would keep silently using the hardcoded local
provider regardless. Falls back to the *_local provider (with the same
construction kwargs pipeline.py already computes - device, settings, etc)
whenever nothing is registered/active, so a pipeline run behaves exactly
as before for anyone who has never touched the Marketplace.
"""

_CLOUD_KINDS = ("cloud_api", "local_api")
import os
import json
from pathlib import Path
from core.model_contract import local_contract


def uses_exact_reference(registry):
    entry = registry.get_active('tts') if registry else None
    if not entry or entry.get('kind') != 'local_file' or not entry.get('local_path'):
        return False
    try:
        config = json.loads((Path(entry['local_path']) / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(config, dict) and config.get('model_type') == 'inf5'



def confirmed_reference(registry, supplied_reference=None):
    """Use the selected verified voice; validate an explicitly supplied recording."""
    import hashlib
    from core.providers.tts.indicf5_local import load_reference_profile
    entry = registry.get_active('tts')
    confirmed = load_reference_profile((entry.get('meta') or {}).get('reference_profile'))
    if supplied_reference:
        supplied = Path(supplied_reference)
        if not supplied.is_file():
            raise ValueError('The supplied Hindi voice reference does not exist.')
        with supplied.open('rb') as handle:
            digest = hashlib.sha256()
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() not in {confirmed['reference_sha256'], confirmed.get('original_source_sha256')}:
            raise ValueError('Select the audio belonging to the confirmed Hindi voice.')
    return confirmed['reference_audio']


def _local(entry):
    """Validate a selected artifact; a missing selection cannot become a default."""
    if not entry or entry.get("kind") != "local_file":
        return None
    if entry.get("request_preset") == "airllm":
        return None
    path = entry.get("local_path")
    if not path:
        raise ValueError("Selected local model has no installed artifact")
    return local_contract(entry["stage_type"], path, entry.get("request_preset"))


def voice_entry(registry, actor):
    if not registry:
        return None
    entries = registry.list("voice")
    exact = next((entry for entry in entries if entry.get("id") == actor), None)
    if exact:
        return exact
    aliases = [entry for entry in entries if entry["display_name"] == actor]
    if len(aliases) > 1:
        raise ValueError("Voice name is ambiguous; select its unique model connection")
    return aliases[0] if aliases else None


def resolve_stt(registry, model_size, runtime=None):
    entry = registry.get_active("stt") if registry else None
    contract = _local(entry)
    if contract and contract['adapter'] == 'whisper_turbo':
        from core.providers.stt.whisper_turbo_local import WhisperTurboLocalProvider
        return WhisperTurboLocalProvider(entry['local_path'])
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.stt.cloud_rest import STTCloudRestProvider
        return STTCloudRestProvider(
            entry["api_base_url"], entry.get("credential_ref"), entry.get("request_preset") or "custom",
            extra=(entry.get("meta") or {}).get("stt_request")
        )
    from core.providers.stt.whisper_local import WhisperLocalProvider
    options = {'runtime': runtime} if runtime is not None else {}
    # faster-whisper's WhisperModel accepts either a named size ("medium",
    # "large-v3", auto-downloaded from Systran/faster-whisper-<size> on
    # first use) or a local CTranslate2 model directory - a Marketplace-
    # connected local_file STT entry's downloaded snapshot (a real
    # Systran/faster-whisper-* repo is already CT2-format) is exactly
    # that, so no separate loading code is needed - just pass its path
    # through in place of the settings-configured size string.
    if contract:
        return WhisperLocalProvider(model_size=entry["local_path"], **options)
    return WhisperLocalProvider(model_size=model_size, **options)


def resolve_translation(registry, ollama_host, runtime=None, fallback_runtime=None):
    entry = registry.get_active("translation") if registry else None
    contract = _local(entry)
    # AirLLM is opt-in only: it's just another translation entry in the
    # registry (source_url holds the HF model id, request_preset marks it
    # as "airllm" - see bridge/api.py's add_airllm_model()), never used
    # unless the user explicitly added one and set it active.
    if contract and contract['adapter'] == 'indictrans2':
        from core.providers.translation.indictrans2_local import IndicTrans2LocalProvider
        return IndicTrans2LocalProvider(entry['local_path'])
    if entry and entry.get("request_preset") == "airllm":
        from core.providers.translation.airllm_local import AirLLMTranslationProvider
        return AirLLMTranslationProvider(
            entry["source_url"], compression=(entry.get("meta") or {}).get("compression")
        )
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.translation.cloud_rest import TranslationCloudRestProvider
        return TranslationCloudRestProvider(
            entry["api_base_url"], entry.get("credential_ref"), entry.get("request_preset") or "openai_chat",
            extra=(entry.get("meta") or {}).get("translation_request"),
        )
    # A downloaded NLLB-200 repo (or any other AutoModelForSeq2SeqLM-shaped
    # local_file translation entry - marked this way since NLLB is the
    # only such recommended model today, see core/recommended_models.py)
    # loads through transformers directly rather than Ollama/M2M100.
    if contract:
        from core.providers.translation.nllb_local import NLLBLocalProvider
        return NLLBLocalProvider(entry["local_path"], **({'runtime': runtime} if runtime is not None else {}))
    from core.providers.translation.ollama_m2m100_local import OllamaM2M100LocalProvider
    return OllamaM2M100LocalProvider(ollama_host=ollama_host,
        **({'runtime':fallback_runtime} if fallback_runtime is not None else {}))


def resolve_tts(registry, device, runtime=None):
    entry = registry.get_active("tts") if registry else None
    contract = _local(entry)
    if contract and contract['adapter'] == 'indicf5':
        from core.providers.tts.indicf5_local import IndicF5TTSProvider
        return IndicF5TTSProvider(entry['local_path'],
            (entry.get('meta') or {}).get('reference_profile'),
            device=(entry.get('meta') or {}).get('speech_device') or device)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.tts.cloud_rest import TTSCloudRestProvider
        return TTSCloudRestProvider(
            entry["api_base_url"], entry.get("credential_ref"), entry.get("request_preset") or "custom",
            extra=(entry.get("meta") or {}).get("tts_request"),
            voice=(entry.get("meta") or {}).get("voice_id")
        )
    from core.providers.tts.xtts_local import XTTSLocalProvider
    options = {'runtime': runtime} if runtime is not None else {}
    # A downloaded coqui/XTTS-v2 (or compatible) repo is the same model
    # architecture as the bundled default, just a different checkpoint
    # directory - TTSHandler's model_path override loads it directly.
    if contract:
        return XTTSLocalProvider(device=device, model_path=entry["local_path"], **options)
    return XTTSLocalProvider(device=device, **options)


def resolve_voice_for_actor(registry, actor_name, device):
    """Voice is chosen per cast member (the Dashboard's per-render dropdown,
    or a node graph's cast list), not via a single global "active" model
    the way the other stages are - so this looks up the registry entry
    matching the actor's exact name instead of get_active("voice")."""
    entry = voice_entry(registry, actor_name)
    contract = _local(entry)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.voice.cloud_rest import VoiceCloudRestProvider
        return VoiceCloudRestProvider(
            entry["api_base_url"], entry.get("credential_ref"), entry.get("request_preset") or "custom",
            extra={**((entry.get("meta") or {}).get("voice_request") or {}),
                   **({"voice_id": entry["meta"]["voice_id"]} if (entry.get("meta") or {}).get("voice_id") else {})}
        )
    # F5-TTS is a real zero-shot cloning TTS, not an RVC-style audio-to-
    # audio converter - request_preset="f5tts" marks a voice entry as
    # this shape (same marker pattern AirLLM uses for translation - see
    # bridge/api.py's add_airllm_model()), so _dub_segment() routes it
    # through F5TTSVoiceProvider instead of RVC.
    if entry and entry.get("request_preset") == "f5tts":
        from core.providers.voice.f5tts_local import F5TTSVoiceProvider
        return F5TTSVoiceProvider(device=device, model_path=entry["local_path"])
    from core.providers.voice.rvc_local import RVCLocalProvider
    if contract:
        return RVCLocalProvider(device=device, model_path=contract["checkpoint_path"],
                                index_path=(entry.get("meta") or {}).get("index_path"),
                                version=contract["rvc_version"])
    return RVCLocalProvider(device=device)


def resolve_enhancer(registry, device, upscale, runtime="legacy"):
    entry = registry.get_active("enhancer") if registry else None
    contract = _local(entry)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.enhancer.cloud_rest import EnhancerCloudRestProvider
        return EnhancerCloudRestProvider(entry["api_base_url"], entry.get("credential_ref"), extra=(entry.get("meta") or {}).get("enhancer_request"))
    from core.providers.enhancer.gfpgan_local import GFPGANLocalProvider
    return GFPGANLocalProvider(device=device, upscale=upscale,
                               model_path=contract["checkpoint_path"] if contract else None, **({"runtime":runtime} if runtime!="legacy" else {}))


def resolve_filter(registry, device=None):
    entry = registry.get_active("filter") if registry else None
    contract = _local(entry)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.filter.cloud_rest import FilterCloudRestProvider
        return FilterCloudRestProvider(entry["api_base_url"], entry.get("credential_ref"), extra=(entry.get("meta") or {}).get("filter_request"))
    # Only a local_file entry explicitly marked "image_classifier" routes
    # here - a plain image classifier (whole-frame safe/unsafe, no
    # localization) is a fundamentally different shape from a real
    # detector like NudeNet or a vision-language model like Llama Guard
    # 3 Vision (still unwired - see recommended_models.py's note on why),
    # so this can't just be "any local_file filter entry" the way the
    # other resolve_*() functions treat their one supported local shape.
    if entry and entry["kind"] == "local_file" and entry.get("request_preset") == "image_classifier" and entry.get("local_path"):
        from core.providers.filter.vision_classifier_local import VisionClassifierLocalProvider
        return VisionClassifierLocalProvider(entry["local_path"], device=device)
    from core.providers.filter.nudenet_local import NudeNetLocalProvider
    return NudeNetLocalProvider()


def resolve_lipsync(registry, device=None):
    entry = registry.get_active("lipsync") if registry else None
    contract = _local(entry)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.lipsync.cloud_rest import LipSyncCloudRestProvider
        return LipSyncCloudRestProvider(entry["api_base_url"], entry.get("credential_ref"), extra=(entry.get("meta") or {}).get("lipsync_request"))
    if contract and contract["adapter"] == "wav2lip":
        from core.providers.lipsync.wav2lip_local import Wav2LipLocalProvider
        return Wav2LipLocalProvider(model_path=contract["checkpoint_path"], device=device)
    if contract:
        from core.providers.lipsync.musetalk_local import MuseTalkLocalProvider
        return MuseTalkLocalProvider(device=device, models_dir=entry["local_path"])
    from core.providers.lipsync.wav2lip_local import Wav2LipLocalProvider
    return Wav2LipLocalProvider(device=device)


def resolve_profanity_filter(registry, ollama_host="http://localhost:11434", device=None):
    """Only ever called when a profanity_filter model is active (see
    core/pipeline.py) - unlike the other resolve_*() functions, there's no
    "nothing installed" default here, since running this stage at all is
    itself opt-in."""
    entry = registry.get_active("profanity_filter") if registry else None
    contract = _local(entry)
    if entry and entry["kind"] in _CLOUD_KINDS:
        from core.providers.profanity_filter.cloud_rest import ProfanityFilterCloudRestProvider
        return ProfanityFilterCloudRestProvider(
            entry["api_base_url"], entry.get("credential_ref"), entry.get("request_preset") or "custom",
            extra=(entry.get("meta") or {}).get("profanity_filter_request")
        )
    # A downloaded sequence-classifier repo (e.g. a toxicity classifier)
    # can't rewrite text like an instructable LLM can - see
    # ClassifierProfanityFilterProvider's docstring for how it "censors"
    # instead. request_preset marks which kind of local_file this is,
    # same pattern AirLLM's translation entries use (see
    # bridge/api.py's add_airllm_model()); today the only local_file
    # profanity_filter recommendation is classifier-shaped, so it's the
    # default for this kind rather than requiring an explicit preset.
    if entry and entry["kind"] == "local_file" and entry.get("local_path"):
        from core.providers.profanity_filter.classifier_local import ClassifierProfanityFilterProvider
        return ClassifierProfanityFilterProvider(entry["local_path"], device=device)
    from core.providers.profanity_filter.ollama_local import OllamaProfanityFilterProvider
    return OllamaProfanityFilterProvider(ollama_host=ollama_host)
