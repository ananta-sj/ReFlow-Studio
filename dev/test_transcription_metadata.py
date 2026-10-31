"""Transcription metadata tests; no real Whisper model or network calls."""
from contextlib import ExitStack
import importlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core.transcription import TranscriptionResult, normalize_transcription
from core.providers.stt import cloud_rest as cloud, whisper_local as local
import pipeline
with patch.dict(sys.modules, {'faster_whisper': SimpleNamespace(WhisperModel=Mock())}):
    handler = importlib.import_module('stt.stt_handler')

SEGMENTS = [{'start': 0.0, 'end': 1.0, 'text': 'Hello'},
            {'start': 1.1, 'end': 2.0, 'text': 'world'}]


def envelope(language='hi', probability=0.91):
    return {'segments': SEGMENTS, 'language': language, 'language_probability': probability}


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


class MetadataTests(unittest.TestCase):
    def test_transcription_must_fit_decoded_media(self):
        from core.transcription import require_media_bounds
        require_media_bounds(SEGMENTS, 2)
        for segment in ({'start': 8, 'end': 11, 'text': 'hallucination'},
                        {'start': float('nan'), 'end': 1}, {'start': True, 'end': 1},
                        {'start': 1, 'end': .5}, {'start': -1, 'end': 1}):
            with self.assertRaises(ValueError):
                require_media_bounds([segment], 8)
    def test_list_compatibility_and_payload_round_trip(self):
        result = normalize_transcription(envelope())
        self.assertIsInstance(result, list)
        self.assertEqual(result, SEGMENTS)
        self.assertEqual(result[0]['text'], 'Hello')
        self.assertEqual(len(result), 2)
        recovered = normalize_transcription(json.loads(json.dumps(result.to_payload())))
        self.assertEqual(recovered.language, 'hi')
        self.assertEqual(recovered.language_probability, 0.91)
        self.assertEqual(recovered, SEGMENTS)

    def test_legacy_list_is_unknown_not_english(self):
        result = normalize_transcription(SEGMENTS)
        self.assertIsNone(result.language)
        self.assertIsNone(result.language_probability)

    def test_envelope_without_metadata_is_compatible(self):
        result = normalize_transcription({'segments': SEGMENTS})
        self.assertIsNone(result.language)
        self.assertIsNone(result.language_probability)

    def test_raw_language_labels_are_retained_without_guessing_aliases(self):
        for language in ('English', 'pa', 'unknown-provider-label', 'hi-en'):
            self.assertEqual(normalize_transcription(envelope(language)).language, language)

    def test_probability_endpoints_and_unknown_are_preserved(self):
        for probability in (0, 1, 0.5, None):
            self.assertEqual(normalize_transcription(envelope(probability=probability)).language_probability, probability)

    def test_invalid_probabilities_become_unknown_with_warning(self):
        for probability in (True, False, '0.9', [], {}, float('nan'), float('inf'), -0.1, 1.1, 10**400):
            with self.subTest(probability=probability), self.assertLogs(level='WARNING'):
                result = normalize_transcription(envelope(probability=probability))
            self.assertEqual(result.language, 'hi')
            self.assertIsNone(result.language_probability)
            self.assertEqual(result, SEGMENTS)

    def test_invalid_language_becomes_unknown(self):
        for language in ('', '  ', 42, [], True):
            with self.subTest(language=language), self.assertLogs(level='WARNING'):
                result = normalize_transcription(envelope(language))
            self.assertIsNone(result.language)
            self.assertIsNone(result.language_probability)

    def test_probability_without_language_is_not_invented(self):
        self.assertIsNone(normalize_transcription(envelope(None)).language_probability)

    def test_malformed_segment_shapes_are_explicit_errors(self):
        for payload in (None, 42, {}, {'segments': None}, {'segments': {}}, ['text'], [{}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize_transcription(payload)

    def test_result_copies_segment_dicts_and_preserves_extra_fields(self):
        original = [{'start': 0, 'end': 1, 'text': 'Hello', 'speaker': 'A'}]
        result = normalize_transcription(original)
        result[0]['text'] = 'Changed'
        self.assertEqual(original[0]['text'], 'Hello')
        self.assertEqual(result[0]['speaker'], 'A')

    def test_with_segments_keeps_metadata(self):
        original = normalize_transcription(envelope())
        replaced = original.with_segments([{'start': 0, 'end': 2, 'text': 'Hello world'}])
        self.assertEqual(replaced.language, original.language)
        self.assertEqual(replaced.language_probability, original.language_probability)
        self.assertEqual(len(original), 2)
        self.assertEqual(len(replaced), 1)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.audio = self.directory / 'input.wav'
        self.audio.write_bytes(b'mocked-audio')

    def worker_payload(self, payload):
        def run(command, **kwargs):
            Path(command[4]).write_text(json.dumps(payload), encoding='utf-8')
        return run

    def test_local_worker_envelope_is_preserved(self):
        with patch.object(local.subprocess, 'run', side_effect=self.worker_payload(envelope())) as run:
            result = local.WhisperLocalProvider('mock').transcribe(str(self.audio))
        self.assertEqual(result.language, 'hi')
        self.assertEqual(result.language_probability, 0.91)
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertEqual(run.call_args.kwargs['timeout'], 3600)
        self.assertFalse(Path(run.call_args.args[0][4]).exists())

    def test_local_legacy_worker_list_remains_compatible(self):
        with patch.object(local.subprocess, 'run', side_effect=self.worker_payload(SEGMENTS)):
            result = local.WhisperLocalProvider().transcribe(str(self.audio))
        self.assertEqual(result, SEGMENTS)
        self.assertIsNone(result.language)

    def test_local_worker_failure_propagates(self):
        with patch.object(local.subprocess, 'run', side_effect=RuntimeError('worker failed')), self.assertRaisesRegex(RuntimeError, 'worker failed'):
            local.WhisperLocalProvider().transcribe(str(self.audio))

    def test_local_malformed_worker_response_fails(self):
        with patch.object(local.subprocess, 'run', side_effect=self.worker_payload({})), self.assertRaises(ValueError):
            local.WhisperLocalProvider().transcribe(str(self.audio))

    def test_cloud_presets_preserve_metadata(self):
        for request in (cloud._custom_request, cloud._openai_whisper_request):
            with patch.object(cloud, 'request', return_value=response(envelope('Hindi', None))):
                result = request('http://example.invalid', 'mock-key', str(self.audio), {})
            self.assertEqual(result.language, 'Hindi')
            self.assertIsNone(result.language_probability)
            self.assertEqual(result, SEGMENTS)

    def test_cloud_custom_legacy_list_remains_compatible(self):
        with patch.object(cloud, 'request', return_value=response(SEGMENTS)):
            result = cloud._custom_request('http://example.invalid', None, str(self.audio), {})
        self.assertEqual(result, SEGMENTS)
        self.assertIsNone(result.language)

    def test_cloud_metadata_free_envelope_remains_compatible(self):
        with patch.object(cloud, 'request', return_value=response({'segments': SEGMENTS})):
            result = cloud._openai_whisper_request('http://example.invalid', 'key', str(self.audio), {})
        self.assertIsNone(result.language)

    def test_cloud_malformed_response_is_explicit_error(self):
        for request in (cloud._custom_request, cloud._openai_whisper_request):
            with patch.object(cloud, 'request', return_value=response({'error': 'bad response'})), self.assertRaises(ValueError):
                request('http://example.invalid', 'key', str(self.audio), {})

    def test_actual_handler_collects_generator_metadata_without_loading_model(self):
        subject = handler.STTHandler.__new__(handler.STTHandler)
        subject.model = Mock()
        subject.model.transcribe.return_value = (iter(SimpleNamespace(**segment) for segment in SEGMENTS), SimpleNamespace(language='hi', language_probability=0.91))
        result = subject.transcribe(str(self.audio))
        self.assertEqual(result, SEGMENTS)
        self.assertEqual(result.language, 'hi')
        self.assertEqual(result.language_probability, 0.91)
        self.assertFalse(hasattr(subject, 'model'))

    def test_actual_handler_missing_metadata_is_unknown(self):
        subject = handler.STTHandler.__new__(handler.STTHandler)
        subject.model = Mock()
        subject.model.transcribe.return_value = (iter([]), SimpleNamespace())
        result = subject.transcribe(str(self.audio))
        self.assertEqual(result, [])
        self.assertIsNone(result.language)

    def test_worker_script_writes_metadata_envelope(self):
        output = self.directory / 'transcript.json'
        engine = Mock()
        engine.transcribe.return_value = normalize_transcription(envelope())
        fake_handler = SimpleNamespace(STTHandler=Mock(return_value=engine))
        with patch.dict(sys.modules, {'stt.stt_handler': fake_handler}), patch.object(sys, 'argv', ['run_stt.py', str(self.audio), str(output), 'mock']), patch.object(sys, 'stdout', io.StringIO()):
            runpy.run_path(str(ROOT / 'core' / 'run_stt.py'), run_name='__main__')
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), envelope())

    def test_worker_script_accepts_legacy_handler_list(self):
        output = self.directory / 'transcript.json'
        engine = Mock()
        engine.transcribe.return_value = SEGMENTS
        with patch.dict(sys.modules, {'stt.stt_handler': SimpleNamespace(STTHandler=Mock(return_value=engine))}), patch.object(sys, 'argv', ['run_stt.py', str(self.audio), str(output)]), patch.object(sys, 'stdout', io.StringIO()):
            runpy.run_path(str(ROOT / 'core' / 'run_stt.py'), run_name='__main__')
        result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(result['segments'], SEGMENTS)
        self.assertIsNone(result['language'])


