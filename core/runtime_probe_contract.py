"""Shared, fixed dependency-probe routes; no dynamic module names from the UI."""
ROUTES = {
    'demucs': (90, ('cpu', 'cuda:0')),
    'faster_whisper': (45, ('cpu',)),
    'nllb': (120, ('cpu',)),
    'm2m100': (120, ('cpu',)),
    'whisper_turbo': (45, ('cuda:0',)),
    'indictrans2': (45, ('cuda:0',)),
    'indicf5': (90, ('cpu', 'cuda:0')),
    'f5tts': (90, ('cpu', 'cuda:0')),
    'musetalk': (90, ('cpu', 'cuda:0')),
    'nudenet': (45, ('cpu',)),
    'rvc': (90, ('cpu', 'cuda:0')),
    'gfpgan': (90, ('cpu', 'cuda:0')),
    'wav2lip': (60, ('cpu', 'cuda:0')),
    'image_classifier': (60, ('cpu', 'cuda:0')),
    'text_classifier': (60, ('cpu', 'cuda:0')),
}


def require_route(adapter, device):
    if not isinstance(adapter, str) or adapter not in ROUTES or device not in ROUTES[adapter][1]:
        raise ValueError('Unsupported runtime probe route')
    return ROUTES[adapter][0]
