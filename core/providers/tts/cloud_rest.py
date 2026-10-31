"""Generic cloud REST TTS provider - one adapter class configured with an
API base URL, a stored credential (see core/credential_store.py), and a
named "request preset" describing how to shape the request/response for
a given vendor. "Any possible TTS model" realistically means "point at an
HTTP endpoint with an API key," not hand-integrating every vendor SDK - a
couple of well-known presets cover the common services, and "custom"
covers anything else via a user-supplied JSON body template.
"""

from core.providers.base import TTSProvider
from core.providers.cloud_rest_common import request, resolve_credential
from core.http_media import write_media
from core.audio_utils import load_speech_audio


def _openai_tts_request(base_url, api_key, text, language, voice, extra):
    url = f"{base_url}/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "model": extra.get("model", "tts-1"),
        "voice": voice or extra.get("voice", "alloy"),
        "input": text,
    }
    return request("POST", url, headers=headers, json_body=body)


def _elevenlabs_tts_request(base_url, api_key, text, language, voice, extra):
    voice_id = voice or extra.get("voice_id")
    if not voice_id:
        raise ValueError("ElevenLabs TTS requires a voice_id (set it as the model's 'voice').")
    url = f"{base_url}/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key}
    body = {"text": text, "model_id": extra.get("model_id", "eleven_multilingual_v2")}
    return request("POST", url, headers=headers, json_body=body)


def _custom_request(base_url, api_key, text, language, voice, extra):
    path = extra.get("path", "/")
    url = f"{base_url}{path}"
    headers = {}
    if api_key:
        auth_header = extra.get("auth_header", "Authorization")
        auth_prefix = extra.get("auth_prefix", "Bearer ")
        headers[auth_header] = f"{auth_prefix}{api_key}"
    body_template = extra.get("body", {"text": "{text}", "language": "{language}", "voice": "{voice}"})
    body = _fill_template(body_template, text=text, language=language, voice=voice or "")
    return request("POST", url, headers=headers, json_body=body)


def _fill_template(template, **values):
    if isinstance(template, str):
        return template.format(**values)
    if isinstance(template, dict):
        return {k: _fill_template(v, **values) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill_template(v, **values) for v in template]
    return template


TTS_PRESETS = {
    "openai_tts": _openai_tts_request,
    "elevenlabs_tts": _elevenlabs_tts_request,
    "custom": _custom_request,
}


class TTSCloudRestProvider(TTSProvider):
    def __init__(self, api_base_url, credential_ref, request_preset="custom", voice=None, extra=None):
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.request_preset = request_preset
        self.voice = voice
        self.extra = extra or {}

    def synthesize(self, text, output_path, language="en", reference_audio=None):
        build_request = TTS_PRESETS.get(self.request_preset)
        if build_request is None:
            raise ValueError(f"Unknown TTS request preset: {self.request_preset}")

        # Credential is optional - a self-hosted "Local Service" model (no
        # API key, added via the Marketplace's Local Service flow) has no
        # credential_ref at all.
        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        resp = build_request(self.api_base_url, api_key, text, language, self.voice, self.extra)

        return write_media(resp, output_path, {'audio'}, validate_output=load_speech_audio)
