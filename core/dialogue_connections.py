"""Explicit opt-in dialogue services, separate from the active translator."""
import hashlib
import ipaddress
import json
import os
from urllib.parse import urlsplit


def connection(entry, mode):
    if (not isinstance(entry, dict) or entry.get('stage_type') != 'translation'
            or entry.get('kind') not in ('local_api', 'cloud_api')
            or entry.get('request_preset') != 'openai_chat' or entry.get('status') != 'installed'):
        raise ValueError('Select an installed chat-compatible connection from Marketplace → Translation.')
    base = entry.get('api_base_url')
    if not isinstance(base, str):
        raise ValueError('Dialogue connection needs an endpoint.')
    parsed = urlsplit(base)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Use an HTTP(S) endpoint without embedded credentials, query or fragment.')
    parsed.port  # Validate malformed ports before saving or requesting.
    host = parsed.hostname.lower()
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host == 'localhost'
    if mode == 'local' and not local:
        raise ValueError('Local dialogue mode requires a loopback endpoint on this computer.')
    if not local and parsed.scheme != 'https':
        raise ValueError('Remote dialogue connections require HTTPS.')
    if not local and not entry.get('credential_ref'):
        raise ValueError('Remote dialogue connections require a stored credential reference.')
    extra = (entry.get('meta') or {}).get('translation_request') or {}
    model = extra.get('model') if isinstance(extra, dict) else None
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError('Specify an explicit model name in this connection; no default model is chosen.')
    return dict(id=entry['id'], label=entry['display_name'], endpoint=base.rstrip('/'),
        model=model.strip(), credential_ref=entry.get('credential_ref'), local=local)


def selected(values, registry):
    mode = values.get('dialogue_mode', 'off')
    if mode not in ('local', 'hybrid'):
        raise ValueError('Dialogue assistance is off.')
    entries = [registry.get(values.get('dialogue_'+role+'_id', '')) for role in ('writer', 'reviewer')]
    return tuple(connection(entry, mode) for entry in entries)


def fingerprint(values, registry):
    connections = selected(values, registry)
    payload = dict(mode=values['dialogue_mode'], connections=connections)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def readiness(values, registry):
    if values.get('dialogue_mode', 'off') == 'off':
        return dict(status='off', ready=False, message='Dialogue assistance is off. No assistance requests are made.')
    try:
        writer, reviewer = selected(values, registry)
        current = fingerprint(values, registry)
    except (ValueError, TypeError) as error:
        return dict(status='needs_connection', ready=False, message=str(error))
    if values['dialogue_mode'] == 'hybrid' and (
            values.get('dialogue_text_consent') is not True
            or values.get('dialogue_consent_fingerprint') != current):
        return dict(status='needs_consent', ready=False,
            message='Confirm sharing dialogue text with these selected connections. Provider changes require confirmation again.')
    if os.environ.get('REFLOW_OFFLINE') == '1' and not (writer['local'] and reviewer['local']):
        return dict(status='offline', ready=False, message='Offline mode blocks remote dialogue assistance.')
    # Configuration readiness does not contact or certify the service/model.
    return dict(status='configured', ready=True,
        message='Connections configured; service availability and dialogue quality have not been verified.',
        writer={k: writer[k] for k in ('label', 'endpoint', 'model', 'local')},
        reviewer={k: reviewer[k] for k in ('label', 'endpoint', 'model', 'local')})


def resolve(values, registry):
    status = readiness(values, registry)
    if not status['ready']:
        raise ValueError(status['message'])
    from core.providers.dialogue_chat import DialogueChatProvider
    return tuple(DialogueChatProvider(item) for item in selected(values, registry))
