"""Local RVC voice-conversion provider - thin wrapper around the
existing RVCHandler."""

from core.providers.base import VoiceProvider
from rvc.rvc_handler import RVCHandler


class RVCLocalProvider(VoiceProvider):
    def __init__(self, device="cuda", model_path=None, index_path=None, version=None):
        self.device = device
        self.model_path, self.index_path, self.version = model_path, index_path, version
        self._handler = None  # lazy + cached, same reasoning as the TTS
        # provider: convert() runs once per segment, RVCHandler's model
        # load should happen once per video.

    def convert(self, input_audio, output_audio, model_name, pitch_change=0, text=None, reference_audio=None):
        if self._handler is None:
            self._handler = RVCHandler(device=self.device)
        kwargs = {'model_name': model_name, 'pitch_change': pitch_change}
        if self.model_path:
            kwargs.update(model_path=self.model_path, index_path=self.index_path, version=self.version)
        return self._handler.infer(input_audio, output_audio, **kwargs)
