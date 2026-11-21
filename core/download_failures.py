"""Bounded public download failures; never forward provider exception text."""
from typing import TypedDict
import errno
import requests


class DownloadFailure(TypedDict):
    code: str
    message: str


class DownloadTransportUnavailable(RuntimeError):
    pass


MESSAGES = {
    'missing_transport': 'Repository downloads need the desktop Hub download client. Update the desktop setup, then retry.',
    'access_denied': 'Repository access was denied. Check model access and your local sign-in before retrying.',
    'network_error': 'The transfer could not reach the server. Check the connection and retry.',
    'storage_error': 'The transfer could not write its files. Check free space and folder permissions before retrying.',
    'transfer_failed': 'The model transfer did not finish. Retained files are preserved; retry or review the local diagnostics.',
}


class DownloadTransferFailure(RuntimeError):
    def __init__(self, code):
        self.code = code if isinstance(code, str) and code in MESSAGES else 'transfer_failed'
        super().__init__(MESSAGES[self.code])


def describe_download_failure(error: BaseException) -> DownloadFailure:
    code = 'transfer_failed'
    if isinstance(error, DownloadTransferFailure):
        code = error.code
    elif isinstance(error, DownloadTransportUnavailable):
        code = 'missing_transport'
    elif getattr(getattr(error, 'response', None), 'status_code', None) in (401, 403):
        code = 'access_denied'
    elif isinstance(error, (requests.ConnectionError, requests.Timeout, TimeoutError)):
        code = 'network_error'
    elif isinstance(error, PermissionError) or isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EDQUOT, errno.EACCES):
        code = 'storage_error'
    if code == 'transfer_failed':
        # Hub uses an optional HTTP client; avoid importing it for direct URLs.
        if type(error).__module__.split('.')[0] in ('httpx', 'httpx2'):
            if 'Timeout' in type(error).__name__ or type(error).__name__ in ('ConnectError', 'NetworkError', 'ReadError', 'WriteError'):
                code = 'network_error'
    return {'code': code, 'message': MESSAGES[code]}
