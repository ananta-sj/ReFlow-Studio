"""Translate an explicit source selection to a Whisper language token.

Script selections guide the language only; Whisper does not guarantee the
requested Chinese/Punjabi writing system. Each worker validates its own model.
"""
from core.source_language import normalize_source_selection


def whisper_language(selection='auto'):
    selected = normalize_source_selection(selection)
    if selected == 'auto':
        return None
    return {'zh-Hans': 'zh', 'zh-Hant': 'zh', 'pa-Guru': 'pa',
            'jv': 'jw'}.get(selected, selected)
