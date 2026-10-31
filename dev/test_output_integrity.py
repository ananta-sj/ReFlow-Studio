"""Media failure/publishing checks; no AI inference or model downloads."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
import pipeline
from pydub import AudioSegment
from core import janitor
import audio_utils


class MediaFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT / "temp")))
        self.subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        self.subject.temp_dir = str(self.directory)
        self.subject.output_dir = str(self.directory)
        self.subject.registry = Mock()
        self.subject.registry.get_active.return_value = None
        self.subject.registry.list.return_value = []
        self.destination = self.directory / "existing.mp4"
        self.destination.write_bytes(b"previous good output")

    def assert_preserved(self):
        self.assertEqual(self.destination.read_bytes(), b"previous good output")
        self.assertFalse(list(self.directory.glob(".reflow-*")))

    def inputs(self):
        video, audio = self.directory / 'video.mp4', self.directory / 'audio.wav'
        video.write_bytes(b'input video')
        audio.write_bytes(b'input audio')
        subtitles = self.directory / 'subtitles.srt'
        self.subject.generate_srt([{'start': 0, 'end': 1, 'text': 'Hello'}], subtitles)
        return str(video), str(audio), str(subtitles)


class OutputIntegrityTests(MediaFixture):

    def test_nonzero_exit_retains_bounded_diagnostics(self):
        def failure(cmd, **kwargs):
            kwargs['stderr'].write(b'x' * 10000 + b' specific codec failure')
            self.assertTrue(kwargs['check'])
            self.assertEqual(kwargs['timeout'], 1800)
            raise subprocess.CalledProcessError(9, cmd)
        with patch.object(pipeline.subprocess, 'run', side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, 'exit code 9') as error:
                pipeline._run_ffmpeg(['ffmpeg'], stderr=subprocess.DEVNULL)
        self.assertIn('specific codec failure', str(error.exception))
        self.assertLess(len(str(error.exception)), 6200)

    def test_timeout_has_useful_error(self):
        with patch.object(pipeline.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ffmpeg', 1800)):
            with self.assertRaisesRegex(RuntimeError, 'timed out after 1800s'):
                pipeline._run_ffmpeg(['ffmpeg'])

    def test_missing_executable_has_useful_error(self):
        with patch.object(pipeline.subprocess, 'run', side_effect=FileNotFoundError('missing executable')):
            with self.assertRaisesRegex(RuntimeError, 'could not start'):
                pipeline._run_ffmpeg(['ffmpeg'])

    def test_duration_probe_is_bounded_and_positive(self):
        with patch.object(pipeline.subprocess, 'run', return_value=Mock(stdout=b'1.25')) as run:
            self.assertEqual(self.subject.get_duration('input.mp4'), 1.25)
        self.assertEqual(run.call_args.kwargs['timeout'], 60)
        self.assertTrue(run.call_args.kwargs['check'])

    def test_invalid_durations_fail(self):
        for output in (b'0', b'-1', b'nan', b'inf', b'N/A', b''):
            with self.subTest(output=output), patch.object(pipeline.subprocess, 'run', return_value=Mock(stdout=output)):
                with self.assertRaisesRegex(RuntimeError, 'valid duration'):
                    self.subject.get_duration('input.mp4')

    def test_staged_exception_preserves_old_output(self):
        with self.assertRaisesRegex(RuntimeError, 'encode failed'):
            with pipeline._staged_output(self.destination) as pending:
                Path(pending).write_bytes(b'partial data')
                raise RuntimeError('encode failed')
        self.assert_preserved()

    def test_empty_staged_output_preserves_old_output(self):
        with self.assertRaisesRegex(RuntimeError, 'No usable output'):
            with pipeline._staged_output(self.destination):
                pass
        self.assert_preserved()

    def test_publish_failure_preserves_old_output(self):
        with patch.object(pipeline.os, 'replace', side_effect=PermissionError('destination locked')):
            with self.assertRaises(PermissionError):
                with pipeline._staged_output(self.destination) as pending:
                    Path(pending).write_bytes(b'new render')
        self.assert_preserved()

    def test_invalid_media_is_not_published(self):
        for info in (
            {'format': {'duration': '1'}, 'streams': [{'codec_type': 'video'}]},
            {'format': {'duration': '0'}, 'streams': [{'codec_type': 'audio'}, {'codec_type': 'video'}]},
            {},
        ):
            with self.subTest(info=info), patch.object(pipeline, '_run_media_command', return_value=Mock(stdout=json.dumps(info))):
                with self.assertRaisesRegex(RuntimeError, 'Invalid media output'):
                    with pipeline._staged_output(self.destination) as pending:
                        Path(pending).write_bytes(b'partial media')
                        pipeline._validate_media(pending, {'video', 'audio'})
            self.assert_preserved()

    def test_malformed_probe_json_is_rejected(self):
        with patch.object(pipeline, '_run_media_command', return_value=Mock(stdout=b'not json')):
            with self.assertRaisesRegex(RuntimeError, 'Invalid media output'):
                pipeline._validate_media('file.mp4', {'video'})

    def test_subtitle_write_error_preserves_existing_file(self):
        with patch('builtins.open', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.subject.generate_srt([{'start': 0, 'end': 1, 'text': 'Hello'}], self.destination)
        self.assert_preserved()

    def test_invalid_subtitle_timing_preserves_existing_file(self):
        with self.assertRaisesRegex(ValueError, 'subtitle timing'):
            self.subject.generate_srt([{'start': 1, 'end': 0, 'text': 'Hello'}], self.destination)
        self.assert_preserved()

    def test_blank_subtitles_preserve_existing_file(self):
        with self.assertRaisesRegex(RuntimeError, 'nonempty subtitle cues'):
            self.subject.generate_srt([{'start': 0, 'end': 1, 'text': ' '}], self.destination)
        self.assert_preserved()

    def test_valid_subtitles_replace_existing_file(self):
        self.subject.generate_srt([
            {'start': 0, 'end': 1, 'text': ' '},
            {'start': 1, 'end': 2, 'text': 'Hello'},
        ], self.destination)
        self.assertEqual(self.destination.read_text(), '1\n00:00:01,000 --> 00:00:02,000\nHello\n\n')
        self.assertFalse(list(self.directory.glob('.reflow-*')))

    def test_failed_initial_mux_preserves_old_output(self):
        inputs = self.inputs()
        with patch.object(pipeline, '_run_ffmpeg', side_effect=RuntimeError('mux failed')):
            with self.assertRaisesRegex(RuntimeError, 'mux failed'):
                self.subject.merge_av(*inputs, str(self.destination))
        self.assert_preserved()

    def test_failed_subtitle_pass_preserves_old_output(self):
        inputs = self.inputs()
        def encode(cmd, **kwargs):
            if cmd[-1].endswith('clean.mp4'):
                Path(cmd[-1]).write_bytes(b'clean video')
            else:
                Path(cmd[-1]).write_bytes(b'partial subtitled video')
                raise RuntimeError('subtitle pass failed')
        for burn in (False, True):
            with self.subTest(burn=burn), patch.object(pipeline, '_run_ffmpeg', side_effect=encode):
                with self.assertRaisesRegex(RuntimeError, 'subtitle pass failed'):
                    self.subject.merge_av(*inputs, str(self.destination), burn_subs=burn)
            self.assert_preserved()

    def test_missing_merge_input_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'merge input'):
            self.subject.merge_av('missing.mp4', 'missing.wav', 'missing.srt', str(self.destination))
        self.assert_preserved()

    def test_requested_burn_without_subtitles_fails(self):
        video, audio, subtitles = self.inputs()
        Path(subtitles).unlink()
        with self.assertRaisesRegex(RuntimeError, 'burn-in was requested'):
            self.subject.merge_av(video, audio, subtitles, str(self.destination), burn_subs=True)
        self.assert_preserved()


class BundledMediaTests(MediaFixture):
    # Keep these tests separate from unit checks while sharing fixture helpers.
    def setUp(self):
        super().setUp()
        executable_dir = ROOT / 'ffmpeg' / 'bin'
        if not (executable_dir / 'ffmpeg.exe').is_file():
            self.skipTest('Bundled Windows FFmpeg unavailable')
        self.stack.enter_context(patch.dict(os.environ, {'PATH': str(executable_dir) + os.pathsep + os.environ.get('PATH', '')}))

    def actual_inputs(self):
        video = self.directory / 'source.mp4'
        audio = self.directory / 'source.wav'
        pipeline._run_ffmpeg(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=10', '-t', '0.5', str(video)])
        AudioSegment.silent(duration=500).export(audio, format='wav').close()
        subtitles = self.directory / 'source.srt'
        self.subject.generate_srt([{'start': 0, 'end': 0.4, 'text': 'Hello'}], subtitles)
        return str(video), str(audio), str(subtitles)

    def test_real_mux_without_subtitles(self):
        video, audio, _ = self.actual_inputs()
        self.subject.merge_av(video, audio, str(self.directory / 'absent.srt'), str(self.destination), ffmpeg_preset='veryfast')
        pipeline._validate_media(str(self.destination), {'video', 'audio'})
        self.assertFalse(list(self.directory.glob('.reflow-*')))

    def test_real_mux_with_embedded_subtitles(self):
        self.subject.merge_av(*self.actual_inputs(), str(self.destination), ffmpeg_preset='veryfast')
        pipeline._validate_media(str(self.destination), {'video', 'audio', 'subtitle'})
        self.assertFalse(list(self.directory.glob('.reflow-*')))

    def test_real_mux_with_burned_subtitles(self):
        self.subject.merge_av(*self.actual_inputs(), str(self.destination), burn_subs=True, ffmpeg_preset='veryfast')
        pipeline._validate_media(str(self.destination), {'video', 'audio'})
        self.assertFalse(list(self.directory.glob('.reflow-*')))

    def test_real_ffmpeg_failure_preserves_old_output(self):
        _, audio, subtitles = self.actual_inputs()
        invalid_video = self.directory / 'corrupt.mp4'
        invalid_video.write_bytes(b'not media')
        with self.assertRaisesRegex(RuntimeError, 'exit code'):
            self.subject.merge_av(str(invalid_video), audio, subtitles, str(self.destination))
        self.assert_preserved()

    def test_real_speed_change_has_unique_files_and_valid_audio(self):
        original = AudioSegment.silent(duration=1000)
        output = self.subject.speed_change(original, 1.2)
        self.assertGreater(len(output), 0)
        self.assertLess(len(output), len(original))
        self.assertFalse(list(self.directory.glob('reflow-stretch-*')))

    def test_speech_tempo_preserves_pitch_timing_and_headroom(self):
        import numpy as np
        from pydub.generators import Sine
        from core.loudness import measure_loudness
        original = Sine(220).to_audio_segment(duration=2000).apply_gain(-3)
        for speed in (.85, 1.342):
            with self.subTest(speed=speed):
                result = self.subject.speed_change(original, speed)
                self.assertLess(abs(len(result)-len(original)/speed), 30)
                middle = result[200:-200]
                samples = np.asarray(middle.get_array_of_samples(), dtype=float)
                spectrum = np.abs(np.fft.rfft(samples*np.hanning(len(samples))))
                frequency = np.fft.rfftfreq(len(samples), 1/middle.frame_rate)[np.argmax(spectrum)]
                self.assertAlmostEqual(frequency, 220, delta=2)
                output = self.directory / 'tempo.wav'
                result.export(output, format='wav').close()
                self.assertLessEqual(measure_loudness(output)['input_tp'], -1.2)
        self.assertFalse(list(self.directory.glob('reflow-stretch-*')))

    def test_missing_rubberband_is_explicit_without_fallback(self):
        with patch.object(pipeline, '_run_ffmpeg', side_effect=RuntimeError("No such filter: 'rubberband'")) as command:
            with self.assertRaisesRegex(RuntimeError, 'Use the bundled FFmpeg'):
                self.subject.speed_change(AudioSegment.silent(duration=1000), 1.342)
        self.assertEqual(command.call_count, 1)
        self.assertFalse(list(self.directory.glob('reflow-stretch-*')))

    def test_invalid_speech_tempo_rejected_before_process(self):
        with patch.object(pipeline, '_run_ffmpeg') as command:
            for speed in (True, '1.342', float('nan'), float('inf'), 0, -1, 101):
                with self.subTest(speed=speed), self.assertRaises(ValueError):
                    self.subject.speed_change(AudioSegment.silent(duration=1000), speed)
        command.assert_not_called()

    def test_cancelled_speech_tempo_does_not_start_or_leak(self):
        from core.render_context import RenderContext, bind_job, RenderCancelled
        job = RenderContext(self.directory)
        try:
            job.request_stop()
            with bind_job(job), self.assertRaises(RenderCancelled):
                self.subject.speed_change(AudioSegment.silent(duration=1000), 1.342)
            self.assertFalse(list(self.directory.glob('reflow-stretch-*')))
        finally:
            job.cleanup()

    def test_audio_template_preserves_old_output_on_validation_failure(self):
        _, audio, _ = self.actual_inputs()
        destination = self.directory / 'source_DUBBED_SOURCE.wav'
        destination.write_bytes(b'old audio')
        def segments(*args, **kwargs):
            yield 50, 'Simulated dubbing', None
            return AudioSegment.silent(duration=500)
        with patch.object(janitor, 'Janitor'), patch.object(audio_utils, 'AudioEngineer'), \
                patch.object(pipeline, 'Settings', return_value={}), \
                patch.object(self.subject, '_transcribe_and_translate', return_value=pipeline.normalize_transcription({'segments': [], 'language': 'en', 'language_probability': .99})), \
                patch.object(self.subject, '_dub_all_segments', side_effect=segments), \
                patch.object(pipeline.providers, 'resolve_tts'), \
                patch.object(pipeline, '_validate_media', side_effect=RuntimeError('audio invalid')):
            with self.assertRaisesRegex(RuntimeError, 'audio invalid'):
                list(self.subject.process_audio_dub_gen(audio, ['CLONED_USER'], target_lang='source', keep_background=False, compute_device='cpu'))
        self.assertEqual(destination.read_bytes(), b'old audio')
        self.assertFalse(list(self.directory.glob('.reflow-*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
