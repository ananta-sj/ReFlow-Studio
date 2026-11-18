"""Shared HTTP plumbing for the generic per-stage cloud-REST providers.

Each stage's cloud_rest.py stays stage-shaped (STT uploads audio and gets
back segments, TTS posts text and gets back audio bytes, etc - genuinely
different I/O), but they all share the same "base URL + stored credential
+ named preset" request pattern. That one piece is identical across all
of them, so it lives here instead of being copy-pasted six times.
"""

import time

import requests
from urllib.parse import urljoin, urlsplit

from core.credential_store import get_credential
from core.render_context import check_cancelled, wait_or_cancel


class CloudRestError(RuntimeError):
    pass


def resolve_credential(credential_ref):
    """Looks up a stored API key by reference name. A configured cloud
    model with no resolvable credential is a configuration error, not a
    silent no-op - callers should see exactly why the request can't go
    out."""
    if not credential_ref:
        raise CloudRestError("No credential_ref configured for this cloud model.")
    api_key = get_credential(credential_ref)
    if not api_key:
        raise CloudRestError(
            f"No stored credential found for '{credential_ref}'. "
            "Add the API key for this model in the Marketplace before using it."
        )
    return api_key


def _origin(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise CloudRestError('Expected an HTTP(S) URL without embedded credentials')
        port = parsed.port
        return parsed.scheme, parsed.hostname.lower(), port if port is not None else (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        raise CloudRestError('Invalid HTTP(S) service URL') from None


def _joined_url(base, target):
    try:
        return urljoin(base, target)
    except ValueError:
        raise CloudRestError('Remote service returned an invalid URL') from None


def read_json(response):
    """Consume and close JSON without echoing upstream read/decoder details."""
    try:
        return response.json()
    except (ValueError, requests.RequestException):
        raise CloudRestError('Remote service response could not be read as JSON.') from None
    finally:
        response.close()


def iter_response(response, chunk_size):
    """Keep ownership with the caller and sanitize only transport failures."""
    try:
        yield from response.iter_content(chunk_size=chunk_size)
    except requests.RequestException:
        raise CloudRestError('Remote response transfer failed; check the service connection.') from None


def asset_headers(service_url, asset_url, headers):
    """Allow signed foreign-origin assets without forwarding service secrets."""
    service, asset = _origin(service_url), _origin(asset_url)
    if service[0] == 'https' and asset[0] != 'https':
        raise CloudRestError('Refusing HTTPS-to-HTTP asset downgrade')
    return dict(headers or {}) if service == asset else {}


def request(method, url, headers=None, json_body=None, data=None, files=None, timeout=120):
    from core.network_policy import require_network_allowed
    _origin(url)
    require_network_allowed(url)
    check_cancelled()
    if files:
        from core.http_media import MultipartBody
        data = MultipartBody(data, files)
        headers = {**(headers or {}), 'Content-Type': data.content_type}
        files = None
    request_timeout = timeout if isinstance(timeout, tuple) else (min(15, timeout), timeout)
    resp = None
    try:
        for redirect in range(6):
            resp = requests.request(
                method, url, headers=headers, json=json_body, data=data, files=files,
                timeout=request_timeout, allow_redirects=False, stream=True,
            )
            if resp.status_code not in (301, 302, 303, 307, 308):
                resp.raise_for_status()
                break
            location = resp.headers.get('Location')
            resp.close()
            if method.upper() != 'GET' or not location or redirect == 5:
                raise CloudRestError('Unsupported service redirect; configure the final endpoint URL')
            next_url = _joined_url(url, location)
            headers = asset_headers(url, next_url, headers)
            require_network_allowed(next_url)
            url = next_url
            check_cancelled()
    except requests.RequestException:
        if resp is not None:
            resp.close()
        status = getattr(resp, 'status_code', None)
        detail = f" (HTTP {status})" if isinstance(status, int) and 400 <= status <= 599 else ""
        raise CloudRestError(f"{method} request failed{detail}; check the service endpoint, connection or credentials.") from None
    try:
        check_cancelled()
    except BaseException:
        if resp is not None:
            resp.close()
        raise
    return resp


def poll_until_done(status_url, headers, done_field, done_value, result_field, poll_interval=3, timeout=1800, service_url=None):
    """Polls a job-status endpoint (the common shape for async video-processing
    APIs - submit a job, poll until it's finished, then fetch the result) until
    `payload[done_field] == done_value`, then returns `payload[result_field]`
    (typically a download URL). Raises on timeout rather than looping forever."""
    deadline = time.monotonic() + timeout
    if service_url:
        status_url = _joined_url(service_url + '/', status_url)
        if _origin(status_url) != _origin(service_url):
            raise CloudRestError('Polling URL must share the configured service origin')
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        resp = request("GET", status_url, headers=headers, timeout=max(.001, min(120, remaining)))
        payload = read_json(resp)
        if not isinstance(payload, dict):
            raise CloudRestError('Remote job status must be a JSON object')
        if payload.get(done_field) == done_value:
            result = payload.get(result_field)
            if not isinstance(result, str) or not result.strip():
                raise CloudRestError('Completed remote job has no usable result URL')
            return _joined_url(service_url + '/', result) if service_url else result
        if payload.get(done_field) in ("failed", "error"):
            raise CloudRestError("Remote job failed; check the service status without sharing private response data.")
        wait_or_cancel(min(poll_interval, max(0, deadline - time.monotonic())))
    raise CloudRestError(f"Timed out after {timeout}s waiting for the remote job.")
