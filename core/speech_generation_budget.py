"""Reject unfinished synthesis at its token budget; never publish truncated words."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math

_tokens = ContextVar('xtts_generation_tokens', default=None)


class SpeechGenerationLimitExceeded(RuntimeError):
    pass


@contextmanager
def generation_budget(seconds, token_seconds):
    if seconds is None:
        yield
        return
    if not math.isfinite(seconds) or seconds <= 0 or not math.isfinite(token_seconds) or token_seconds <= 0:
        raise ValueError('Invalid speech generation budget')
    token = _tokens.set(max(1,math.ceil(seconds/token_seconds)))
    try:
        yield
    finally:
        _tokens.reset(token)


def bounded_generate(function):
    @wraps(function)
    def call(*args,**kwargs):
        budget = _tokens.get()
        if budget is None:
            return function(*args,**kwargs)
        inputs = args[0] if args else kwargs.get('inputs')
        prefix = inputs.shape[-1]
        limit = min(budget,kwargs.pop('max_length',prefix+budget)-prefix,
                    kwargs.get('max_new_tokens',budget))
        kwargs['max_new_tokens'] = max(1,limit)
        result = function(*args,**kwargs)
        sequences = getattr(result,'sequences',result)
        eos = kwargs.get('eos_token_id')
        if eos is None or not bool((sequences[:,-1] == eos).all()):
            raise SpeechGenerationLimitExceeded('XTTS did not finish within the dialogue budget; unfinished audio was rejected')
        return result
    return call
