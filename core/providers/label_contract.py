"""Exact binary moderation labels; negative names cannot match substrings."""
import re


def positive_index(labels, positive, negative):
    normalized = {int(index): re.sub(r'[\s-]+', '_', str(name).strip().lower())
                  for index, name in labels.items()}
    if len(normalized) != 2 or set(normalized) != {0, 1}:
        raise ValueError('Expected an explicitly labeled two-class classifier')
    matches = [index for index, name in normalized.items() if name in positive]
    others = [index for index, name in normalized.items() if name in negative]
    if len(matches) != 1 or len(others) != 1:
        raise ValueError(f'Unsupported or ambiguous moderation labels: {normalized}')
    return matches[0]