class PipelineMetadataTests(unittest.TestCase):
    def setUp(self):
        self.subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        self.subject.registry = Mock()
        self.subject.registry.get_active.return_value = None
        self.stt = Mock()

    def test_source_metadata_survives_real_short_segment_merge(self):
        self.stt.transcribe.return_value = envelope()
        result = self.subject._transcribe_source(self.stt, 'mock.wav')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'Hello world')
        self.assertEqual(result.language, 'hi')
        self.assertEqual(result.language_probability, 0.91)

    def test_legacy_provider_remains_unknown(self):
        self.stt.transcribe.return_value = SEGMENTS
        result = self.subject._transcribe_source(self.stt, 'mock.wav')
        self.assertIsNone(result.language)
        self.assertIsNone(result.language_probability)

    def test_metadata_survives_translation_text_replacement(self):
        self.stt.transcribe.return_value = envelope()
        translator = Mock()
        translator.translate.return_value = 'Bonjour'
        with patch.object(pipeline.providers, 'resolve_stt', return_value=self.stt), patch.object(self.subject, '_resolve_translation_and_filter', return_value=(translator, '', None, '')):
            result = self.subject._transcribe_and_translate('mock.wav', 'fr', {})
        self.assertEqual(result[0]['text'], 'Bonjour')
        self.assertEqual(result.language, 'hi')
        self.assertEqual(result.language_probability, 0.91)
        translator.translate.assert_called_once()
        self.assertEqual(translator.translate.call_args.kwargs['source_language'].code, 'hi')
        self.assertEqual(translator.translate.call_args.kwargs['source_language'].probability, 0.91)

    def test_source_bypass_preserves_metadata_without_translating(self):
        self.stt.transcribe.return_value = envelope()
        with patch.object(pipeline.providers, 'resolve_stt', return_value=self.stt), patch.object(self.subject, '_resolve_translation_and_filter') as resolve:
            result = self.subject._transcribe_and_translate('mock.wav', 'source', {})
        resolve.assert_not_called()
        self.assertEqual(result.language, 'hi')

    def test_sequential_results_do_not_share_metadata(self):
        self.stt.transcribe.side_effect = [envelope(), SEGMENTS]
        first = self.subject._transcribe_source(self.stt, 'one.wav')
        second = self.subject._transcribe_source(self.stt, 'two.wav')
        self.assertEqual(first.language, 'hi')
        self.assertIsNone(second.language)

    def test_empty_dialogue_still_fails(self):
        self.stt.transcribe.return_value = {'segments': [], 'language': 'hi', 'language_probability': 0.91}
        with self.assertRaisesRegex(RuntimeError, 'No dialogue'):
            self.subject._transcribe_source(self.stt, 'mock.wav')

    def test_long_sentence_continuation_uses_complete_source_window(self):
        source = [dict(start=0, end=4.92, text="Before long, a news language became immediately"),
                  dict(start=4.92, end=6.3, text="recognisable to anyone."),
                  dict(start=6.66, end=8.28, text="Me, has this report.")]
        result = self.subject._merge_short_segments(source, allow_sentence_continuations=True)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['end'], 6.3)
        self.assertTrue(result[0]['text'].endswith('recognisable to anyone.'))
        self.assertEqual(source[0]['end'], 4.92)
        self.assertEqual(source[0]['text'], 'Before long, a news language became immediately')

    def test_sentence_join_respects_boundaries(self):
        cases = [
            ('Finished sentence.', 'lowercase next.', 4, 5, {}),
            ('Finished sentence.”', 'lowercase next.', 4, 5, {}),
            ('Finished sentence।', 'lowercase next.', 4, 5, {}),
            ('Unfinished thought', 'New thought.', 4, 5, {}),
            ('Unfinished thought', 'continuation.', 4.7, 6, {}),
            ('Unfinished thought', 'continuation.', 4, 9.1, {}),
            ('Unfinished thought', 'continuation.', 3.9, 5, {}),
            ('Unfinished thought', 'continuation.', 4, 5, {'speaker_id': 'second'}),
        ]
        for first, second, start, end, metadata in cases:
            with self.subTest(first=first, start=start, end=end, metadata=metadata):
                source = [dict(start=0, end=4, text=first),
                          dict(start=start, end=end, text=second, **metadata)]
                self.assertEqual(len(self.subject._merge_short_segments(
                    source, allow_sentence_continuations=True)), 2)

    def test_short_join_does_not_cross_known_speaker_change(self):
        source = [dict(start=0, end=1, text='Hello', speaker='one'),
                  dict(start=1, end=2, text='world', speaker='two')]
        self.assertEqual(len(self.subject._merge_short_segments(source)), 2)

    def test_multi_voice_keeps_long_cue_assignments(self):
        source = [dict(start=0, end=4, text='An unfinished thought'),
                  dict(start=4, end=6, text='continues here.')]
        self.stt.transcribe.return_value = source
        with patch.object(pipeline.providers, 'resolve_stt', return_value=self.stt), \
                patch.object(self.subject, '_check_speech_routes'), \
                patch.object(self.subject, '_moderate_source'):
            multi = self.subject._transcribe_and_translate('mock.wav', 'source', {},
                source_language='en', speech_cast=['voice1', 'voice2'])
            single = self.subject._transcribe_and_translate('mock.wav', 'source', {},
                source_language='en', speech_cast=['voice1'])
        self.assertEqual(len(multi), 2)
        self.assertEqual(len(single), 1)

    def test_sentence_join_retains_detected_language(self):
        self.stt.transcribe.return_value = {'segments': [
            dict(start=0, end=4, text='An unfinished thought'),
            dict(start=4, end=6, text='continues here.')],
            'language': 'en', 'language_probability': 0.97}
        result = self.subject._transcribe_source(self.stt, 'mock.wav', True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.language, 'en')
        self.assertEqual(result.language_probability, 0.97)


if __name__ == '__main__':
    unittest.main(verbosity=2)
