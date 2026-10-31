"""Python -> JS push channel, replacing PyQt signals.

`webview.windows[0].evaluate_js()` is thread-safe to call from a background
thread - pywebview marshals it onto the GUI thread internally - which is
what lets a worker thread push live progress/log/telemetry events into the
page the same way PipelineWorker's Qt signals used to.
"""

import json

import webview


def emit(event_name, payload):
    """Dispatch `payload` into the page as `window.__reflow.dispatch(event_name, payload)`.
    The frontend's lib/events.ts defines that function and fans the event out
    to whichever React components are subscribed."""
    if not webview.windows:
        return
    js = f"window.__reflow && window.__reflow.dispatch({json.dumps(event_name)}, {json.dumps(payload)})"
    webview.windows[0].evaluate_js(js)
