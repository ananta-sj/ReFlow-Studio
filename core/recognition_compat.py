"""Narrow faster-whisper 1.2.1 / PyAV 19.0.1 decoding compatibility.

PyAV 19 removed metadata_errors from av.open. Only faster-whisper's private
module reference is adapted; the installed packages and global av.open stay
unchanged. Metadata decoding otherwise follows PyAV 19's native behavior.
"""
from importlib.metadata import PackageNotFoundError, version


class _AudioAV:
    def __init__(self, module):
        self._module = module

    def __getattr__(self, name):
        return getattr(self._module, name)

    def open(self, *args, **kwargs):
        if 'metadata_errors' in kwargs:
            if kwargs.pop('metadata_errors') != 'ignore':
                raise ValueError('Unsupported faster-whisper metadata error policy')
        return self._module.open(*args, **kwargs)


def apply():
    try:
        if version('faster-whisper') != '1.2.1' or version('av') != '19.0.1':
            return False
    except PackageNotFoundError:
        return False
    import av
    from faster_whisper import audio
    if av.__version__ != '19.0.1':
        raise RuntimeError('PyAV metadata and imported version disagree')
    if not isinstance(audio.av, _AudioAV):
        if audio.av is not av:
            raise RuntimeError('Unexpected faster-whisper decoder module; refusing compatibility override')
        audio.av = _AudioAV(av)
    return True
