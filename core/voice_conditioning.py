"""Bounded, model-local memoization of reference conditioning tensors."""
from collections import OrderedDict
from functools import wraps
import inspect
from pathlib import Path
import threading


def cached_conditioning(function, capacity=16):
    signature = inspect.signature(function)
    cache, lock = OrderedDict(), threading.RLock()
    @wraps(function)
    def call(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = dict(bound.arguments)
        paths = values.pop('audio_path')
        if not isinstance(paths, (list,tuple)):
            paths = [paths]
        identities = []
        for value in paths:
            path = Path(value).resolve()
            info = path.stat()
            identities.append((str(path),info.st_size,info.st_mtime_ns,info.st_ino))
        key = (tuple(identities), tuple(sorted(values.items())))
        with lock:
            if key not in cache:
                cache[key] = function(*args,**kwargs)
                if len(cache) > capacity:
                    cache.popitem(last=False)
            cache.move_to_end(key)
            return cache[key]
    return call
