"""Real PCM checks against clipping introduced by the voice EQ sum."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from pydub import AudioSegment
from pydub.generators import Sine
from core.audio_utils import AudioEngineer


class VoiceMasteringTests(unittest.TestCase):
    def test_failed_loudness_pass_preserves_original_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'voice.wav'
            Sine(220).to_audio_segment(duration=400).export(output, format='wav').close()
            original = output.read_bytes()
            with patch('core.loudness.normalize_voice_loudness', side_effect=RuntimeError('failed loudness')):
                with self.assertRaisesRegex(RuntimeError, 'failed loudness'):
                    AudioEngineer().master_voice_segment(str(output))
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob('.reflow-*')), [])

    def test_loud_voice_background_mix_does_not_clip(self):
        import math
        voice = Sine(220, sample_rate=44100).to_audio_segment(duration=500)
        background = voice.apply_gain(-1)
        mixed = AudioEngineer().dynamic_mix(voice, background, ducking_db=0, active_ducking_db=0)
        self.assertEqual(len(mixed), len(voice))
        self.assertLess(mixed.max_dBFS, 0)
        samples = np.asarray(mixed.get_array_of_samples(), dtype=float)
        phase = np.arange(len(samples)) * 2 * math.pi * 220 / 44100
        basis = np.column_stack((np.sin(phase), np.cos(phase)))
        fitted = basis @ np.linalg.lstsq(basis, samples, rcond=None)[0]
        self.assertLess(np.linalg.norm(samples - fitted) / np.linalg.norm(samples), .001)

    def test_full_scale_tone_remains_linear_without_clipping_harmonics(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'voice.wav'
            Sine(4000, sample_rate=44100).to_audio_segment(duration=400).export(
                output, format='wav').close()
            # Isolate the EQ/mix from the intentional nonlinear compressor.
            with patch('core.audio_utils.effects.compress_dynamic_range', side_effect=lambda audio, **kw: audio), \
                    patch('core.loudness.normalize_voice_loudness'):
                AudioEngineer().master_voice_segment(str(output))
            clip = AudioSegment.from_wav(output)
            self.assertLessEqual(clip.max_dBFS, -0.95)
            self.assertGreater(clip.max_dBFS, -1.05)
            samples = np.asarray(clip.get_array_of_samples(), dtype=np.float64)[4410:]
            phase = np.arange(len(samples)) * 2 * np.pi * 4000 / 44100
            basis = np.column_stack((np.sin(phase), np.cos(phase), np.ones(len(phase))))
            fitted = basis @ np.linalg.lstsq(basis, samples, rcond=None)[0]
            relative_error = np.linalg.norm(samples - fitted) / np.linalg.norm(samples)
            self.assertLess(relative_error, .005, 'EQ overlay introduced waveform distortion')

    def test_silent_mastering_preserves_valid_timeline(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'silence.wav'
            AudioSegment.silent(duration=400).export(output, format='wav').close()
            AudioEngineer().master_voice_segment(str(output))
            clip = AudioSegment.from_wav(output)
            self.assertEqual(len(clip), 400)
            self.assertEqual(clip.max, 0)
