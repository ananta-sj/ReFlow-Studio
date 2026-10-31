"""Generic cloud REST voice-conversion provider - audio in, re-voiced
audio out. Same base_url + credential + preset pattern as the other
cloud_rest adapters (see core/providers/tts/cloud_rest.py).
"""

from core.providers.base import VoiceProvider
from core.providers.cloud_rest_common import request, resolve_credential
from core.http_media import write_media
from core.audio_utils import load_speech_audio


def _elevenlabs_sts_request(base_url, api_key, input_audio, model_name, extra):
    voice_id = extra.get("voice_id")
    if not voice_id:
        raise ValueError("ElevenLabs speech-to-speech requires a configured service voice_id; display names are not service IDs.")
    url = f"{base_url}/v1/speech-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key}
    data = {"model_id": extra.get("model_id", "eleven_multilingual_sts_v2")}
    with open(input_audio, "rb") as f:
        files = {"audio": (input_audio, f, "application/octet-stream")}
        return request("POST", url, headers=headers, data=data, files=files)


def _custom_request(base_url, api_key, input_audio, model_name, extra):
    path = extra.get("path", "/convert")
    url = f"{base_url}{path}"
    auth_header = extra.get("auth_header", "Authorization")
    auth_prefix = extra.get("auth_prefix", "Bearer ")
    headers = {auth_header: f"{auth_prefix}{api_key}"} if api_key else {}
    data = {"model_name": model_name}
    with open(input_audio, "rb") as f:
        files = {"file": (input_audio, f, "application/octet-stream")}
        return request("POST", url, headers=headers, data=data, files=files)


VOICE_PRESETS = {
    "elevenlabs_sts": _elevenlabs_sts_request,
    "custom": _custom_request,
}


class VoiceCloudRestProvider(VoiceProvider):
    def __init__(self, api_base_url, credential_ref, request_preset="custom", extra=None):
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.request_preset = request_preset
        self.extra = extra or {}

    def convert(self, input_audio, output_audio, model_name, pitch_change=0, text=None, reference_audio=None):
        build_request = VOICE_PRESETS.get(self.request_preset)
        if build_request is None:
            raise ValueError(f"Unknown voice request preset: {self.request_preset}")

        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        resp = build_request(self.api_base_url, api_key, input_audio, model_name, self.extra)

        return write_media(resp, output_audio, {'audio'}, validate_output=load_speech_audio)
