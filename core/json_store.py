"""Small, cooperating-process JSON transactions; no cross-store transaction."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import logging
import os
import tempfile
import threading
import time

from filelock import FileLock

_locks = {}
_locks_guard = threading.Lock()


def _reject_constant(value):
    raise ValueError('Non-finite JSON number: ' + value)


def atomic_bytes(path, content):
    """Publish complete bytes, leaving the old file intact on pre-replace failure."""
    fd, temporary = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.',
                                     suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                if os.name != 'nt' or getattr(error, 'winerror', None) not in (5, 32) or attempt == 3:
                    raise
                time.sleep(.05 * (2 ** attempt))
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class JsonStore:
    _serializable = False

    def __init__(self, path, default, validate, warning=None):
        self.path = os.path.realpath(os.path.abspath(path))
        self.default = default
        self.validate = validate
        self.warning = warning
        self._reported = set()
        self._file_lock = FileLock(self.path + '.lock', timeout=30)
        with _locks_guard:
            self._lock = _locks.setdefault(os.path.normcase(self.path), threading.RLock())

    @contextmanager
    def locked(self):
        # Always thread lock first, then process lock. Lock files are retained:
        # deleting one can split the lock domain while another process uses it.
        with self._lock:
            with self._file_lock:
                yield

    def _read(self):
        try:
            with open(self.path, 'rb') as stream:
                raw = stream.read()
        except FileNotFoundError:
            return deepcopy(self.default)
        try:
            data = json.loads(raw.decode('utf-8'), parse_constant=_reject_constant)
            json.dumps(data, allow_nan=False)  # Also rejects overflow such as 1e999.
            return self.validate(data)
        except (UnicodeError, ValueError, TypeError) as error:
            digest = hashlib.sha256(raw).hexdigest()
            backup = self.path + '.corrupt-' + digest + '.bak'
            try:
                with open(backup, 'rb') as stream:
                    if stream.read() != raw:
                        raise OSError('Recovery copy has unexpected contents: ' + backup)
            except FileNotFoundError:
                atomic_bytes(backup, raw)
            message = f'Invalid saved state {self.path}: {error}. Preserved recovery copy: {backup}; using defaults.'
            if digest not in self._reported:
                logging.getLogger(__name__).warning(message)
                if self.warning:
                    try:
                        self.warning(message)
                    except Exception:
                        logging.getLogger(__name__).exception('Could not deliver persistence warning')
                self._reported.add(digest)
            return deepcopy(self.default)

    def read(self):
        with self.locked():
            return deepcopy(self._read())

    def mutate(self, change):
        with self.locked():
            candidate = deepcopy(self._read())
            result = change(candidate)
            candidate = self.validate(candidate)
            encoded = json.dumps(candidate, ensure_ascii=False, allow_nan=False,
                                 indent=2).encode('utf-8')
            atomic_bytes(self.path, encoded)
            return deepcopy(candidate), deepcopy(result)

    def replace(self, candidate):
        with self.locked():
            candidate = self.validate(deepcopy(candidate))
            encoded = json.dumps(candidate, ensure_ascii=False, allow_nan=False,
                                 indent=2).encode('utf-8')
            self._read()  # Preserve corrupt prior bytes before replacement.
            atomic_bytes(self.path, encoded)
            return deepcopy(candidate)

    def clear(self):
        with self.locked():
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass


def require(condition, message):
    if not condition:
        raise ValueError(message)
