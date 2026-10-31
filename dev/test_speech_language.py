"""Speech preflight regressions, with no model loading or HTTP calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from dev.test_speech_integrity import pipeline, xtts_local, handler_module
from core.speech_language import (require_xtts_language, resolve_speech_language,
                                  preflight_speech, actor_uses_f5)
from core.source_language import resolve_source_language
from core.transcription import TranscriptionResult


class SpeechLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'temp')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = self.path / 'config.json'
        self.config.write_text(json.dumps({'model': 'xtts', 'languages': ['en', 'zh-cn']}))

    def registry(self, voices=(), tts=None):
        return Mock(list=Mock(return_value=list(voices)), get_active=Mock(return_value=tts))

    def test_chinese_aliases_and_native_engine_code(self):
        for code in ('zh', 'zh-Hans', 'zh-Hant', 'zh-cn'):
            self.assertEqual(require_xtts_language(code, self.path), 'zh-cn')

    def test_custom_config_is_authoritative(self):
        with self.assertRaisesRegex(ValueError, 'does not support'):
            require_xtts_language('hi', self.path)

    def test_bad_configs_and_missing_custom_config_fail(self):
        for content in ('{', '[]', '{"model":"other","languages":["en"]}',
                        '{"model":"xtts","languages":[]}',
                        '{"model":"xtts","languages":[null]}'):
            self.config.write_text(content)
            with self.assertRaises(ValueError):
                require_xtts_language('en', self.path)
        self.config.unlink()
        with self.assertRaisesRegex(ValueError, 'Cannot read'):
            require_xtts_language('en', self.path)

    def test_default_contract_without_downloaded_config(self):
        with patch('core.speech_language.config.MODELS_DIR', str(self.path)):
            self.assertEqual(require_xtts_language('zh'), 'zh-cn')
            with self.assertRaisesRegex(ValueError, 'does not support'):
                require_xtts_language('bn')

    def test_source_manual_and_confident_detection(self):
        self.assertEqual(resolve_speech_language('source', 'Hindi'), 'hi')
        self.assertEqual(resolve_speech_language('source', resolve_source_language('auto', 'en', .8)), 'en')
        self.assertEqual(resolve_speech_language('en'), 'en')

    def test_unresolved_source_and_unknown_target_fail(self):
        for source in (None, resolve_source_language('auto', 'en', .79),
                       resolve_source_language('auto', 'unknown', .99)):
            with self.assertRaisesRegex(ValueError, 'resolved source'):
                resolve_speech_language('source', source)
        with self.assertRaisesRegex(ValueError, 'Unknown speech'):
            resolve_speech_language('xx')

    def test_provider_rejects_before_handler_construction(self):
        with patch.object(xtts_local, 'TTSHandler') as load:
            provider = xtts_local.XTTSLocalProvider(model_path=str(self.path))
            with self.assertRaises(ValueError):
                provider.synthesize('hello', 'unused.wav', 'bn')
            load.assert_not_called()

    def test_handler_rejects_before_asset_download(self):
        with patch('core.model_assets.ensure_assets') as download:
            with self.assertRaises(ValueError):
                handler_module.TTSHandler(language='bn')
            download.assert_not_called()

    def test_f5_only_and_cloud_base_skip_xtts(self):
        voices = [{'display_name': 'f5', 'kind': 'local_file', 'request_preset': 'f5tts'}]
        registry = self.registry(voices)
        with patch('core.speech_language.require_xtts_language') as check:
            preflight_speech(registry, ['f5'], 'en')
            check.assert_not_called()
            preflight_speech(self.registry(tts={'kind': 'cloud_api'}), ['CLONED_USER'], 'bn')
            check.assert_not_called()

    def test_cloud_voice_marker_does_not_bypass_base_tts(self):
        registry = self.registry([{'display_name': 'cloud', 'kind': 'cloud_api', 'request_preset': 'f5tts'}])
        self.assertFalse(actor_uses_f5(registry, 'cloud'))
        with self.assertRaisesRegex(ValueError, 'does not support'):
            preflight_speech(registry, ['cloud'], 'bn')

    def test_actual_nonblank_cast_assignments_only(self):
        pipe = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        pipe.registry = self.registry([{'display_name': 'f5', 'kind': 'local_file', 'request_preset': 'f5tts',
                                        'meta': {'supported_languages': ['bn']}}])
        pipe._check_speech_routes(['f5', 'CLONED_USER'], 'bn', [{'text': 'hello'}, {'text': ' '}])
        with self.assertRaises(ValueError):
            pipe._check_speech_routes(['f5', 'CLONED_USER'], 'bn', [{'text': 'hello'}, {'text': 'world'}])

    def test_default_f5_capability_is_not_unrestricted(self):
        registry = self.registry([{'display_name': 'f5', 'kind': 'local_file', 'request_preset': 'f5tts'}])
        preflight_speech(registry, ['f5'], 'en')
        preflight_speech(registry, ['f5'], 'zh-cn')
        with self.assertRaisesRegex(ValueError, 'F5 checkpoint'):
            preflight_speech(registry, ['f5'], 'bn')

    def test_audio_preflight_precedes_translation(self):
        pipe = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        pipe.registry = None
        pipe._transcribe_source = Mock(return_value=TranscriptionResult(
            [{'start': 0, 'end': 1, 'text': 'hello'}], language='en', language_probability=.99))
        pipe._resolve_translation_and_filter = Mock()
        with patch.object(pipeline.providers, 'resolve_stt'):
            with self.assertRaisesRegex(ValueError, 'does not support'):
                pipe._transcribe_and_translate('unused', 'bn', Mock(), speech_cast=['CLONED_USER'])
        pipe._resolve_translation_and_filter.assert_not_called()

    def test_early_generator_check_before_cleanup(self):
        pipe = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        pipe.registry = None
        for method in (pipe.process_video_gen, pipe.process_audio_dub_gen):
            with patch('core.janitor.Janitor') as janitor:
                with self.assertRaisesRegex(ValueError, 'does not support'):
                    next(method('unused', ['CLONED_USER'], target_lang='bn'))
                janitor.assert_not_called()

    def test_source_language_reaches_both_dubbing_loops(self):
        from contextlib import ExitStack
        for method_name in ('process_video_gen', 'process_audio_dub_gen'):
            pipe = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
            pipe.registry = None
            pipe.temp_dir = pipe.output_dir = str(self.path)
            media = self.path / 'source.wav'
            media.write_bytes(b'mocked media')
            transcript = TranscriptionResult([{'start': 0, 'end': 1, 'text': 'hello'}], 'en', .99)
            with ExitStack() as stack:
                stack.enter_context(patch('core.janitor.Janitor'))
                stack.enter_context(patch('audio_utils.AudioEngineer'))
                stack.enter_context(patch.object(pipeline, '_run_ffmpeg'))
                stack.enter_context(patch.object(pipe, 'get_duration', return_value=1))
                stack.enter_context(patch.object(pipe, 'generate_srt'))
                stack.enter_context(patch.object(pipe, '_transcribe_source', return_value=transcript))
                stack.enter_context(patch.object(pipeline.providers, 'resolve_stt'))
                stack.enter_context(patch.object(pipeline.providers, 'resolve_tts'))
                translate = stack.enter_context(patch.object(pipe, '_resolve_translation_and_filter'))
                dub = stack.enter_context(patch.object(pipe, '_dub_all_segments', side_effect=RuntimeError('stop at synthesis')))
                with self.assertRaisesRegex(RuntimeError, 'stop at synthesis'):
                    list(getattr(pipe, method_name)(str(media), ['CLONED_USER'], target_lang='source',
                                                  source_language='fr', keep_background=False, compute_device='cpu'))
                self.assertEqual(dub.call_args.args[2], 'fr')
                self.assertEqual(transcript[0]['text'], 'hello')
                translate.assert_not_called()

    def test_mixed_cast_defers_early_check(self):
        pipe = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        pipe.registry = self.registry([{'display_name': 'f5', 'kind': 'local_file', 'request_preset': 'f5tts'}])
        pipe._early_speech_check(['f5', 'CLONED_USER'], 'bn', 'auto')
        with self.assertRaises(ValueError):
            pipe._check_speech_routes(['f5', 'CLONED_USER'], 'bn', [{'text': 'hello'}, {'text': 'world'}])


if __name__ == '__main__':
    unittest.main()

