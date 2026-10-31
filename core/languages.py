"""Shared language names and exact fixed-vocabulary translation targets.

The language menu is a product list, not a guarantee for every provider.
Prompt-based LLM coverage depends on the selected model and is unverified.
Fixed-vocabulary providers must reject missing targets, never substitute a
related language or script. Source-language policy is in core/source_language.py.
"""

LANGUAGES = [
    ("en", "English"),
    ("zh", "Mandarin Chinese"),
    ("hi", "Hindi"),
    ("hi-en", "Hinglish"),
    ("es", "Spanish"),
    ("ar", "Standard Arabic"),
    ("fr", "French"),
    ("bn", "Bengali"),
    ("ja", "Japanese"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("id", "Indonesian"),
    ("de", "German"),
    ("pcm", "Nigerian Pidgin"),
    ("ko", "Korean"),
    ("ta", "Tamil"),
    ("kn", "Kannada"),
    ("pnb", "Western Punjabi"),
    ("tr", "Turkish"),
    ("vi", "Vietnamese"),
    ("mr", "Marathi"),
    ("te", "Telugu"),
    ("jv", "Javanese"),
    ("it", "Italian"),
]

# code -> display name - what pipeline.py needs to turn a Dashboard/wizard
# selection (a short code) into the human-readable name every translation
# provider's prompt actually uses.
LANGUAGE_NAMES = dict(LANGUAGES)

# Exact M2M100 targets only; omitted languages are unsupported.
M2M100_LANG_MAP = {
    "English": "en", "Mandarin Chinese": "zh", "Hindi": "hi",
    "Spanish": "es", "Standard Arabic": "ar", "French": "fr", "Bengali": "bn",
    "Japanese": "ja", "Portuguese": "pt", "Russian": "ru", "Indonesian": "id",
    "German": "de",
    "Korean": "ko", "Tamil": "ta", "Kannada": "kn",
    "Turkish": "tr", "Vietnamese": "vi", "Marathi": "mr",
    "Javanese": "jv", "Italian": "it",
}

# Exact NLLB targets only. Hinglish, Nigerian Pidgin, and Western Punjabi
# have no exact tokens in the installed NLLB vocabulary; never approximate.
NLLB_LANG_MAP = {
    "English": "eng_Latn", "Mandarin Chinese": "zho_Hans", "Hindi": "hin_Deva",
    "Spanish": "spa_Latn", "Standard Arabic": "arb_Arab", "French": "fra_Latn",
    "Bengali": "ben_Beng",
    "Japanese": "jpn_Jpan", "Portuguese": "por_Latn", "Russian": "rus_Cyrl",
    "Indonesian": "ind_Latn",
    "German": "deu_Latn",
    "Korean": "kor_Hang", "Tamil": "tam_Taml", "Kannada": "kan_Knda",
    "Turkish": "tur_Latn", "Vietnamese": "vie_Latn", "Marathi": "mar_Deva",
    "Telugu": "tel_Telu",
    "Javanese": "jav_Latn", "Italian": "ita_Latn",
}

assert set(M2M100_LANG_MAP) <= set(LANGUAGE_NAMES.values())
assert set(NLLB_LANG_MAP) <= set(LANGUAGE_NAMES.values())


def require_known_target(target_language):
    if target_language not in LANGUAGE_NAMES.values():
        raise ValueError(f"Unknown translation target language: {target_language}")


def require_fixed_translation(engine, targets, target_language, custom_instructions=""):
    """Validate before model loading, tokenization, or fallback side effects."""
    require_known_target(target_language)
    if target_language not in targets:
        raise ValueError(
            f"{engine} does not support an exact target for '{target_language}'. "
            "Select another translation provider; language substitution is disabled."
        )
    if custom_instructions and custom_instructions.strip():
        raise ValueError(
            f"{engine} cannot accept custom translation instructions. "
            "Clear the instructions or select a prompt-based translation provider."
        )
    return targets[target_language]
