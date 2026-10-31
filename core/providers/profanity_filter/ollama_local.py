"""Local profanity-filter provider - rewrites already-translated dialogue
through the same local Ollama LLM the default translation provider talks
to, prompted to censor/rewrite rather than translate. This is the only
architecturally honest "local" default available for this stage today:
unlike STT/TTS/Voice/Enhancer/Filter/Lipsync, profanity filtering that
*rewrites* text (not just scores it) needs an instructable model, and
Ollama is the one already-integrated local instructable engine in this
app (see core/llm_translator.py). Never used unless the user has
connected and activated a profanity_filter model in the Marketplace -
see core/providers/resolve.py.
"""

import requests

from core.providers.base import ProfanityFilterProvider

_DEFAULT_INSTRUCTION = (
    "You censor profanity and slurs in a line of dialogue while preserving "
    "its meaning, tone, and language. Reply with ONLY the rewritten line, "
    "no notes or quotes."
)


class OllamaProfanityFilterProvider(ProfanityFilterProvider):
    def __init__(self, ollama_host="http://localhost:11434", ollama_model="llama3"):
        self.ollama_host = ollama_host
        self.ollama_model = ollama_model

    def filter_text(self, text, custom_instructions=""):
        from core.network_policy import require_network_allowed
        require_network_allowed(self.ollama_host)
        if not text or not text.strip():
            return text

        instruction = _DEFAULT_INSTRUCTION
        if custom_instructions and custom_instructions.strip():
            instruction += f" Additional instructions: {custom_instructions.strip()}"

        prompt = f"{instruction}\n\nLine: {text}\nRewritten:"
        try:
            resp = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model, "prompt": prompt, "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=30,
            )
            if resp.status_code == 200:
                out = resp.json().get("response", "").strip()
                if not out:
                    raise RuntimeError("Ollama profanity filter returned empty text")
                return out
        except requests.exceptions.RequestException as error:
            raise RuntimeError(f"Ollama profanity filtering failed: {error}") from error
        raise RuntimeError(f"Ollama profanity filtering returned HTTP {resp.status_code}")
