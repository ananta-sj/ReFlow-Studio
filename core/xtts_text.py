"""Preserve short XTTS cue context within the selected checkpoint's limits."""

# Retain only the language routes that improved in the paired default-checkpoint
# speech/ASR controls. Other languages keep their established delivery. This is
# a generation policy, not a declaration of model language support.
SHORT_CONTEXT_LANGUAGES = frozenset({'de', 'fr', 'hu', 'ko', 'pl', 'pt', 'tr'})


def should_split_sentences(text, language, model):
    # In particular, keep the reviewed Hindi recipe and the rejected Czech
    # candidate intact; do not generalize an improvement across all languages.
    if language not in SHORT_CONTEXT_LANGUAGES:
        return True
    tokenizer = getattr(model, 'tokenizer', None)
    limits = getattr(tokenizer, 'char_limits', None)
    token_limit = getattr(getattr(model, 'args', None), 'gpt_max_text_tokens', None)
    base_language = language.split('-')[0]
    char_limit = limits.get(base_language) if isinstance(limits, dict) else None
    if type(token_limit) is not int or token_limit <= 1 or type(char_limit) is not int or char_limit <= 0:
        return True
    normalized = text.strip().lower()
    if len(normalized) > char_limit:
        return True
    # Match XTTS's actual inference preprocessing, including its language-aware
    # number/script normalization. Character count alone cannot bound tokens.
    tokens = tokenizer.encode(normalized, lang=base_language)
    if not isinstance(tokens, (list, tuple)) or not tokens or any(type(token) is not int or token < 0 for token in tokens):
        raise ValueError('XTTS tokenizer returned invalid speech tokens')
    # Preserve context only for short cues. Longer text keeps the established
    # splitting route; the checkpoint's stricter limit always takes precedence.
    return len(tokens) >= min(128, token_limit)
