"""Python -> JS push channel, replacing PyQt signals.

`webview.windows[0].evaluate_js()` is thread-safe to call from a background
thread - pywebview marshals it onto the GUI thread internally - which is
what lets a worker thread push live progress/log/telemetry events into the
page the same way PipelineWorker's Qt signals used to.
"""

import json
from collections import deque
import logging
from pathlib import Path
import threading
import time
import uuid

import webview

_logs = deque(maxlen=1000)
_lock = threading.RLock()
_session = uuid.uuid4().hex
_sequence = 0
_loaded = False


def _log_path():
    import config
    return Path(config.OUTPUT_PATH) / 'application-log.jsonl'


def recent_logs():
    global _loaded
    with _lock:
        if not _loaded:
            _loaded = True
            try:
                with _log_path().open('rb') as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell()-1024*1024))
                    lines = stream.read().decode('utf-8', errors='replace').splitlines()
                restored = []
                for line in lines:
                    try:
                        item = json.loads(line)
                        if isinstance(item.get('id'), str) and isinstance(item.get('message'), str):
                            restored.append(item)
                    except (ValueError, TypeError, AttributeError):
                        continue
                _logs.extend(restored[-1000:])
            except OSError:
                pass
        return list(_logs)


def install_logging():
    class LiveLogHandler(logging.Handler):
        def emit(self, record):
            if record.name != 'root' and not record.name.startswith('core.'):
                return
            level = 'error' if record.levelno >= logging.ERROR else 'warning' if record.levelno >= logging.WARNING else 'info'
            emit('log', dict(level=level, message=record.getMessage()))
    handler = LiveLogHandler()
    root = logging.getLogger()
    if root.getEffectiveLevel() > logging.INFO:
        root.setLevel(logging.INFO)
    root.addHandler(handler)
    return handler


def emit(event_name, payload):
    """Dispatch `payload` into the page as `window.__reflow.dispatch(event_name, payload)`.
    The frontend's lib/events.ts defines that function and fans the event out
    to whichever React components are subscribed."""
    global _sequence
    if event_name == 'log':
        with _lock:
            recent_logs()
            _sequence += 1
            payload = dict(payload, id=f'{_session}-{_sequence}', time_ms=time.time()*1000)
            _logs.append(payload)
            try:
                path = _log_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.stat().st_size > 5*1024*1024:
                    path.replace(path.with_suffix('.previous.jsonl'))
                with path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(payload, ensure_ascii=False) + '\n')
            except OSError:
                pass
    if not webview.windows:
        return
    js = f"window.__reflow && window.__reflow.dispatch({json.dumps(event_name)}, {json.dumps(payload)})"
    try:
        webview.windows[0].evaluate_js(js)
    except Exception:
        # Reloading or closing the page must not fail a running render. The
        # authoritative job snapshot and logs are available for reconnect.
        pass
