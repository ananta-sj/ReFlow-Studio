"""Generic cloud REST profanity-filter provider - same base_url + credential
+ preset pattern as the other cloud_rest adapters. "openai_chat" targets
the OpenAI-compatible chat-completions shape (also what most local
inference servers mimic); "custom" covers anything else via a
user-supplied endpoint/body template, same as every other stage's custom
preset.
"""

from core.providers.base import ProfanityFilterProvider
from core.providers.cloud_rest_common import request, resolve_credential

_SYSTEM_PROMPT = (
    "You censor profanity and slurs in a line of dialogue while preserving "
    "its meaning, tone, and language. Reply with ONLY the rewritten line, "
    "no notes or quotes."
)


def _openai_chat_request(base_url, api_key, text, extra, custom_instructions=""):
    url = f"{base_url}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    system_prompt = _SYSTEM_PROMPT
    if custom_instructions and custom_instructions.strip():
        system_prompt += f" Additional instructions: {custom_instructions.strip()}"
    body = {
        "model": extra.get("model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": extra.get("temperature", 0.2),
    }
    resp = request("POST", url, headers=headers, json_body=body)
    payload = resp.json()
    return payload["choices"][0]["message"]["content"].strip()


def _custom_request(base_url, api_key, text, extra, custom_instructions=""):
    path = extra.get("path", "/moderate")
    url = f"{base_url}{path}"
    auth_header = extra.get("auth_header", "Authorization")
    auth_prefix = extra.get("auth_prefix", "Bearer ")
    headers = {auth_header: f"{auth_prefix}{api_key}"} if api_key else {}
    body_template = extra.get("body", {"text": "{text}"})
    body = {
        k: (v.format(text=text, custom_instructions=custom_instructions or "") if isinstance(v, str) else v)
        for k, v in body_template.items()
    }
    resp = request("POST", url, headers=headers, json_body=body)
    payload = resp.json()
    response_field = extra.get("response_field", "text")
    return payload[response_field].strip() if isinstance(payload, dict) else str(payload).strip()


PROFANITY_FILTER_PRESETS = {
    "openai_chat": _openai_chat_request,
    "custom": _custom_request,
}


class ProfanityFilterCloudRestProvider(ProfanityFilterProvider):
    def __init__(self, api_base_url, credential_ref=None, request_preset="custom", extra=None):
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.request_preset = request_preset
        self.extra = extra or {}

    def filter_text(self, text, custom_instructions=""):
        if not text or not text.strip():
            return text
        build_request = PROFANITY_FILTER_PRESETS.get(self.request_preset, _custom_request)
        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        return build_request(self.api_base_url, api_key, text, self.extra, custom_instructions)
