"""Real audio decoding/assembly with simulated speech engines; no downloads."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
import pipeline
import config
from pydub import AudioSegment
from pydub.generators import Sine
from core.audio_utils import load_playable_audio, load_speech_audio
with patch.dict(sys.modules, {'TTS.tts.configs.xtts_config': None}):
    import tts.tts_handler as handler_module
# patch.dict restores the module inventory; retain the module just imported
# so the provider uses the same handler rather than importing it a second time.
sys.modules['tts.tts_handler'] = handler_module
TTSHandler = handler_module.TTSHandler
from rvc.rvc_handler import RVCHandler
from core.providers.tts import xtts_local
from core.providers.voice import rvc_local, f5tts_local


class SpeechFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT / 'temp')))
        self.stack.enter_context(patch.dict(os.environ, {'PATH': str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')}))
        self.reference = self.directory / 'reference.wav'
        self.write_audio(self.reference)
        self.output = self.directory / 'output.wav'

    def write_audio(self, path, duration=1000):
        Sine(220).to_audio_segment(duration=duration).export(path, format='wav').close()


class AudioValidationTests(SpeechFixture):
    def test_missing_and_empty_audio_fail(self):
        for exists in (False, True):
            if exists:
                self.output.touch()
            with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
                load_playable_audio(self.output)

    def test_corrupt_audio_fails_decode(self):
        self.output.write_bytes(b'not audio')
        with self.assertRaisesRegex(RuntimeError, 'could not be decoded'):
            load_playable_audio(self.output)

    def test_zero_sample_wav_fails(self):
        AudioSegment.silent(duration=0).export(self.output, format='wav').close()
        with self.assertRaisesRegex(RuntimeError, 'no playable samples'):
            load_playable_audio(self.output)

    def test_real_short_audio_is_playable(self):
        self.write_audio(self.output, 300)
        self.assertEqual(len(load_playable_audio(self.output)), 300)

    def test_digital_silence_is_valid_background_but_not_generated_speech(self):
        AudioSegment.silent(duration=300).export(self.output, format='wav').close()
        self.assertEqual(len(load_playable_audio(self.output)), 300)
        with self.assertRaisesRegex(RuntimeError, 'digitally silent'):
            load_speech_audio(self.output)


class XTTSTests(SpeechFixture):
    def setUp(self):
        super().setUp()
        self.model_dir = self.directory / 'model'
        self.model_dir.mkdir()
        (self.model_dir / 'config.json').write_text('{"model":"xtts","languages":["en"]}')
        self.engine = Mock()
        self.engine.synthesizer = SimpleNamespace(output_sample_rate=22050,
            tts_model=SimpleNamespace(hifigan_decoder=SimpleNamespace(output_sample_rate=24000)))
        self.factory = Mock(return_value=self.engine)
        self.stack.enter_context(patch.dict(sys.modules, {'TTS.api': SimpleNamespace(TTS=self.factory)}))
        self.engine.tts_to_file.side_effect = lambda **kw: self.write_audio(kw['file_path'])

    def handler(self, device='cpu', **kwargs):
        return TTSHandler(device=device, model_path=str(self.model_dir), **kwargs)

    def test_missing_config_fails_initialization(self):
        (self.model_dir / 'config.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'model/config files'):
            self.handler()
        self.factory.assert_not_called()

    def test_cpu_initialization_failure_propagates(self):
        self.factory.side_effect = RuntimeError('bad checkpoint')
        with self.assertRaisesRegex(RuntimeError, 'bad checkpoint'):
            self.handler()

    def test_gpu_recovery_warns_and_updates_actual_device(self):
        self.factory.side_effect = [RuntimeError('out of memory'), self.engine]
        notify = Mock()
        with self.assertLogs(level='WARNING'):
            handler = self.handler('cuda', warning_callback=notify)
        self.assertEqual(handler.device, 'cpu')
        self.assertFalse(handler.use_gpu)
        self.assertIn('continuing on CPU', notify.call_args.args[0])

    def test_gpu_and_cpu_failure_propagate_both_causes(self):
        self.factory.side_effect = [RuntimeError('GPU broke'), RuntimeError('CPU broke')]
        with self.assertRaisesRegex(RuntimeError, 'GPU broke.*CPU broke'):
            self.handler('cuda')

    def test_generation_failure_propagates(self):
        self.engine.tts_to_file.side_effect = RuntimeError('inference broke')
        with self.assertRaisesRegex(RuntimeError, 'inference broke'):
            self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))

    def test_missing_engine_output_is_failure(self):
        self.engine.tts_to_file.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
            self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))

    def test_stale_audio_is_not_success(self):
        self.write_audio(self.output)
        previous = self.output.read_bytes()
        self.engine.tts_to_file.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
            self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))
        self.assertEqual(self.output.read_bytes(), previous)

    def test_bad_explicit_reference_is_not_substituted(self):
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
            self.handler().generate_audio('Hello', str(self.output), reference_audio='missing-reference.wav')
        self.engine.tts_to_file.assert_not_called()

    def test_no_reference_fails_without_emergency_silence(self):
        with patch.object(config, 'BASE_DIR', str(self.directory)), patch.object(config, 'TEMP_PATH', str(self.directory)):
            with self.assertRaisesRegex(RuntimeError, 'playable voice reference'):
                self.handler().generate_audio('Hello', str(self.output))
        self.assertFalse((self.directory / 'emergency_ref.wav').exists())

    def test_success_returns_actual_generated_path(self):
        result = self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))
        self.assertEqual(result, str(self.output))
        self.assertGreater(len(load_playable_audio(result)), 0)

    def test_hindi_disables_random_sampling_and_retains_explicit_reference(self):
        (self.model_dir / 'config.json').write_text('{"model":"xtts","languages":["en","hi"]}')
        self.handler().generate_audio('नमस्ते', str(self.output), language='hi', reference_audio=str(self.reference))
        options = self.engine.tts_to_file.call_args.kwargs
        self.assertIs(options['do_sample'], False)
        self.assertEqual(options['num_beams'], 1)
        self.assertEqual(options['language'], 'hi')
        self.assertEqual(options['speaker_wav'], str(self.reference))

    def test_english_keeps_engine_sampling_defaults(self):
        self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))
        options = self.engine.tts_to_file.call_args.kwargs
        self.assertNotIn('do_sample', options)
        self.assertNotIn('num_beams', options)
        self.assertEqual(options['temperature'], .75)
        self.assertIs(options['split_sentences'], True)

    def test_short_cue_context_policy_reaches_the_real_generation_call(self):
        model = self.engine.synthesizer.tts_model
        model.args = SimpleNamespace(gpt_max_text_tokens=402)
        model.tokenizer = SimpleNamespace(char_limits={'de': 253}, encode=Mock(return_value=[1, 2, 3]))
        (self.model_dir / 'config.json').write_text('{"model":"xtts","languages":["en","de"]}')
        text = 'Guten Morgen. Willkommen in unserem Studio.'
        self.handler().generate_audio(text, str(self.output), language='de', reference_audio=str(self.reference))
        self.assertIs(self.engine.tts_to_file.call_args.kwargs['split_sentences'], False)
        self.assertEqual(self.engine.tts_to_file.call_args.kwargs['text'], text)

    def test_tokenizer_failure_preserves_prior_output_before_inference(self):
        self.write_audio(self.output)
        original = self.output.read_bytes()
        model = self.engine.synthesizer.tts_model
        model.args = SimpleNamespace(gpt_max_text_tokens=402)
        model.tokenizer = SimpleNamespace(char_limits={'de': 253}, encode=Mock(side_effect=RuntimeError('invalid tokens')))
        (self.model_dir / 'config.json').write_text('{"model":"xtts","languages":["en","de"]}')
        with self.assertRaisesRegex(RuntimeError, 'invalid tokens'):
            self.handler().generate_audio('Guten Morgen.', str(self.output), language='de', reference_audio=str(self.reference))
        self.assertEqual(self.output.read_bytes(), original)
        self.engine.tts_to_file.assert_not_called()

    def test_decoder_samples_save_at_native_rate_without_pitch_or_duration_shift(self):
        import numpy as np
        # One second of decoder samples, not an already-resampled clip.
        samples = (np.sin(2*np.pi*220*np.arange(24000)/24000)*12000).astype('<i2').tobytes()
        def save(**kwargs):
            AudioSegment(samples, sample_width=2, frame_rate=self.engine.synthesizer.output_sample_rate,
                         channels=1).export(kwargs['file_path'], format='wav').close()
        self.engine.tts_to_file.side_effect = save
        self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))
        clip = load_speech_audio(self.output)
        self.assertEqual(clip.frame_rate, 24000)
        self.assertEqual(len(clip), 1000)
        spectrum = np.abs(np.fft.rfft(np.array(clip.get_array_of_samples(), dtype=float)))
        frequency = np.fft.rfftfreq(len(samples)//2, 1/clip.frame_rate)[spectrum.argmax()]
        self.assertAlmostEqual(frequency, 220, places=1)

    def test_custom_decoder_rate_and_cpu_recovery_are_preserved(self):
        self.engine.synthesizer.tts_model.hifigan_decoder.output_sample_rate = 32000
        self.factory.side_effect = [RuntimeError('GPU unavailable'), self.engine]
        with self.assertLogs(level='WARNING'):
            handler = self.handler('cuda')
        self.assertEqual(handler.tts.synthesizer.output_sample_rate, 32000)

    def test_invalid_decoder_rate_fails_before_generation(self):
        self.engine.synthesizer.tts_model.hifigan_decoder.output_sample_rate = True
        with self.assertRaisesRegex(RuntimeError, 'invalid output sample rate'):
            self.handler()
        self.engine.tts_to_file.assert_not_called()

    def test_silent_generated_speech_preserves_prior_output(self):
        self.write_audio(self.output)
        previous = self.output.read_bytes()
        self.engine.tts_to_file.side_effect = lambda **kw: AudioSegment.silent(
            duration=300).export(kw['file_path'], format='wav').close()
        with self.assertRaisesRegex(RuntimeError, 'digitally silent'):
            self.handler().generate_audio('Hello', str(self.output), reference_audio=str(self.reference))
        self.assertEqual(self.output.read_bytes(), previous)

    def test_source_language_rejected_before_provider_loading(self):
        with patch.object(xtts_local, 'TTSHandler') as constructor:
            with self.assertRaisesRegex(ValueError, 'explicit speech language'):
                xtts_local.XTTSLocalProvider().synthesize('Hello', str(self.output), language='source')
        constructor.assert_not_called()

    def test_wrapper_does_not_invent_success_path(self):
        provider = xtts_local.XTTSLocalProvider()
        provider._handler = Mock()
        provider._handler.generate_audio.side_effect = RuntimeError('failed')
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            provider.synthesize('Hello', str(self.output))

    def test_wrapper_delivers_recovery_warning_to_ui_log(self):
        with patch.object(xtts_local, 'TTSHandler') as factory, patch('bridge.push.emit') as emit:
            provider = xtts_local.XTTSLocalProvider()
            provider.synthesize('Hello', str(self.output))
            factory.call_args.kwargs['warning_callback']('Recovered on CPU')
        emit.assert_called_once_with('log', {'level': 'warning', 'message': 'Recovered on CPU'})


class SegmentTests(SpeechFixture):
    def setUp(self):
        super().setUp()
        self.subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        self.subject.temp_dir = str(self.directory)
        self.subject.registry = Mock()
        self.subject.registry.get_active.return_value = None
        self.subject.registry.list.return_value = []
        self.subject.registry.list.return_value = []
        self.subject.speed_change = lambda clip, speed: clip
        self.tts = Mock()
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path)
        self.master = Mock()
        self.segment = {'start': 0, 'end': 1, 'text': 'Hello'}
        self.voice = Mock()
        self.voice.convert.side_effect = lambda source, dest, **kw: self.write_audio(dest)

    def run_segment(self, actor='CLONED_USER', segment=None, language='en'):
        return self.subject._dub_segment(0, segment or self.segment, [actor], language, self.tts,
                                         {actor: self.voice}, None, str(self.reference), 'cpu', self.master)

    def assert_cleaned(self):
        self.assertFalse(list(self.directory.glob('reflow-segment-*')))

    def test_synthesis_failure_has_segment_context_and_cleans_files(self):
        def failed(text, path, **kw):
            Path(path).write_bytes(b'partial')
            raise RuntimeError('engine broke')
        self.tts.synthesize.side_effect = failed
        with self.assertRaisesRegex(RuntimeError, 'Segment 1.*speech generation.*engine broke'):
            self.run_segment()
        self.assert_cleaned()

    def test_missing_audio_cannot_be_skipped(self):
        self.tts.synthesize.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'Segment 1.*Missing or empty audio'):
            self.run_segment()
        self.assert_cleaned()

    def test_corrupt_generated_audio_has_stage_context(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: Path(path).write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError, 'speech generation.*could not be decoded'):
            self.run_segment()
        self.assert_cleaned()

    def test_repeated_segment_index_uses_fresh_output_folder(self):
        paths = []
        def generate(text, path, **kw):
            paths.append(path)
            self.write_audio(path)
        self.tts.synthesize.side_effect = generate
        self.run_segment()
        self.run_segment()
        self.assertNotEqual(paths[0], paths[1])
        self.assert_cleaned()

    def test_selected_voice_failure_does_not_fall_back(self):
        self.voice.convert.side_effect = RuntimeError('conversion broke')
        with self.assertRaisesRegex(RuntimeError, 'selected voice conversion.*conversion broke'):
            self.run_segment('Chosen actor')
        self.assert_cleaned()

    def test_missing_selected_voice_output_does_not_fall_back(self):
        self.voice.convert.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'selected voice conversion.*Missing or empty audio'):
            self.run_segment('Chosen actor')

    def test_f5_failure_propagates_without_xtts(self):
        self.subject.registry.list.return_value = [{'display_name': 'F5 actor', 'request_preset': 'f5tts'}]
        self.voice.convert.side_effect = RuntimeError('F5 broke')
        with self.assertRaisesRegex(RuntimeError, 'F5 speech generation.*F5 broke'):
            self.run_segment('F5 actor')
        self.tts.synthesize.assert_not_called()
        self.assert_cleaned()

    def test_mastering_failure_is_not_skipped(self):
        self.master.master_voice_segment.side_effect = RuntimeError('mastering broke')
        with self.assertRaisesRegex(RuntimeError, 'mastering.*mastering broke'):
            self.run_segment('Chosen actor')

    def test_generated_voices_share_loudness_treatment_across_languages(self):
        for language in ('en', 'es', 'fr', 'de', 'ja', 'hi'):
            with self.subTest(language=language), patch('core.loudness.normalize_voice_loudness') as normalize:
                self.run_segment(language=language)
                normalize.assert_called_once()
        self.master.master_voice_segment.assert_not_called()

    def test_f5_voice_uses_loudness_without_extra_eq(self):
        self.subject.registry.list.return_value = [{'display_name': 'F5 actor', 'request_preset': 'f5tts'}]
        with patch('core.loudness.normalize_voice_loudness') as normalize:
            self.run_segment('F5 actor')
        normalize.assert_called_once()
        self.master.master_voice_segment.assert_not_called()

    def test_cloned_hindi_normalization_failure_keeps_context_and_cleans(self):
        with patch('core.loudness.normalize_voice_loudness', side_effect=RuntimeError('normalization broke')):
            with self.assertRaisesRegex(RuntimeError, 'Segment 1.*mastering.*normalization broke'):
                self.run_segment(language='hi')
        self.master.master_voice_segment.assert_not_called()
        self.assert_cleaned()

    def test_valid_300ms_line_is_kept(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 300)
        clip = self.run_segment(segment={'start': 0, 'end': .3, 'text': 'Hi'})
        self.assertEqual(len(clip), 300)
        self.assertGreater(clip.rms, 0)
        self.assert_cleaned()

    def test_timing_cannot_cut_away_all_generated_speech(self):
        def delayed_voice(text, path, **kw):
            clip = AudioSegment.silent(duration=1500) + Sine(220).to_audio_segment(duration=500)
            clip.export(path, format='wav').close()
        self.tts.synthesize.side_effect = delayed_voice
        with self.assertRaisesRegex(RuntimeError, 'cannot fit without cutting words'):
            self.run_segment(segment={'start': 0, 'end': 1, 'text': 'Hello'})
        self.assert_cleaned()

    def test_speech_uses_gap_without_unnecessary_acceleration(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 1600)
        self.subject.speed_change = Mock(side_effect=lambda clip, speed: clip)
        clip = self.subject._dub_segment(0, self.segment, ['CLONED_USER'], 'en', self.tts,
            {}, None, str(self.reference), 'cpu', self.master, next_start=2)
        self.assertEqual(len(clip), 1600)
        self.assertEqual(self.subject.speed_change.call_args.args[1], 1.0)
        self.assert_cleaned()

    def test_short_english_speech_is_not_stretched_to_fill_the_window(self):
        self.tts.synthesize.side_effect=lambda text,path,**kw:self.write_audio(path,600)
        self.subject.speed_change=Mock(side_effect=lambda clip,speed:clip)
        clip=self.run_segment()
        self.assertEqual(len(clip),600);self.assertEqual(self.subject.speed_change.call_args.args[1],1.0)

    def test_final_cue_can_use_media_tail_in_sequential_and_parallel_execution(self):
        self.tts.synthesize.side_effect=lambda text,path,**kw:self.write_audio(path,1600)
        for workers in [1,2]:
            with self.subTest(workers=workers):
                track=self.collect_batch([self.segment],workers)
                self.assertEqual(len(track),3000);self.assertGreater(track[1200:1500].rms,0)
                self.assertEqual(track[1800:2500].max,0)

    def test_hindi_short_speech_keeps_approved_pace_in_a_spacious_cue(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 1000)
        self.subject.speed_change = Mock(wraps=pipeline.ReflowPipeline.speed_change.__get__(self.subject))
        clip = self.run_segment(segment={'start': 0, 'end': 2, 'text': 'नमस्ते'}, language='hi')
        self.assertAlmostEqual(len(clip), 1000 / 1.342, delta=70)
        self.assertGreater(clip.rms, 0)
        self.assertEqual(self.subject.speed_change.call_args.args[1], 1.342)
        self.assert_cleaned()

    def test_hindi_uses_gap_without_exceeding_approved_pace(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 1600)
        self.subject.speed_change = Mock(wraps=pipeline.ReflowPipeline.speed_change.__get__(self.subject))
        clip = self.subject._dub_segment(0, self.segment, ['CLONED_USER'], 'hi', self.tts,
            {}, None, str(self.reference), 'cpu', self.master, next_start=2)
        self.assertLess(len(clip), 1300)
        self.assertEqual(self.subject.speed_change.call_args.args[1], 1.342)
        self.assert_cleaned()

    def test_hindi_overlong_words_fail_at_the_approved_pace(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 2000)
        self.subject.speed_change = Mock(wraps=pipeline.ReflowPipeline.speed_change.__get__(self.subject))
        with self.assertRaisesRegex(RuntimeError, 'cannot fit without cutting words'):
            self.run_segment(language='hi')
        self.assertEqual(self.subject.speed_change.call_args.args[1], 1.342)
        self.assert_cleaned()

    def test_review_can_audition_overlong_hindi_without_weakening_render_guard(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 2000)
        self.subject.speed_change = Mock(wraps=pipeline.ReflowPipeline.speed_change.__get__(self.subject))
        clip = self.subject._dub_segment(0, self.segment, ['CLONED_USER'], 'hi', self.tts,
            {}, None, str(self.reference), 'cpu', self.master, allow_overflow=True)
        self.assertGreater(len(clip), 1400)
        self.assertEqual(self.subject.speed_change.call_args.args[1], 1.342)
        with self.assertRaisesRegex(RuntimeError, 'cannot fit without cutting words'):
            self.run_segment(language='hi')
        self.assert_cleaned()

    def test_small_overflow_is_fitted_by_real_tempo_without_word_cutting(self):
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 1050)
        self.subject.speed_change = pipeline.ReflowPipeline.speed_change.__get__(self.subject)
        clip = self.run_segment()
        self.assertLessEqual(len(clip), 1000)
        self.assertGreater(len(clip), 900)
        self.assertGreater(clip.rms, 0)
        self.assert_cleaned()

    def test_overflow_can_discard_silence_but_not_spoken_tail(self):
        def trailing_silence(text, path, **kw):
            (Sine(220).to_audio_segment(duration=500) + AudioSegment.silent(duration=1500)).export(
                path, format='wav').close()
        self.tts.synthesize.side_effect = trailing_silence
        clip = self.run_segment()
        self.assertEqual(len(clip), 1000)
        self.assertGreater(clip.max, 0)
        self.tts.synthesize.side_effect = lambda text, path, **kw: self.write_audio(path, 2000)
        with self.assertRaisesRegex(RuntimeError, 'cannot fit without cutting words'):
            self.run_segment()
        self.assert_cleaned()

    def test_blank_gap_is_skipped(self):
        self.assertIsNone(self.run_segment(segment={'start': 0, 'end': 1, 'text': ' '}))
        self.tts.synthesize.assert_not_called()

    def test_bad_timing_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'timing validation'):
            self.run_segment(segment={'start': 1, 'end': 0, 'text': 'Hello'})

    def collect_batch(self, transcript, workers):
        gen = self.subject._dub_all_segments(transcript, ['CLONED_USER'], 'en', self.tts, {},
                                             None, str(self.reference), 'cpu', self.master, 3, 45, 30,
                                             max_workers=workers)
        while True:
            try:
                next(gen)
            except StopIteration as end:
                return end.value

    def test_empty_or_blank_transcript_fails_clearly(self):
        for transcript in ([], [{'start': 0, 'end': 1, 'text': ' '} ]):
            with self.assertRaisesRegex(RuntimeError, 'No dialogue detected'):
                self.collect_batch(transcript, 1)

    def test_empty_transcription_stops_before_translation(self):
        with patch.object(pipeline.providers, 'resolve_stt') as stt, \
                patch.object(pipeline.providers, 'resolve_translation') as translate:
            stt.return_value.transcribe.return_value = []
            with self.assertRaisesRegex(RuntimeError, 'No dialogue detected'):
                self.subject._transcribe_and_translate(str(self.reference), 'hi', {})
        translate.assert_not_called()

    def test_failures_propagate_in_sequential_and_segment_workers(self):
        self.tts.synthesize.side_effect = RuntimeError('synthesis broke')
        transcript = [self.segment, {'start': 1, 'end': 2, 'text': 'Second'}]
        for workers in (1, 2):
            with self.subTest(workers=workers), self.assertRaisesRegex(RuntimeError, 'speech generation.*synthesis broke'):
                self.collect_batch(transcript, workers)
            self.assert_cleaned()

    def test_successful_assembly_has_dialogue_and_keeps_blank_gaps(self):
        transcript = [self.segment, {'start': 1, 'end': 2, 'text': ' '}, {'start': 2, 'end': 3, 'text': 'Second'}]
        for workers in (1, 2):
            with self.subTest(workers=workers):
                track = self.collect_batch(transcript, workers)
                self.assertGreater(track[:900].rms, 0)
                self.assertEqual(track[1100:1900].rms, 0)
                self.assertGreater(track[2100:2900].rms, 0)
                self.assert_cleaned()


class RVCTests(SpeechFixture):
    def test_successful_initialization_on_cp1252_console(self):
        import io
        factory = Mock()
        console_bytes = io.BytesIO()
        console = io.TextIOWrapper(console_bytes, encoding='cp1252')
        with patch.dict(sys.modules, {
                'rvc_python.infer': SimpleNamespace(RVCInference=factory),
                'core.model_assets': SimpleNamespace(ensure_assets=Mock()),
        }), patch('sys.stdout', console):
            handler = RVCHandler(device='cpu')
        console.flush()
        self.assertTrue(handler.ready)
        self.assertIn(b'RVC System Online', console_bytes.getvalue())
        factory.assert_called_once_with(device='cpu')

    def setUp(self):
        super().setUp()
        self.models = self.directory / 'models'
        self.weights = self.models / 'rvc/weights'
        self.weights.mkdir(parents=True)
        import torch
        torch.save({'config': [0] * 17 + [40000], 'version': 'v2',
                    'weight': {'emb_g.weight': torch.zeros(1, 256),
                               'enc_p.emb_phone.weight': torch.zeros(1, 768)}}, self.weights / 'Actor.pth')
        self.stack.enter_context(patch.object(config, 'MODELS_DIR', str(self.models)))
        self.handler = RVCHandler.__new__(RVCHandler)
        self.handler.ready = True
        self.handler.inference = SimpleNamespace(load_model=Mock(), set_params=Mock())
        self.calls = []
        def infer(input_path, output_path):
            self.calls.append((input_path, output_path))
            self.write_audio(output_path)
        self.handler.inference.infer_file = infer

    def test_unready_rvc_fails(self):
        self.handler.ready = False
        with self.assertRaisesRegex(RuntimeError, 'not initialized'):
            self.handler.infer(str(self.reference), str(self.output), 'Actor')

    def test_missing_checkpoint_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'checkpoint is missing'):
            self.handler.infer(str(self.reference), str(self.output), 'Missing actor')

    def test_real_preprocessing_and_mocked_inference_success(self):
        result = self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(result, str(self.output))
        self.assertGreater(len(load_playable_audio(result)), 0)
        self.handler.inference.set_params.assert_called_once_with(f0up_key=0)
        self.assertFalse((self.directory / 'reference_16k.wav').exists())

    def test_internal_typeerror_is_not_retried(self):
        def infer(input_path, output_path):
            self.calls.append(1)
            Path(output_path).write_bytes(b'partial')
            raise TypeError('internal inference bug')
        self.handler.inference.infer_file = infer
        with self.assertRaisesRegex(RuntimeError, 'internal inference bug'):
            self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.directory / 'reference_16k.wav').exists())

    def test_failed_rvc_preserves_prior_output_and_preprocessing_sibling(self):
        self.write_audio(self.output)
        previous = self.output.read_bytes()
        sibling = self.directory / 'reference_16k.wav'
        sibling.write_bytes(b'user file')
        def failed(input_path, output_path):
            Path(output_path).write_bytes(b'partial')
            raise RuntimeError('conversion failed')
        self.handler.inference.infer_file = failed
        with self.assertRaisesRegex(RuntimeError, 'conversion failed'):
            self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertEqual(sibling.read_bytes(), b'user file')

    def test_rvc_reuses_loaded_model_until_checkpoint_changes(self):
        self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(self.handler.inference.load_model.call_count, 1)
        checkpoint = self.directory / 'rvc/weights/Actor.pth'
        if not checkpoint.exists():
            checkpoint = Path(self.handler.inference.load_model.call_args.args[0])
        checkpoint.write_bytes(checkpoint.read_bytes() + b'changed')
        self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(self.handler.inference.load_model.call_count, 2)

    def test_keyword_pitch_api_is_selected_without_retry(self):
        seen = []
        def infer(input_path, output_path, f0_up_key=0):
            seen.append(f0_up_key)
            self.write_audio(output_path)
        self.handler.inference.infer_file = infer
        self.handler.infer(str(self.reference), str(self.output), 'Actor', pitch_change=2)
        self.assertEqual(seen, [2])
        self.handler.inference.set_params.assert_not_called()

    def test_missing_inference_output_fails(self):
        self.handler.inference.infer_file = lambda input_path, output_path: None
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
            self.handler.infer(str(self.reference), str(self.output), 'Actor')

    def test_preprocessing_failure_has_no_input_fallback(self):
        self.stack.enter_context(patch.object(pipeline, '_run_ffmpeg', side_effect=RuntimeError('ffmpeg broke')))
        with self.assertRaisesRegex(RuntimeError, 'ffmpeg broke'):
            self.handler.infer(str(self.reference), str(self.output), 'Actor')
        self.assertEqual(self.calls, [])

    def test_engine_initialization_failure_propagates_without_download(self):
        with patch.dict(sys.modules, {'rvc_python.infer': SimpleNamespace(RVCInference=Mock(side_effect=RuntimeError('load broke')))}), \
                patch('core.model_assets.ensure_assets') as assets:
            with self.assertRaisesRegex(RuntimeError, 'initialization failed.*load broke'):
                RVCHandler(device='cpu')
        assets.assert_called_once_with('rvc')

    def test_wrapper_propagates_failure(self):
        provider = rvc_local.RVCLocalProvider()
        provider._handler = Mock()
        provider._handler.infer.side_effect = RuntimeError('voice failed')
        with self.assertRaisesRegex(RuntimeError, 'voice failed'):
            provider.convert(str(self.reference), str(self.output), 'Actor')


class F5Tests(SpeechFixture):
    def setUp(self):
        super().setUp()
        # These tests exercise the deliberately mocked in-process engine;
        # separately installed optional runtimes must not change that fixture.
        self.stack.enter_context(patch('core.optional_runtime.interpreter', return_value=None))
        self.stack.enter_context(patch('core.feature_worker.prepare_f5_reference',
                                      return_value=(str(self.reference), 'Reference speech.')))

    def test_missing_engine_output_fails(self):
        provider = f5tts_local.F5TTSVoiceProvider()
        provider._f5tts = Mock()
        provider._f5tts.infer.return_value = (None, None, None)
        self.write_audio(self.output)
        with self.assertRaisesRegex(RuntimeError, 'Missing or empty audio'):
            provider.convert(None, str(self.output), 'Actor', text='Hello', reference_audio=str(self.reference))

    def test_valid_mocked_engine_output_succeeds(self):
        provider = f5tts_local.F5TTSVoiceProvider()
        provider._f5tts = Mock()
        def infer(**kwargs):
            self.write_audio(kwargs['file_wave'])
            return None, None, None
        provider._f5tts.infer.side_effect = infer
        self.assertEqual(provider.convert(None, str(self.output), 'Actor', text='Hello', reference_audio=str(self.reference)), str(self.output))


if __name__ == '__main__':
    unittest.main(verbosity=2)
