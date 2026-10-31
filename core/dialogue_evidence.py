"""Bind advisory meaning opinions to exact supplied text, never certify meaning."""
from copy import deepcopy
import unicodedata

PROTOCOL = 'quoted-spans.v1'
LEGACY = 'legacy-reasons.v1'


def _word(char):
    return bool(char) and (unicodedata.category(char)[0] in ('L', 'M', 'N') or char in '_\u200c\u200d')


def _contains(text, quote):
    start = text.find(quote)
    while start != -1:
        end = start + len(quote)
        if not (_word(quote[0]) and start and _word(text[start-1])
                or _word(quote[-1]) and end < len(text) and _word(text[end])):
            return True
        start = text.find(quote, start+1)
    return False


def validate_evidence(status, evidence, source, candidate):
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 3:
        raise ValueError('Meaning review requires one to three source/candidate evidence pairs.')
    seen, relations = set(), set()
    for pair in evidence:
        if not isinstance(pair, dict) or set(pair) != {'source_quote', 'candidate_quote', 'relation'}:
            raise ValueError('Invalid meaning evidence pair.')
        left, right, relation = pair['source_quote'], pair['candidate_quote'], pair['relation']
        if (not isinstance(left, str) or not isinstance(right, str) or len(left) > 240 or len(right) > 240
                or relation not in ('equivalent', 'changed', 'omitted', 'added', 'uncertain')):
            raise ValueError('Invalid meaning evidence text or relation.')
        if (left and (not left.strip() or not _contains(source, left))) or (right and (not right.strip() or not _contains(candidate, right))):
            raise ValueError('Meaning evidence quotes text absent from the supplied source or candidate.')
        if (relation == 'omitted' and (not left or right)
                or relation == 'added' and (left or not right)
                or relation not in ('omitted', 'added') and (not left or not right)):
            raise ValueError('Meaning evidence has no valid counterpart for its relation.')
        key = (left, right, relation)
        if key in seen:
            raise ValueError('Duplicate meaning evidence pair.')
        seen.add(key)
        relations.add(relation)
    if (status == 'preserved' and relations != {'equivalent'}
            or status == 'changed' and not relations.intersection({'changed', 'omitted', 'added'})
            or status == 'uncertain' and 'uncertain' not in relations
            or status not in ('preserved', 'changed', 'uncertain')):
        raise ValueError('Meaning status contradicts its cited evidence relations.')
    return deepcopy(evidence)
