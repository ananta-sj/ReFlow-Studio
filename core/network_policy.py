"""Offline permits local services and cached files, and rejects remote requests."""
import ipaddress
import os
from urllib.parse import urlsplit


def require_network_allowed(url):
    if os.environ.get('REFLOW_OFFLINE') != '1':
        return
    host = urlsplit(url).hostname or ''
    if host.lower() == 'localhost':
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise RuntimeError('Offline mode: remote network requests are disabled')
