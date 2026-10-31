"""Stronger ASR selection, lifetime, language metadata and sentence integrity."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from core.providers.stt.whisper_turbo_local import WhisperTurboLocalProvider
from core.providers import resolve
from core.transcription import TranscriptionResult
from core.sentence_grouping import group_sentences
from core.render_context import RenderContext, bind_job
from core.model_registry import ModelRegistry
from dev.test_render_queue import api

ROOT = Path(__file__).resolve().parents[1]


class WhisperTurboIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT/'temp')))
        self.audio = self.root/'source.wav'
        self.audio.write_bytes(b'worker fixture input')
        self.stack.enter_context(patch('core.providers.stt.whisper_turbo_local.validate_assets',return_value={'adapter':'whisper_turbo'}))
        self.stack.enter_context(patch('core.providers.stt.whisper_turbo_local.isolated_interpreter',return_value='fixture-python'))
        self.worker = self.stack.enter_context(patch('core.feature_session.FeatureSession'))
        self.provider = WhisperTurboLocalProvider('fixture')
        self.worker.return_value.finished.is_set.return_value = True

    def test_metadata_is_actual_and_worker_closes_before_return(self):
        self.worker.return_value.call.return_value = dict(duration_seconds=2,
            transcription=dict(segments=[dict(start=0,end=1,text='Hello.')],language='en',language_probability=.93))
        job = RenderContext(self.root)
        try:
            with bind_job(job):
                result = self.provider.transcribe(self.audio)
            self.assertEqual((result.language,result.language_probability),('en',.93))
            self.assertTrue(self.provider.worker_released)
            self.worker.return_value.close.assert_called_once()
        finally:
            job.cleanup()

    def test_failure_and_bad_timestamps_close_worker(self):
        for response in [RuntimeError('inference failed'),dict(duration_seconds=1,
            transcription=dict(segments=[dict(start=0,end=2,text='Hello')]))]:
            with self.subTest(response=response):
                worker = self.worker.return_value
                worker.close.reset_mock()
                worker.call.side_effect = response if isinstance(response,Exception) else None
                worker.call.return_value = response
                with self.assertRaises((RuntimeError,ValueError)):
                    self.provider.transcribe(self.audio)
                worker.close.assert_called_once()

    def test_explicit_hint_survives_owned_job_recursion_and_worker_json(self):
        self.worker.return_value.call.return_value = dict(duration_seconds=2,
            transcription=dict(segments=[dict(start=0,end=1,text='नमस्ते।')],
                               language='hi',language_probability=1,language_origin='hint'))
        result = self.provider.transcribe(self.audio, source_language='Hindi')
        self.worker.return_value.call.assert_called_once_with(dict(audio_path=str(self.audio), source_language='hi'))
        self.assertEqual(result.language_origin, 'hint')
        self.assertIsNone(result.language_probability)
        self.worker.return_value.close.assert_called_once()

    def test_nonspoken_recognition_closes_worker_and_retains_raw_evidence(self):
        self.worker.return_value.call.return_value = dict(duration_seconds=2,
            transcription=dict(segments=[dict(start=0,end=1,text='.')],language='en',language_probability=.38))
        with self.assertRaisesRegex(ValueError,'No spoken words'):
            self.provider.transcribe(self.audio)
        self.worker.return_value.close.assert_called_once()
        self.assertEqual(self.provider.last_result['transcription']['segments'][0]['text'],'.')

    def test_resolver_never_loads_faster_whisper_for_strong_contract(self):
        registry = Mock()
        registry.get_active.return_value = dict(kind='local_file',stage_type='stt',local_path='fixture')
        with patch.object(resolve,'_local',return_value={'adapter':'whisper_turbo'}):
            self.assertIsInstance(resolve.resolve_stt(registry,'tiny'),WhisperTurboLocalProvider)


class SentenceGroupingTests(unittest.TestCase):
    def test_punctuation_only_recognition_is_not_sent_to_translation(self):
        from core.transcription import require_spoken_transcription
        for text in ['.', '…', '।!?', ' 🎵 ', '   ']:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError,'No spoken words'):
                require_spoken_transcription(TranscriptionResult([dict(start=0,end=1,text=text)],'en',.38))

    def test_lexical_unicode_recognition_preserves_original_words_and_metadata(self):
        from core.transcription import require_spoken_transcription
        source = TranscriptionResult([dict(start=0,end=1,text='.'),dict(start=1,end=2,text='नमस्ते!'),
            dict(start=2,end=3,text='你好。'),dict(start=3,end=4,text='١٢٣')],'hi',.95)
        result = require_spoken_transcription(source)
        self.assertEqual([row['text'] for row in result],['नमस्ते!','你好。','١٢٣'])
        self.assertEqual((result.language,result.language_probability),('hi',.95))
        self.assertEqual(len(source),4)

    def test_decoder_completion_uses_underlying_output_not_trimmed_timestamp_tokens(self):
        from core.whisper_completion import require_finished_decoder
        require_finished_decoder([50258,50259,50359,100,50257],2,50257)
        for tokens,steps in [([100,50257],440),([100,50364],2),([],2),([100,50257],0)]:
            with self.subTest(tokens=tokens,steps=steps),self.assertRaises(ValueError):
                require_finished_decoder(tokens,steps,50257)
    def test_long_sentence_is_complete_and_short_finished_line_stays_separate(self):
        cues = [dict(start=0,end=2,text='Hi.'),dict(start=2,end=8,text='A sentence ending in'),
                dict(start=8,end=16,text='a continuation.'),dict(start=16,end=17,text='Bye.')]
        result = group_sentences(TranscriptionResult(cues,'en',.99))
        self.assertEqual(len(result),3)
        self.assertEqual(result[1]['text'],'A sentence ending in a continuation.')
        self.assertEqual(result[1]['end'],16)
        self.assertEqual(result[1]['source_fragments'],cues[1:3])
        self.assertEqual(cues[1]['text'],'A sentence ending in')

    def test_gap_speaker_and_length_limits_prevent_unsafe_join(self):
        for start,end,metadata in [(4.7,5,{}),(4,31,{}),(4,5,{'speaker_id':'other'})]:
            source = TranscriptionResult([dict(start=0,end=4,text='Unfinished thought'),
                                          dict(start=start,end=end,text='continues.',**metadata)],'en',.99)
            self.assertEqual(len(group_sentences(source)),2)

    def test_block_boundary_join_retains_original_punctuation_in_provenance(self):
        source = TranscriptionResult([dict(start=27,end=30,text='The facts and not.'),
            dict(start=30,end=35,text='what people think.',asr_block_boundary=True)],'en',.99)
        result = group_sentences(source)
        self.assertEqual(result[0]['text'],'The facts and not what people think.')
        self.assertTrue(result[0]['boundary_punctuation_join'])
        self.assertEqual(result[0]['source_fragments'][0]['text'],'The facts and not.')
        self.assertEqual(source[0]['text'],'The facts and not.')

    def test_final_unfinished_phrase_is_retained_for_review(self):
        result = group_sentences(TranscriptionResult([dict(start=0,end=3,text='Unfinished tail')],'en',.9))
        self.assertTrue(result[0]['incomplete_sentence_tail'])
        self.assertEqual(result[0]['text'],'Unfinished tail')


class WhisperConnectionTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(dir=ROOT/'temp')))
        (self.root/'model.safetensors').write_bytes(b'fixture')
        self.stack.enter_context(patch('core.model_registry.REGISTRY_PATH',str(self.root/'registry.json')))
        self.stack.enter_context(patch('core.whisper_turbo_assets.installed_path',return_value=self.root))
        self.validation = self.stack.enter_context(patch('core.whisper_turbo_assets.validate_assets',return_value={'revision':'pinned'}))
        self.stack.enter_context(patch('core.whisper_turbo_assets.isolated_interpreter',return_value='fixture-python'))
        self.bridge = api.PythonBridge.__new__(api.PythonBridge)
        self.bridge.registry = ModelRegistry()
        self.bridge._render_lock = threading.Lock()
        self.bridge._deletion_busy = Mock(return_value=False)

    def test_connect_preserves_selection_reuses_entry_and_reports_gpu_route(self):
        old = self.bridge.registry.add('stt','cloud_api','Existing recognizer')
        first = self.bridge.connect_whisper_turbo()
        self.assertTrue(first['ok'],first)
        self.assertEqual(first['model']['id'],self.bridge.connect_whisper_turbo()['model']['id'])
        self.assertEqual(self.bridge.registry.get_active('stt')['id'],old['id'])
        self.bridge.registry.set_active('stt',first['model']['id'])
        self.assertEqual(self.bridge._estimate_routes('cpu',{'cast_list':['CLONED_USER']})['stt'],'cuda:0')

    def test_busy_or_invalid_assets_cannot_add_connection(self):
        self.bridge._deletion_busy.return_value = True
        self.assertFalse(self.bridge.connect_whisper_turbo()['ok'])
        self.bridge._deletion_busy.return_value = False
        self.validation.side_effect = ValueError('asset changed')
        self.assertFalse(self.bridge.connect_whisper_turbo()['ok'])
        self.assertEqual(self.bridge.registry.list(),[])


if __name__ == '__main__':
    unittest.main()
