"""Actual FFmpeg loudness, short-cue and cancellation acceptance."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from pydub import AudioSegment
from pydub.generators import Sine
from core.loudness import measure_loudness, normalize_voice_loudness
from core.render_context import RenderContext, RenderCancelled, bind_job


class LoudnessTests(unittest.TestCase):
    def test_conversion_peak_overshoot_is_corrected_without_changing_timing(self):
        from core import loudness
        original_ffmpeg = loudness._ffmpeg
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'overshoot.wav'
            Sine(440).to_audio_segment(duration=4000).apply_gain(-.1).export(output, format='wav').close()
            def conversion_overshoot(args):
                if '-c:a' in args:
                    # Simulate an excessive converter peak; measurements remain real.
                    shutil.copy2(args[args.index('-i') + 1], args[-1])
                    return ''
                return original_ffmpeg(args)
            with patch.object(loudness, '_ffmpeg', side_effect=conversion_overshoot):
                report = normalize_voice_loudness(output)
            self.assertGreater(report['peak_correction_db'], 1)
            self.assertLessEqual(measure_loudness(output)['input_tp'], -1.49)
            self.assertEqual(len(AudioSegment.from_wav(output)), 4000)
            self.assertEqual(AudioSegment.from_wav(output).frame_rate, 44100)

    def test_quiet_clip_reaches_measured_loudness_without_changing_timeline(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'quiet.wav'
            Sine(440).to_audio_segment(duration=4000).apply_gain(-25).export(output, format='wav').close()
            before = measure_loudness(output)
            report = normalize_voice_loudness(output)
            after = measure_loudness(output)
            self.assertGreater(after['input_i'] - before['input_i'], 10)
            self.assertLess(abs(after['input_i'] + 14), 1)
            self.assertLessEqual(after['input_tp'], -1.2)
            self.assertEqual(len(AudioSegment.from_wav(output)), 4000)
            self.assertEqual(AudioSegment.from_wav(output).frame_rate, 44100)
            self.assertTrue(report['integrated_loudness_measured'])

    def test_short_cue_falls_back_without_invalid_infinite_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'short.wav'
            Sine(440).to_audio_segment(duration=100).export(output, format='wav').close()
            report = normalize_voice_loudness(output)
            self.assertEqual(report['mode'], 'short_clip_peak_fallback')
            self.assertEqual(len(AudioSegment.from_wav(output)), 100)
            self.assertLessEqual(AudioSegment.from_wav(output).max_dBFS, -1.49)

    def test_cancelled_normalization_preserves_previous_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(folder)
            output = job.workspace / 'voice.wav'
            Sine(440).to_audio_segment(duration=1000).export(output, format='wav').close()
            before = output.read_bytes()
            with bind_job(job):
                job.request_stop()
                with self.assertRaises(RenderCancelled):
                    normalize_voice_loudness(output)
            self.assertEqual(output.read_bytes(), before)
            self.assertFalse(list(job.workspace.glob('.reflow-*')))
            job.cleanup()
