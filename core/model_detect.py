"""Best-effort model-type detection for the Marketplace's "just paste a
link" flow - inspects a URL (and, for Hugging Face links, the HF API's own
model metadata) to guess which pipeline stage a model belongs to, so the
user doesn't have to already know the answer before adding it.

Detection is inherently a guess, never a certainty - callers (bridge/api.py,
the Marketplace UI) must treat the result as a suggestion to confirm or
override, never as something to silently commit to the registry.
"""

import re

import requests

from core.model_registry import STAGE_TYPES

# Hugging Face's own pipeline_tag is the most reliable signal available -
# it's metadata the model author declared, not a guess from a filename.
_HF_PIPELINE_TAG_MAP = {
    "automatic-speech-recognition": "stt",
    "translation": "translation",
    "text-to-speech": "tts",
    "audio-to-audio": "voice",
    "voice-activity-detection": "stt",
    "image-to-image": "enhancer",
    "image-classification": "filter",
}

# Fallback for non-HF links, or HF links whose pipeline_tag isn't one of
# the above (or the HF API call fails) - keyword match against known
# engine/architecture names. Ordered roughly most->least specific.
#
# Real filenames separate words with underscores/hyphens far more often
# than spaces (e.g. "my_custom_RVC_model.zip") - regex \b treats "_" as a
# word character, so \brvc\b never matches "_RVC_". _kw() below defines
# the boundary as "not a letter" instead, so underscore/hyphen/digit all
# count as valid separators.
def _kw(word):
    return re.compile(rf"(?<![a-zA-Z]){word}(?![a-zA-Z])", re.I)


_KEYWORD_PATTERNS = [
    (re.compile(r"whisper|faster-whisper|wav2vec|speech-to-text", re.I), "stt"),
    (_kw("asr"), "stt"),
    (re.compile(r"m2m100|nllb|opus-mt|marian|translat", re.I), "translation"),
    (re.compile(r"xtts|tortoise-tts|text-to-speech|coqui|bark|piper", re.I), "tts"),
    (_kw("tts"), "tts"),
    (re.compile(r"so-vits|voice-clone|voice-conversion|retrieval-based-voice", re.I), "voice"),
    (_kw("rvc"), "voice"),
    (re.compile(r"gfpgan|codeformer|real-?esrgan|face-?restor|face-?enhanc", re.I), "enhancer"),
    (re.compile(r"nudenet|nsfw|content-?filter|nudity", re.I), "filter"),
    (re.compile(r"wav2lip|lip-?sync|musetalk|liveportrait|talking-?head|talking-?face", re.I), "lipsync"),
    (re.compile(r"toxic|profanity|hate-?speech|moderation", re.I), "profanity_filter"),
]

_HF_REPO_RE = re.compile(r"huggingface\.co/([^/\s]+/[^/\s?#]+)")

# Known API hosts -> a starting guess. Weak signal on purpose: one host
# (e.g. api.openai.com) can genuinely serve multiple stage types, so this
# is only ever "low" confidence.
_API_HOST_HINTS = [
    (re.compile(r"elevenlabs", re.I), "tts", "ElevenLabs (also offers voice conversion - confirm the stage)"),
    (re.compile(r"openai\.com", re.I), "tts", "OpenAI-compatible host (also offers STT/chat - confirm the stage)"),
    (re.compile(r"ollama|:11434", re.I), "translation", "Ollama-style local LLM host"),
    (re.compile(r"replicate\.com", re.I), "enhancer", "Replicate (hosts many task types - confirm the stage)"),
]


def _keyword_match(text: str):
    for pattern, stage_type in _KEYWORD_PATTERNS:
        if pattern.search(text):
            return {"stage_type": stage_type, "confidence": "low", "reason": f"matched '{pattern.pattern}' in the link"}
    return {"stage_type": None, "confidence": "low", "reason": "no match"}


def detect_from_url(url: str) -> dict:
    """For a local-download source URL. Returns
    {"stage_type": str|None, "confidence": "high"|"low", "reason": str}."""
    repo_match = _HF_REPO_RE.search(url)
    if repo_match:
        repo_id = repo_match.group(1)
        try:
            from core.network_policy import require_network_allowed
            require_network_allowed('https://huggingface.co')
            resp = requests.get(f"https://huggingface.co/api/models/{repo_id}", timeout=6)
            if resp.ok:
                tag = resp.json().get("pipeline_tag")
                if tag in _HF_PIPELINE_TAG_MAP:
                    return {
                        "stage_type": _HF_PIPELINE_TAG_MAP[tag],
                        "confidence": "high",
                        "reason": f"Hugging Face pipeline_tag: {tag}",
                    }
        except (requests.RequestException, RuntimeError):
            pass  # offline / blocked - fall through to the keyword guess below

    return _keyword_match(url)


def detect_from_api_base_url(api_base_url: str) -> dict:
    """For a cloud/local-API base URL - inherently weaker than the HF path
    (see _API_HOST_HINTS), so this never returns "high" confidence."""
    for pattern, stage_type, reason in _API_HOST_HINTS:
        if pattern.search(api_base_url):
            return {"stage_type": stage_type, "confidence": "low", "reason": reason}
    return {"stage_type": None, "confidence": "low", "reason": "unrecognized host"}


assert set(_HF_PIPELINE_TAG_MAP.values()) <= set(STAGE_TYPES)
assert set(t for _, t in _KEYWORD_PATTERNS) <= set(STAGE_TYPES)
assert set(t for _, t, _ in _API_HOST_HINTS) <= set(STAGE_TYPES)

# Inverse of _HF_PIPELINE_TAG_MAP, for ranking rather than classifying:
# given a stage_type, which HF pipeline_tag(s) should be searched to find
# the best candidate for it.
_STAGE_TO_HF_TAGS = {
    "stt": ["automatic-speech-recognition"],
    "translation": ["translation"],
    "tts": ["text-to-speech"],
    "voice": ["audio-to-audio"],
    "enhancer": ["image-to-image"],
    "filter": ["image-classification"],
    "lipsync": ["video-to-video"],
    "profanity_filter": ["text-classification"],
}


def find_best_hf_model(stage_type: str, limit: int = 3) -> list[dict]:
    """Ranks catalog models with implemented adapters by usage (downloads),
    without treating a matching task tag as execution compatibility.
    Returns up to `limit` candidates, most
    downloaded first: [{"repo_id", "url", "downloads", "likes"}, ...].
    Empty list on network failure or an unrecognized stage_type - callers
    should treat that as "no automatic pick available", not an error."""
    from core.recommended_models import RECOMMENDED_MODELS
    from core.network_policy import require_network_allowed
    repositories = [item['source_url'].removeprefix('https://huggingface.co/')
                    for item in RECOMMENDED_MODELS.get(stage_type, [])
                    if item['kind'] == 'local_file' and item.get('source_url', '').startswith('https://huggingface.co/')]
    results = []
    for repo_id in repositories:
        try:
            require_network_allowed('https://huggingface.co')
            resp = requests.get(
                f"https://huggingface.co/api/models/{repo_id}",
                timeout=10,
            )
            if resp.ok:
                entry = resp.json()
                results.append({
                    "repo_id": repo_id,
                    "url": f"https://huggingface.co/{repo_id}",
                    "downloads": entry.get("downloads", 0),
                    "likes": entry.get("likes", 0),
                })
        except (requests.RequestException, RuntimeError, ValueError, TypeError, AttributeError):
            pass  # offline / blocked - fall through with whatever we already have

    results.sort(key=lambda r: r["downloads"], reverse=True)
    return results[:limit]
