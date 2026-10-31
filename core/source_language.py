"""Source selection and fixed-vocabulary translation policy; no text guessing."""

from dataclasses import dataclass
import math

from core.languages import LANGUAGE_NAMES, M2M100_LANG_MAP, NLLB_LANG_MAP

AUTO_SOURCE_MIN_CONFIDENCE = 0.80
SOURCE_LANGUAGE_NAMES = {**LANGUAGE_NAMES,
                         "zh-Hans": "Mandarin Chinese (Simplified)",
                         "zh-Hant": "Mandarin Chinese (Traditional)",
                         "pa": "Punjabi (script unspecified)",
                         "pa-Guru": "Punjabi (Gurmukhi)"}
_ALIASES = {value.casefold(): code for code, name in SOURCE_LANGUAGE_NAMES.items()
            for value in (code, name)}
_ALIASES.update({"chinese": "zh", "punjabi": "pa", "arabic": "ar"})
_ALIASES.update({token.casefold(): code for code, name in LANGUAGE_NAMES.items()
                 if code != "zh" for token in [NLLB_LANG_MAP.get(name)] if token})
_ALIASES.update({"zho_hans": "zh-Hans", "zho_hant": "zh-Hant", "pan_guru": "pa-Guru"})

# Separate source maps: never infer a script from an ambiguous language label.
M2M100_SOURCE_MAP = {code: M2M100_LANG_MAP[name] for code, name in LANGUAGE_NAMES.items()
                     if name in M2M100_LANG_MAP}
M2M100_SOURCE_MAP.update({"zh-Hans": "zh", "zh-Hant": "zh", "pa-Guru": "pa"})
NLLB_SOURCE_MAP = {code: NLLB_LANG_MAP[name] for code, name in LANGUAGE_NAMES.items()
                   if name in NLLB_LANG_MAP and code != "zh"}
NLLB_SOURCE_MAP.update({"zh-Hans": "zho_Hans", "zh-Hant": "zho_Hant", "pa-Guru": "pan_Guru"})


def _valid_probability(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and 0 <= value <= 1 and math.isfinite(value))


@dataclass(frozen=True)
class SourceLanguage:
    code: str = None
    origin: str = "unknown"
    probability: float = None
    detected_label: str = None

    def __post_init__(self):
        if self.code is not None and self.code not in SOURCE_LANGUAGE_NAMES:
            raise ValueError(f"Unknown source language code: {self.code}")
        if self.origin not in ("manual", "detected", "unknown"):
            raise ValueError("Invalid source language origin.")
        if self.origin == "manual" and self.code is None:
            raise ValueError("Manual source selection requires a language.")
        if self.origin == "unknown" and self.code is not None:
            raise ValueError("Unknown source origin cannot specify a language.")
        if self.probability is not None and not _valid_probability(self.probability):
            raise ValueError("Invalid source language confidence.")

    @property
    def resolved(self):
        return self.code is not None and (self.origin == "manual" or
               (self.origin == "detected" and self.probability is not None
                and self.probability >= AUTO_SOURCE_MIN_CONFIDENCE))


def normalize_source_selection(selection="auto"):
    if selection is None:
        return "auto"
    if not isinstance(selection, str) or not selection.strip():
        raise ValueError("Source language must be 'auto' or a supported source code/name.")
    selection = selection.strip().casefold()
    if selection == "auto":
        return "auto"
    code = _ALIASES.get(selection)
    if code is None:
        raise ValueError(f"Unknown manual source language: {selection}")
    return code


def resolve_source_language(selection="auto", detected_language=None, probability=None):
    selected = normalize_source_selection(selection)
    if selected != "auto":
        return SourceLanguage(selected, "manual")
    label = detected_language.strip() if isinstance(detected_language, str) else None
    return SourceLanguage(_ALIASES.get(label.casefold()) if label else None,
                          "detected" if label else "unknown",
                          probability if _valid_probability(probability) else None, label)


def coerce_source_language(value=None):
    """Direct provider calls may pass a manual code/name or resolved context."""
    return value if isinstance(value, SourceLanguage) else resolve_source_language(value)


def require_fixed_source(engine, sources, source_language=None):
    source = coerce_source_language(source_language)
    if not source.resolved:
        raise ValueError(
            f"{engine} requires a resolved source language. Select it manually, or use "
            f"automatic detection with confidence >= {AUTO_SOURCE_MIN_CONFIDENCE:.2f}; "
            f"detected={source.detected_label!r}, confidence={source.probability!r}."
        )
    if source.code not in sources:
        raise ValueError(f"{engine} has no exact source mapping for '{source.code}'. "
                         "Select a supported language/script or another translation provider.")
    return sources[source.code]


def source_prompt(source_language=None):
    source = coerce_source_language(source_language)
    if source.resolved:
        return f" Source language: {SOURCE_LANGUAGE_NAMES[source.code]}."
    return " Infer the source language from the text."
