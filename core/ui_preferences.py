"""App-owned UI preferences; does not persist WebView cookies or credentials."""
import json
import os
import re
import config
from core.json_store import JsonStore, require

KEYS = {'reflow-theme', 'reflow-experience-level', 'reflow.accentColor',
        'reflow.helpTooltipsEnabled', 'reflow.tourComplete', 'reflow.renderConfig'}

def validate(data):
    require(isinstance(data, dict) and set(data) <= KEYS, 'Unknown UI preference')
    for key, value in data.items():
        require(isinstance(value, str) and len(value) <= 16384, 'Invalid UI preference value')
        if key == 'reflow-theme':
            require(value in ('dark', 'light'), 'Invalid theme')
        elif key == 'reflow-experience-level':
            require(value in ('basic', 'advanced', 'expert'), 'Invalid experience level')
        elif key == 'reflow.accentColor':
            require(re.fullmatch(r'#?[a-fA-F0-9]{6}', value) is not None, 'Invalid accent color')
        elif key in ('reflow.helpTooltipsEnabled', 'reflow.tourComplete'):
            require(value in ('true', 'false'), 'Invalid UI boolean')
        else:
            from core.languages import LANGUAGE_NAMES
            from core.source_language import SOURCE_LANGUAGE_NAMES
            cfg = json.loads(value)
            strings = {'template', 'lang', 'sourceLanguage', 'voice', 'refAudio'}
            booleans = {'keepBg', 'lipsync', 'enhance', 'burnSubs', 'contentFilter',
                        'includeSubtitles', 'exportStems'}
            ranges = {'taskPriority': (0, 100), 'qualityIdx': (0, 2),
                      'parallelWorkers': (1, 8), 'subtitleFontSize': (1, 200)}
            require(isinstance(cfg, dict) and set(cfg) <= strings | booleans | set(ranges), 'Invalid render preferences')
            for field, item in cfg.items():
                if field in booleans:
                    require(type(item) is bool, 'Invalid render boolean: ' + field)
                elif field in ranges:
                    low, high = ranges[field]
                    require(type(item) is int and low <= item <= high, 'Invalid render number: ' + field)
                elif field == 'refAudio' and item is None:
                    continue
                else:
                    require(isinstance(item, str) and bool(item.strip()) and len(item) <= 4096, 'Invalid render string: ' + field)
            if 'template' in cfg:
                require(cfg['template'] in ('video_dub', 'video_dub_lipsync', 'audio_dub', 'subtitle_translate'), 'Invalid template')
            if 'lang' in cfg:
                require(cfg['lang'] in {*LANGUAGE_NAMES, 'source'}, 'Invalid target language')
            if 'sourceLanguage' in cfg:
                require(cfg['sourceLanguage'] in {*SOURCE_LANGUAGE_NAMES, 'auto'}, 'Invalid source language')
    return data

class UIPreferences:
    _serializable = False

    def __init__(self, path=None, warning=None):
        self.store = JsonStore(path or os.path.join(config.BASE_DIR, 'ui_preferences.json'), {}, validate, warning)

    def all(self):
        return self.store.read()

    def update(self, partial):
        validate(partial)
        data, _ = self.store.mutate(lambda saved: saved.update(partial))
        return data
