"""Batch Render Queue Manager - enqueues multiple render jobs, manages job states,
and coordinates automatic batch execution.
"""

import uuid
import time
import threading
import math
from copy import deepcopy
from functools import wraps
from core.json_store import JsonStore, require


def validate_snapshot(data):
    require(isinstance(data, dict) and set(data) == {'version', 'items', 'paused'}, 'Invalid queue snapshot')
    require(data['version'] == 1 and type(data['version']) is int, 'Unknown queue version')
    require(type(data['paused']) is bool and isinstance(data['items'], list), 'Invalid queue state')
    ids = set()
    fields = {'id', 'input_path', 'params', 'template_id', 'status', 'progress', 'status_text', 'output_path', 'error', 'created_at'}
    for item in data['items']:
        require(isinstance(item, dict) and set(item) == fields, 'Invalid queue item')
        require(isinstance(item['id'], str) and bool(item['id']) and item['id'] not in ids, 'Duplicate or invalid queue ID')
        ids.add(item['id'])
        require(isinstance(item['input_path'], str) and bool(item['input_path'].strip()), 'Invalid queue input')
        require(item['template_id'] in ('video_dub', 'video_dub_lipsync', 'audio_dub', 'subtitle_translate'), 'Invalid queue template')
        require(item['status'] in ('draft', 'queued', 'processing', 'completed', 'failed', 'cancelled'), 'Invalid queue status')
        require(item['params'] is None if item['status'] == 'draft' else isinstance(item['params'], dict), 'Invalid accepted parameters')
        require(type(item['progress']) in (int, float) and math.isfinite(item['progress']) and 0 <= item['progress'] <= 100, 'Invalid queue progress')
        require(type(item['created_at']) in (int, float) and math.isfinite(item['created_at']) and item['created_at'] >= 0, 'Invalid queue timestamp')
        require(isinstance(item['status_text'], str), 'Invalid queue message')
        require(all(item[key] is None or isinstance(item[key], str) for key in ('output_path', 'error')), 'Invalid queue result')
    require(sum(item['status'] == 'processing' for item in data['items']) <= 1, 'Multiple active queue items')
    return data


def durable(method):
    """Commit an outer mutation before acknowledging it; rollback on failed writes."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            outer = self._mutation_depth == 0
            before = deepcopy((self._items, self._paused)) if outer else None
            self._mutation_depth += 1
            try:
                result = method(self, *args, **kwargs)
                persistent_change = method.__name__ != 'update_item' or bool(set(kwargs) - {'progress', 'status_text'})
                if outer and self._store and persistent_change and before != (self._items, self._paused):
                    self._store.replace({'version': 1, 'items': self.get_items(), 'paused': self._paused})
                return result
            except Exception as exc:
                if outer:
                    self._items, self._paused = before
                    if self._warning:
                        try:
                            self._warning('Queue change was not saved; previous queue retained: ' + str(exc))
                        except Exception:
                            pass
                raise
            finally:
                self._mutation_depth -= 1
    return call


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call

class QueueItem:
    def __init__(self, input_path, params, template_id="video_dub", item_id=None):
        self.id = item_id or str(uuid.uuid4())
        self.input_path = input_path
        self.params = deepcopy(params)
        self.template_id = template_id
        self.status = "draft" if params is None else "queued"
        self.progress = 0
        self.status_text = "Enqueued"
        self.output_path = None
        self.error = None
        self.created_at = time.time()

    def to_dict(self):
        return deepcopy({
            "id": self.id,
            "input_path": self.input_path,
            "params": self.params,
            "template_id": self.template_id,
            "status": self.status,
            "progress": self.progress,
            "status_text": self.status_text,
            "output_path": self.output_path,
            "error": self.error,
            "created_at": self.created_at,
        })

class QueueManager:
    # pywebview must expose the coordinated bridge endpoints, not internal
    # checkpoint/claim methods through its recursive object discovery.
    _serializable = False

    def __init__(self, path=None, warning=None):
        self._lock = threading.RLock()
        self._items = []
        self._paused = False
        self._mutation_depth = 0
        self._warning = warning
        self._store = JsonStore(path, {'version': 1, 'items': [], 'paused': False}, validate_snapshot, warning) if path else None
        if self._store:
            saved = self._store.read()
            for record in saved['items']:
                item = QueueItem(record['input_path'], record['params'], record['template_id'], record['id'])
                item.__dict__.update(deepcopy(record))
                if item.status == 'processing':
                    item.status, item.progress = 'queued', 0
                    item.status_text = 'Interrupted; ready to restart'
                self._items.append(item)
            # Loading never starts work. Accepted jobs remain frozen and need
            # explicit Resume; drafts still require batch acceptance.
            self._paused = saved['paused'] or any(item.status in ('draft', 'queued') for item in self._items)

    @durable
    def add_item(self, input_path, params=None, template_id="video_dub"):
        if params is None:
            existing = next((it for it in self._items if it.input_path == input_path and
                             it.status in ('draft', 'queued', 'processing')), None)
            if existing:
                return existing.to_dict()
        item = QueueItem(input_path, params, template_id)
        self._items.append(item)
        return item.to_dict()

    @durable
    def remove_item(self, item_id):
        initial_len = len(self._items)
        self._items = [it for it in self._items if it.id != item_id or it.status == "processing"]
        return len(self._items) < initial_len

    @durable
    def clear_completed(self, protected_id=None):
        self._items = [it for it in self._items if it.id == protected_id or it.status not in ("completed", "failed", "cancelled")]

    @synchronized
    def get_items(self):
        return [it.to_dict() for it in self._items]

    @synchronized
    def get_next_queued(self):
        if self._paused:
            return None
        for it in self._items:
            if it.status == "queued":
                return deepcopy(it)
        return None

    @durable
    def update_item(self, item_id, **kwargs):
        for it in self._items:
            if it.id == item_id:
                for k, v in kwargs.items():
                    if hasattr(it, k):
                        setattr(it, k, deepcopy(v))
                return it.to_dict()
        return None

    @durable
    def set_paused(self, paused: bool):
        self._paused = paused

    @synchronized
    def is_paused(self):
        return self._paused

    @durable
    def claim_next(self):
        item = self.get_next_queued()
        if item:
            self.update_item(item.id, status='processing', progress=0, status_text='Starting...')
            item.status = 'processing'
        return item

    @durable
    def freeze_drafts(self, params, template_id):
        for item in self._items:
            if item.status == 'draft':
                item.params = deepcopy(params)
                item.template_id = template_id
                item.status = 'queued'
                item.status_text = 'Enqueued'

    @durable
    def prepare_batch(self, params=None, template_id=None):
        """Accept drafts and claim the first job in one durable write."""
        before = self.checkpoint()
        if params is not None:
            self.freeze_drafts(params, template_id)
        self.set_paused(False)
        first = self.claim_next()
        if first is None:
            self.restore(before)
        return first

    @durable
    def prepare_recovery(self, item_id):
        self.set_paused(True)
        return self.update_item(item_id, status='processing', progress=0, status_text='Starting...')

    @synchronized
    def pause_after_storage_error(self):
        """Emergency in-memory halt when durable writes are unavailable.

        Last committed processing records normalize to queued on next boot.
        Do not pretend this fallback was saved or advance to another job.
        """
        self._paused = True
        for item in self._items:
            if item.status == 'processing':
                item.status = 'queued'
                item.status_text = 'Queue save failed; review before retry'

    @synchronized
    def checkpoint(self):
        return deepcopy((self._items, self._paused))

    @durable
    def restore(self, checkpoint):
        self._items, self._paused = deepcopy(checkpoint)
