"""AirLLM-backed local translation provider - runs a full HF model with
layer-by-layer disk offloading (https://github.com/lyogavin/airllm),
trading speed for the ability to run large (even 70B+) models on very low
VRAM/CPU hardware. This is deliberately just another Translation-stage
option, not a new top-level feature: it's selected the same way any other
model is, via core/model_registry.py. It is meaningfully slower than the
Ollama/M2M100 local provider since every layer streams from disk on every
forward pass - only worth choosing when nothing else fits in memory.
"""

from core.providers.base import TranslationProvider, require_translation_text
from core.languages import require_known_target
from core.source_language import coerce_source_language, source_prompt

_PROMPT_TEMPLATE = (
    "Translate the following text into {target_language}. "
    "Reply with ONLY the translated text, no notes or quotes.{instruction_line}\n\n{text}"
)


class AirLLMTranslationProvider(TranslationProvider):
    def __init__(self, hf_model_id, max_new_tokens=256, compression=None):
        self.hf_model_id = hf_model_id
        self.max_new_tokens = max_new_tokens
        self.compression = compression  # AirLLM's own optional quantization, e.g. "4bit"/"8bit"
        self._model = None  # lazy + cached: translate() is called once per
        # subtitle segment, and AutoModel.from_pretrained() does real setup
        # work (layer indexing, disk cache prep) that must happen once per
        # video, not once per segment - same reasoning as every other
        # lazy-cached provider in this package.

    def _load(self):
        from airllm import AutoModel

        kwargs = {"compression": self.compression} if self.compression else {}
        self._model = AutoModel.from_pretrained(self.hf_model_id, **kwargs)

    def translate(self, text, target_language, custom_instructions="", source_language=None):
        if not text.strip():
            return text
        require_known_target(target_language)
        source_language = coerce_source_language(source_language)
        if self._model is None:
            self._load()

        instruction_line = source_prompt(source_language)
        if custom_instructions and custom_instructions.strip():
            instruction_line += f" Additional instructions: {custom_instructions.strip()}"
        prompt = _PROMPT_TEMPLATE.format(target_language=target_language, text=text, instruction_line=instruction_line)
        input_tokens = self._model.tokenizer(
            [prompt],
            return_tensors="pt",
            return_attention_mask=False,
            truncation=True,
            max_length=2048,
            padding=False,
        )
        generation_output = self._model.generate(
            input_tokens["input_ids"],
            max_new_tokens=self.max_new_tokens,
            use_cache=True,
            return_dict_in_generate=True,
        )
        # Slice off the prompt tokens - callers want just the translation,
        # not the echoed instruction.
        prompt_len = input_tokens["input_ids"].shape[1]
        decoded = self._model.tokenizer.decode(
            generation_output.sequences[0][prompt_len:], skip_special_tokens=True
        )
        return require_translation_text(decoded)
