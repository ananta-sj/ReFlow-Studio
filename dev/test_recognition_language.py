"""Source hints must reach inference and cannot masquerade as detection."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from core.recognition_language import whisper_language
from core.transcription import TranscriptionResult, normalize_transcription
from core.stage_checkpoints import recognition_inputs, digest
from core.providers.stt.cloud_rest import STTCloudRestProvider
from core.providers.stt.whisper_local import WhisperLocalProvider
from core.pipeline import ReflowPipeline
from core.source_language import resolve_source_language


class RecognitionLanguageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'temp')
        self.addCleanup(self.folder.cleanup)
        self.audio = Path(self.folder.name)/'source.wav'
        with wave.open(str(self.audio), 'wb') as stream:
            stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            stream.writeframes(b'\0\0'*16000)
        self.segments = [dict(start=0, end=1, text='नमस्ते।')]

    def test_token_aliases_and_invalid_selection(self):
        for selection, expected in [('auto', None), (None, None), ('Hindi', 'hi'),
                                    ('zh-Hant', 'zh'), ('pa-Guru', 'pa'), ('jv', 'jw')]:
            self.assertEqual(whisper_language(selection), expected)
        with self.assertRaises(ValueError):
            whisper_language('invented')

    def test_forced_probability_removed_through_json_and_resegmentation(self):
        raw = dict(segments=self.segments, language='hi', language_probability=1, language_origin='hint')
        result = normalize_transcription(json.loads(json.dumps(raw))).with_segments(self.segments)
        self.assertEqual(result.language_origin, 'hint')
        self.assertIsNone(result.language_probability)
        self.assertEqual(result.to_payload()['language_origin'], 'hint')
        subject = ReflowPipeline.__new__(ReflowPipeline)
        subject.source_language_callback = Mock()
        subject._report_source_language(resolve_source_language('hi'), result)
        payload = subject.source_language_callback.call_args.args[0]
        self.assertEqual(payload['source_code'], 'hi')
        self.assertIsNone(payload['detected_name'])
        self.assertIsNone(payload['probability'])

    def test_checkpoint_inputs_distinguish_auto_hindi_french(self):
        provider = Mock(prefers_sentence_groups=True)
        identities = [recognition_inputs(self.audio, True, provider, selection)
                      for selection in ['auto', 'hi', 'fr']]
        self.assertEqual(len({digest(value) for value in identities}), 3)
        self.assertEqual(identities[1], recognition_inputs(self.audio, True, provider, 'Hindi'))

    def test_pipeline_passes_hint_and_keeps_auto_call_compatible(self):
        subject = ReflowPipeline.__new__(ReflowPipeline)
        subject._save_cues = Mock()
        provider = Mock()
        provider.transcribe.return_value = TranscriptionResult(self.segments, 'hi', .9)
        for selected, kwargs in [('hi', {'source_language': 'hi'}), ('auto', {})]:
            subject._transcribe_source(provider, str(self.audio), source_language=selected)
            provider.transcribe.assert_called_with(str(self.audio), **kwargs)

    def test_local_provider_worker_argument_and_envelope(self):
        def worker(command, **kwargs):
            self.assertEqual(command[-1], 'hi')
            Path(command[4]).write_text(json.dumps(dict(segments=self.segments, language='hi',
                language_probability=1, language_origin='hint')), encoding='utf-8')
        with patch('core.providers.stt.whisper_local.run_process', side_effect=worker):
            result = WhisperLocalProvider('existing-model').transcribe(str(self.audio), source_language='hi')
        self.assertIsNone(result.language_probability)
        self.assertEqual(result.language_origin, 'hint')

    def test_cloud_hint_transmission_and_saved_extras_unchanged(self):
        for preset, extra, expected in [('openai_whisper', {}, 'language'),
                                        ('custom', {'language_field': 'source'}, 'source')]:
            provider = STTCloudRestProvider('http://example.invalid', None, preset, extra)
            with patch('core.providers.stt.cloud_rest.request') as request:
                request.return_value.json.return_value = dict(segments=self.segments, language='hi', language_probability=1)
                result = provider.transcribe(str(self.audio), source_language='hi')
                self.assertEqual(request.call_args.kwargs['data'][expected], 'hi')
                self.assertIsNone(result.language_probability)
                self.assertEqual(result.language_origin, 'hint')
            self.assertEqual(provider.extra, extra)

    def test_custom_cannot_silently_ignore_hint(self):
        provider = STTCloudRestProvider('http://example.invalid', None)
        with patch('core.providers.stt.cloud_rest.request') as request:
            with self.assertRaisesRegex(ValueError, 'language_field'):
                provider.transcribe(str(self.audio), source_language='hi')
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
