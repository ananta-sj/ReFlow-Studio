"""Generic cloud REST STT provider - same base_url + credential + preset
pattern as core/providers/tts/cloud_rest.py, shaped for audio-in /
segments-out instead of text-in / audio-out. See that file for the
overall design rationale.
"""

from core.providers.base import STTProvider
from core.transcription import normalize_transcription
from core.providers.cloud_rest_common import request, resolve_credential


def _openai_whisper_request(base_url, api_key, audio_path, extra):
    url = f"{base_url}/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": extra.get("model", "whisper-1"), "response_format": "verbose_json"}
    if extra.get('_source_language'):
        data['language'] = extra['_source_language']
    with open(audio_path, "rb") as f:
        files = {"file": (audio_path, f, "application/octet-stream")}
        resp = request("POST", url, headers=headers, data=data, files=files)
    payload = resp.json()
    return normalize_transcription(payload)


def _custom_request(base_url, api_key, audio_path, extra):
    """Accepts a legacy segment list or a segments envelope with optional
    language/language_probability metadata. Provider language labels are
    retained as supplied; source-language resolution is a separate step."""
    path = extra.get("path", "/transcribe")
    url = f"{base_url}{path}"
    auth_header = extra.get("auth_header", "Authorization")
    auth_prefix = extra.get("auth_prefix", "Bearer ")
    headers = {auth_header: f"{auth_prefix}{api_key}"} if api_key else {}
    kwargs = {}
    if extra.get('_source_language'):
        field = extra.get('language_field')
        if not isinstance(field, str) or not field.strip():
            raise ValueError('Custom recognition requires a configured language_field to transmit an explicit source language; configure it or select automatic recognition.')
        kwargs['data'] = {field: extra['_source_language']}
    with open(audio_path, "rb") as f:
        files = {"file": (audio_path, f, "application/octet-stream")}
        resp = request("POST", url, headers=headers, files=files, **kwargs)
    payload = resp.json()
    return normalize_transcription(payload)


STT_PRESETS = {
    "openai_whisper": _openai_whisper_request,
    "custom": _custom_request,
}


class STTCloudRestProvider(STTProvider):
    def __init__(self, api_base_url, credential_ref, request_preset="custom", extra=None):
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.request_preset = request_preset
        self.extra = extra or {}

    def transcribe(self, audio_path, source_language='auto'):
        from core.source_language import normalize_source_selection
        selected = normalize_source_selection(source_language)
        build_request = STT_PRESETS.get(self.request_preset)
        if build_request is None:
            raise ValueError(f"Unknown STT request preset: {self.request_preset}")

        extra = dict(self.extra)
        # Internal request metadata cannot be supplied through saved extras.
        extra.pop('_source_language', None)
        if selected != 'auto':
            extra['_source_language'] = {'zh-Hans': 'zh', 'zh-Hant': 'zh', 'pa-Guru': 'pa'}.get(selected, selected)
        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        result = build_request(self.api_base_url, api_key, audio_path, extra)
        if selected != 'auto':
            from core.transcription import TranscriptionResult
            result = TranscriptionResult(list(result), extra['_source_language'], language_origin='hint')
        return result
