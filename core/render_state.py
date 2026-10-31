"""Tracks whether a render is currently in progress, persisted to disk so
the record survives a crash or force-kill - not just a clean finish/stop.
Used by bridge/api.py to offer resuming an interrupted render the next
time the app launches (see get_interrupted()).

A file that still exists on boot means the app didn't shut down cleanly
last time during a render: a normal finish, an explicit Stop, or the
render erroring out on its own all clear it via bridge/api.py's
_run_render()/stop_render() - only the process itself dying mid-render
(crash, force-kill, power loss) leaves it behind. Resume re-runs the same job, reusing verified recognition and translation
checkpoints for supported selected local engines. Other stages run again;
partial translations and generated speech are not resumed.
"""

import os
import time
import math
import hashlib
import json
from core.json_store import JsonStore, require

import config

STATE_PATH = os.path.join(config.BASE_DIR, "render_state.json")


def _validate(state):
    require(isinstance(state, dict), 'Render record must be an object')
    require(isinstance(state.get('input_path'), str) and bool(state['input_path'].strip()), 'Invalid render input')
    require(isinstance(state.get('params'), dict), 'Invalid render parameters')
    require(state.get('queue_item_id') is None or isinstance(state['queue_item_id'], str) and bool(state['queue_item_id']), 'Invalid recovery queue ID')
    require(state.get('template_id') in ('video_dub', 'video_dub_lipsync', 'audio_dub', 'subtitle_translate'), 'Invalid render template')
    started = state.get('started_at')
    require(type(started) in (int, float) and math.isfinite(started) and started >= 0, 'Invalid render timestamp')
    return state


def _store(warning=None):
    return JsonStore(STATE_PATH, None, _validate, warning)


def mark_started(input_path, params, template_id, warning=None, queue_item_id=None):
    state = {
            "input_path": input_path,
            "params": params,
            "template_id": template_id,
            "started_at": time.time(),
        }
    if queue_item_id is not None:
        state['queue_item_id'] = queue_item_id
    _store(warning).replace(state)


def clear():
    _store().clear()


def get_interrupted(warning=None):
    """Reading an offer never consumes it; acknowledge only an explicit discard."""
    store = _store(warning)
    with store.locked():
        state = store.read()
        if state is None:
            return None
        return {**state, 'recovery_token': _token(state)}


def _token(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, allow_nan=False,
                                    ensure_ascii=False).encode('utf-8')).hexdigest()


def discard(token):
    """A stale dialog cannot delete the marker belonging to a newer render."""
    store = _store()
    with store.locked():
        state = store.read()
        if state is None:
            return True
        if not isinstance(token, str) or token != _token(state):
            return False
        store.clear()
        return True
