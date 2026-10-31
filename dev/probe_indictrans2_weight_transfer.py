"""Probe first bytes with a fresh redirect; never record signed URLs or tokens."""
import json
import os
from pathlib import Path
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')
from huggingface_hub import get_token

report = {}
try:
    response = requests.get('https://huggingface.co/ai4bharat/indictrans2-en-indic-1B/resolve/'
                            '89cd0007fd7b9e0693a2fd4404d187e07dac79fd/model.safetensors',
        params={'download':'true', 'transfer_probe':str(time.time_ns())},
        headers={'Authorization':'Bearer '+get_token(), 'Cache-Control':'no-cache'},
        allow_redirects=False, timeout=(10,20))
    report['resolve_status'] = response.status_code
    response.raise_for_status()
    location = response.headers.get('Location')
    assert location and location.startswith('https://'), 'No HTTPS redirect'
    with requests.get(location, headers={'Range':'bytes=0-1023'}, stream=True, timeout=(10,20)) as stream:
        report.update(transfer_status=stream.status_code, content_length=stream.headers.get('Content-Length'),
                      content_range=stream.headers.get('Content-Range'))
        stream.raise_for_status()
        chunk = next(stream.iter_content(1024))
        report['first_bytes_received'] = len(chunk)
        report['nonzero_bytes'] = sum(value != 0 for value in chunk)
except Exception as exc:
    report['error_type'] = type(exc).__name__
finally:
    (ROOT / 'docs/validation/2026-10-08-indictrans2-weight-transfer-probe.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
