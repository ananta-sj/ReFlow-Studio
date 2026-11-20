"""Modern audio-library compatibility; synthetic samples, no model weights."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]


class Wav2LipAudioCompatibilityTests(unittest.TestCase):
    def test_wavenet_wav_roundtrip_preserves_samples_and_input(self):
        folder = ROOT / 'core/Wav2Lip'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('reflow_wav2lip_audio_test', folder / 'audio.py')
            audio = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(audio)
        finally:
            sys.path.remove(str(folder))
        samples = (0.25 * np.sin(np.arange(1600, dtype=np.float32) * 0.08)).astype(np.float32)
        original = samples.copy()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic.wav'
            audio.save_wavenet_wav(samples, str(path), 16000)
            decoded, rate = sf.read(path, dtype='float32')
        self.assertEqual(rate, 16000)
        self.assertEqual(decoded.shape, original.shape)
        np.testing.assert_allclose(decoded, original, atol=1e-6)
        np.testing.assert_array_equal(samples, original)


if __name__ == '__main__':
    unittest.main()
