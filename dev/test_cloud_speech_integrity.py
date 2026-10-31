"""Cloud speech validation uses local PCM fixtures; no service calls or keys."""
import io
import math
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from core.providers.tts.cloud_rest import TTSCloudRestProvider
from core.providers.voice.cloud_rest import VoiceCloudRestProvider

ROOT = Path(__file__).resolve().parents[1]


def pcm(silent, frequency=220):
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b''.join(struct.pack('<h', 0 if silent else round(8000 * math.sin(2*math.pi*frequency*i/16000)))
                                   for i in range(8000)))
    return output.getvalue()


class CloudSpeechIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.wav'
        self.source.write_bytes(pcm(False))
        self.output = self.folder / 'speech.wav'
        self.original = pcm(False, 440)
        self.output.write_bytes(self.original)
        patcher = patch.dict(os.environ, {'PATH': str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, stage, payload):
        response = Mock(headers={'Content-Type': 'audio/wav', 'Content-Length': str(len(payload))})
        response.iter_content.return_value = iter([payload])
        target = 'core.providers.' + stage + '.cloud_rest.request'
        with patch(target, return_value=response):
            try:
                if stage == 'tts':
                    return TTSCloudRestProvider('https://example.invalid', None).synthesize('A sentence.', str(self.output))
                return VoiceCloudRestProvider('https://example.invalid', None).convert(str(self.source), str(self.output), 'fixture')
            finally:
                response.close.assert_called_once()

    def test_silent_speech_preserves_previous_output_for_both_adapters(self):
        for stage in ('tts', 'voice'):
            with self.subTest(stage=stage), self.assertRaisesRegex(RuntimeError, 'digitally silent'):
                self.call(stage, pcm(True))
            self.assertEqual(self.output.read_bytes(), self.original)
            self.assertEqual(list(self.folder.glob('.reflow-*')), [])

    def test_signal_audio_is_published_and_response_closed_for_both_adapters(self):
        for stage in ('tts', 'voice'):
            with self.subTest(stage=stage):
                self.output.write_bytes(self.original)
                self.assertEqual(self.call(stage, pcm(False)), str(self.output))
                self.assertEqual(self.output.read_bytes(), pcm(False))

    def test_corrupt_audio_cannot_replace_previous_output(self):
        for stage in ('tts', 'voice'):
            with self.subTest(stage=stage), self.assertRaises(RuntimeError):
                self.call(stage, b'not audio')
            self.assertEqual(self.output.read_bytes(), self.original)
