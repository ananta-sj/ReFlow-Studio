"""Provider-independent screening for runaway dialogue, not semantic rewriting."""
import re
import unicodedata


class DialogueIntegrityReviewRequired(RuntimeError):
    pass


def require_explicit_facts(source, output, source_language, target_language):
    """High-confidence English/Hindi alarms; never a general meaning approval.

    These source anchors do not supply replacement dialogue or infer identities.
    Restrict the kinship check to 'we/us ... his father': reflexive 'his father'
    with a singular male subject can correctly become 'अपने पिता'.
    """
    if getattr(source_language,'code',source_language)!='en' or target_language not in ('hi','Hindi'):
        return output
    folded=unicodedata.normalize('NFKC',source).casefold()
    target=unicodedata.normalize('NFKC',output).casefold()
    for word,alternatives in {'north':('उत्तर','नॉर्थ','north'),
                              'south':('दक्षिण','साउथ','south'),
                              'east':('पूर्व','ईस्ट','east'),
                              'west':('पश्चिम','वेस्ट','west')}.items():
        if re.search(r'\b'+word+r'\s+of\b',folded) and not any(term in target for term in alternatives):
            raise DialogueIntegrityReviewRequired('Translation omitted an explicit geographic direction; review required')
    if re.search(r'\b(?:we|us)\b[^.!?]*\bhis father\b',folded) and re.search(r'(?:^|\s)हम\s+[^।.!?]*अपने\s+(?:पिता|पापा|फादर)',target):
        raise DialogueIntegrityReviewRequired('Translation may have changed whose father is being discussed; review required')
    return output


def words(text):
    return ''.join(c.casefold() if unicodedata.category(c)[0] in 'LMN' else ' '
                   for c in unicodedata.normalize('NFKC', text)).split()


def repetition(text):
    tokens = words(text)
    # Short malformed words can evade a word-count screen (e.g. seven
    # repeated Hindi consonants, with optional combining marks).
    for token in tokens:
        letters = ''.join(c for c in token if unicodedata.category(c)[0] in 'LN')
        for width in range(1, min(4, len(letters)//6)+1):
            if re.search(r'(.{%d})\1{5,}' % width, letters):
                return True
    if len(tokens) < 6 or len(text) < 48:
        return False
    for width in range(1, min(8, len(tokens)//6)+1):
        for start in range(len(tokens)-width*6+1):
            pattern = tokens[start:start+width]
            end = start+width
            while tokens[end:end+width] == pattern:
                end += width
            if (end-start)//width >= 6 and end-start >= .60*len(tokens):
                return True
    return False


def require_reasonable(source, output):
    if not isinstance(output, str) or not output.strip():
        raise DialogueIntegrityReviewRequired('Translation produced no spoken dialogue')
    if len(output) > 12000:
        raise DialogueIntegrityReviewRequired('Translation exceeded the safe dialogue text window')
    if repetition(output) and not repetition(source):
        raise DialogueIntegrityReviewRequired('Translation contains runaway repeated words or phrases')
    source_letters = sum(unicodedata.category(c)[0] in 'LMN' for c in source)
    target_letters = sum(unicodedata.category(c)[0] in 'LMN' for c in output)
    if target_letters > max(240, 12*source_letters):
        raise DialogueIntegrityReviewRequired('Translation expanded far beyond the source; review required')
    return output


def recovery_parts(source):
    # Preserve source order and wording. One bounded retry using existing
    # natural phrase boundaries, without a model download or invented text.
    separators = r'[\n,，、;；。！？!?]+'
    if re.search(r'[\u3040-\u30ff]', source):
        separators += r'|\s+'
    parts = [part.strip() for part in re.split(separators, source) if part.strip()]
    return parts if 2 <= len(parts) <= 6 and all(len(part) <= 240 for part in parts) else []


def require_speech_window(text, seconds):
    if len(words(text)) > max(40, seconds*8) or len(text) > max(200, seconds*50):
        raise DialogueIntegrityReviewRequired('Dialogue text is implausibly long for its source speech window')
