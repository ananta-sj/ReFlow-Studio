"""Generic cloud REST translation provider - same base_url + credential +
preset pattern as the other cloud_rest adapters. The "openai_chat" preset
targets the OpenAI chat-completions request/response shape, which is also
what most local inference servers (LM Studio, text-generation-webui,
Ollama's /v1 endpoint) mimic - so this one preset covers a wide range of
actual deployments, cloud or local, not just OpenAI itself.
"""

from string import Formatter
from core.languages import require_known_target
from core.source_language import coerce_source_language, source_prompt, SOURCE_LANGUAGE_NAMES
from core.providers.base import TranslationProvider, require_translation_text
from core.providers.cloud_rest_common import request, resolve_credential

_TRANSLATE_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into "
    "{target_language}. Reply with ONLY the translated text, no notes or quotes."
)


def _openai_chat_request(base_url, api_key, text, target_language, extra, custom_instructions="", source_language=None):
    require_known_target(target_language)
    url = f"{base_url}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    system_prompt = _TRANSLATE_SYSTEM_PROMPT.format(target_language=target_language)
    system_prompt += source_prompt(source_language)
    if custom_instructions and custom_instructions.strip():
        system_prompt += f" Additional instructions: {custom_instructions.strip()}"
    body = {
        "model": extra.get("model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": extra.get("temperature", 0.3),
    }
    resp = request("POST", url, headers=headers, json_body=body, timeout=(5, 120))
    try:
        payload = resp.json()
        value = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Translation endpoint returned an invalid chat response.") from exc
    return require_translation_text(value)


def _custom_request(base_url, api_key, text, target_language, extra, custom_instructions="", source_language=None):
    require_known_target(target_language)
    source = coerce_source_language(source_language)
    source_code = source.code if source.resolved else ""
    source_name = SOURCE_LANGUAGE_NAMES[source_code] if source_code else ""
    path = extra.get("path", "/translate")
    url = f"{base_url}{path}"
    auth_header = extra.get("auth_header", "Authorization")
    auth_prefix = extra.get("auth_prefix", "Bearer ")
    headers = {auth_header: f"{auth_prefix}{api_key}"} if api_key else {}
    body_template = extra.get("body", {"text": "{text}", "target_language": "{target_language}"})
    instruction_keys = []
    source_keys = []
    if source_code:
        source_keys = [key for key, value in body_template.items() if isinstance(value, str)
                       if any(field in ("source_language", "source_language_name")
                              for _, field, _, _ in Formatter().parse(value))]
        if not source_keys:
            raise ValueError("Custom translation request cannot transmit the resolved source language: "
                             "add {source_language} or {source_language_name} to a string value "
                             "in the request body template.")
        for key in source_keys:
            for _, field, format_spec, conversion in Formatter().parse(body_template[key]):
                if field in ("source_language", "source_language_name") and (format_spec or conversion):
                    raise ValueError("Custom source language placeholders must be unmodified; "
                                     "remove formatting/conversion that may discard or truncate the source language.")
    if custom_instructions and custom_instructions.strip():
        instruction_keys = [key for key, value in body_template.items() if isinstance(value, str)
                            if any(field == "custom_instructions" for _, field, _, _ in Formatter().parse(value))]
        if not instruction_keys:
            raise ValueError("Custom translation request cannot transmit custom instructions: "
                             "add {custom_instructions} to a string value in the request body template "
                             "or clear the instructions.")
    body = {
        k: (v.format(text=text, target_language=target_language, custom_instructions=custom_instructions or "",
                     source_language=source_code, source_language_name=source_name)
            if isinstance(v, str) else v)
        for k, v in body_template.items()
    }
    if source_code and not any(
        source_code in body[key] or source_name in body[key] for key in source_keys
    ):
        raise ValueError("Custom translation request template discarded or truncated the source language.")
    if custom_instructions and custom_instructions.strip() and not any(
        custom_instructions in body[key] for key in instruction_keys
    ):
        raise ValueError("Custom translation request must transmit the full custom instructions; "
                         "the request template discarded or truncated them.")
    resp = request("POST", url, headers=headers, json_body=body, timeout=(5, 120))
    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError("Translation endpoint returned invalid JSON.") from exc
    response_field = extra.get("response_field", "text")
    if isinstance(payload, dict):
        if response_field not in payload:
            raise RuntimeError(f"Translation response is missing field '{response_field}'.")
        payload = payload[response_field]
    return require_translation_text(payload)


TRANSLATION_PRESETS = {
    "openai_chat": _openai_chat_request,
    "custom": _custom_request,
}


class TranslationCloudRestProvider(TranslationProvider):
    def __init__(self, api_base_url, credential_ref=None, request_preset="openai_chat", extra=None):
        if extra is not None and not isinstance(extra, dict):
            raise ValueError("Translation request configuration must be a dictionary.")
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.request_preset = request_preset
        self.extra = extra or {}

    def translate(self, text, target_language, custom_instructions="", source_language=None):
        if not text.strip():
            return text
        source_language = coerce_source_language(source_language)
        build_request = TRANSLATION_PRESETS.get(self.request_preset)
        if build_request is None:
            raise ValueError(f"Unknown translation request preset: {self.request_preset}")

        # Credential is optional here (unlike TTS/STT) - a local server
        # like Ollama's /v1 shim usually needs no key at all.
        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        return require_translation_text(build_request(self.api_base_url, api_key, text, target_language,
                                                      self.extra, custom_instructions, source_language))
