"""Defer F5's ASR and training imports for one reviewed upstream revision.

The installed package is unchanged. Pipeline and Trainer imports become lazy
when two hash-bound modules are compiled inside an owned inference worker.
"""
from contextlib import contextmanager
import hashlib
import importlib
import importlib.abc
import importlib.machinery
from importlib import metadata
import sys

VERSION='1.1.22'
SOURCE_SHA256='b05b7b159ceabe07f318b68c082970ec14ba8481fe2812e3774f8246628267c8'
MODULE='f5_tts.infer.utils_infer'
MODEL_MODULE='f5_tts.model'
MODEL_SHA256='a27d1406ccf102af4dfc9e5c9071f06739e21eb356f312784274731f088953a0'
TRAINER_IMPORT='from f5_tts.model.trainer import Trainer\n'
LAZY_TRAINER=('def __getattr__(name):\n'
              '    if name == "Trainer":\n'
              '        from f5_tts.model.trainer import Trainer\n'
              '        globals()["Trainer"] = Trainer\n'
              '        return Trainer\n'
              '    raise AttributeError(name)\n')
NEEDLE='from transformers import pipeline\n'
REPLACEMENT=('def pipeline(*args, **kwargs):\n'
             '    from transformers import pipeline as upstream_pipeline\n'
             '    return upstream_pipeline(*args, **kwargs)\n')


def deferred_source(payload):
    if hashlib.sha256(payload).hexdigest()!=SOURCE_SHA256:
        raise RuntimeError('F5 import adapter source changed; review this installed version before use')
    source=payload.decode('utf-8')
    if source.count(NEEDLE)!=1:raise RuntimeError('F5 pipeline import does not match the reviewed source')
    return source.replace(NEEDLE,REPLACEMENT)+'\n__reflow_reference_asr_deferred__ = True\n'


def deferred_model_source(payload):
    if hashlib.sha256(payload).hexdigest()!=MODEL_SHA256:
        raise RuntimeError('F5 model import adapter source changed; review before use')
    source=payload.decode('utf-8')
    if source.count(TRAINER_IMPORT)!=1:raise RuntimeError('F5 Trainer import differs from reviewed source')
    return source.replace(TRAINER_IMPORT,LAZY_TRAINER)+'\n__reflow_training_deferred__ = True\n'


class _Loader(importlib.machinery.SourceFileLoader):
    def get_code(self,fullname):
        transform=deferred_source if fullname==MODULE else deferred_model_source
        return compile(transform(self.get_data(self.path)),self.path,'exec',dont_inherit=True)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname not in (MODULE,MODEL_MODULE):return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        if spec is None or not spec.origin or not isinstance(spec.loader,importlib.machinery.SourceFileLoader):
            raise RuntimeError('F5 source module must come from an installed Python source file')
        spec.loader=_Loader(fullname,spec.origin)
        return spec


@contextmanager
def defer_reference_asr():
    finder=_Finder();sys.meta_path.insert(0,finder)
    try:yield
    finally:
        if finder in sys.meta_path:sys.meta_path.remove(finder)


def load_f5_api():
    if metadata.version('f5-tts')!=VERSION:raise RuntimeError('F5 import adapter requires reviewed f5-tts '+VERSION)
    with defer_reference_asr():api=importlib.import_module('f5_tts.api')
    engine=getattr(api,'F5TTS',None)
    if not callable(engine) or not callable(getattr(engine,'infer',None)):
        raise RuntimeError('F5 speech API is missing its F5TTS/infer entry points')
    return engine
