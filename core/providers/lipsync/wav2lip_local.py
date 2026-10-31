"""Local Wav2Lip lip-sync provider - thin wrapper around the existing
LipSyncHandler, no behavior change from calling it directly. Fresh
instance per call (matches the original pipeline: lip sync runs once per
video, not once per segment - see core/providers/enhancer/gfpgan_local.py
for the same reasoning)."""

from core.providers.base import LipSyncProvider
from lipsync_handler import LipSyncHandler


class Wav2LipLocalProvider(LipSyncProvider):
    def __init__(self, model_path=None, device=None):
        self.model_path = model_path
        self.device = device

    def execute(self, video_path, audio_path, output_path):
        handler = LipSyncHandler(model_path=self.model_path, device=self.device)
        return handler.execute(video_path, audio_path, output_path)
