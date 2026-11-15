"""Prepare XTTS speech text and preserve short cues within checkpoint limits."""
import re
import unicodedata


_HINDI_SMALL = (
    'शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस '
    'बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस '
    'तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस '
    'चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास '
    'पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ '
    'साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर '
    'सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उनासी '
    'अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सतासी अट्ठासी नवासी '
    'नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे'
).split()
_HINDI_SCALES = ((10**11, 'खरब'), (10**9, 'अरब'), (10**7, 'करोड़'),
                 (10**5, 'लाख'), (1000, 'हजार'), (100, 'सौ'))
_NUMBER = re.compile(
    r'(?<!\w)-?(?:\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{2})*,\d{3}|\d+)(?:\.\d+)?'
    r'|\d+(?:\.\d+)?'
)


def _hindi_integer(digits):
    if len(digits) > 15 or (len(digits) > 1 and digits.startswith('0')):
        return ' '.join(_HINDI_SMALL[int(digit)] for digit in digits)
    number = int(digits)
    if number < 100:
        return _HINDI_SMALL[number]
    for scale, name in _HINDI_SCALES:
        if number >= scale:
            quotient, remainder = divmod(number, scale)
            result = _hindi_integer(str(quotient)) + ' ' + name
            return result + (' ' + _hindi_integer(str(remainder)) if remainder else '')


def prepare_speech_text(text, language):
    """Expand Hindi digits before Coqui's unsupported Hindi number converter."""
    if language != 'hi':
        return text
    text = ''.join(str(unicodedata.decimal(char)) if char.isdecimal() else char for char in text)

    def expand(match):
        raw = match.group().replace(',', '')
        negative = raw.startswith('-')
        whole, dot, fraction = raw.lstrip('-').partition('.')
        spoken = _hindi_integer(whole)
        if dot:
            spoken += ' दशमलव ' + ' '.join(_HINDI_SMALL[int(digit)] for digit in fraction)
        return ('ऋण ' if negative else '') + spoken

    return _NUMBER.sub(expand, text)

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
