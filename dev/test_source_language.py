"""Backend source policy and wiring tests with mocked AI/HTTP boundaries."""
from contextlib import ExitStack
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core import source_language as policy
from core.providers.translation import nllb_local, cloud_rest, airllm_local, ollama_m2m100_local
from core.providers import resolve
from core import render_state
from bridge.api import PythonBridge
import llm_translator
import pipeline
import requests

SEGMENTS = [{'start': 0.0, 'end': 2.0, 'text': 'Hello'}]


def response(payload):
    value = Mock()
    value.json.return_value = payload
    return value


class SourcePolicyTests(unittest.TestCase):
    def test_maps_match_bundled_tokenizer_vocabulary_without_model_load(self):
        from core.languages import M2M100_LANG_MAP, NLLB_LANG_MAP
        directory = ROOT / 'build/windows-portable/Lib/site-packages/transformers/models'
        if not directory.is_dir():
            self.skipTest('Bundled tokenizer source is not available in this checkout.')
        for relative, sources, targets in (
            ('m2m_100/tokenization_m2m_100.py', policy.M2M100_SOURCE_MAP, M2M100_LANG_MAP),
            ('nllb/tokenization_nllb.py', policy.NLLB_SOURCE_MAP, NLLB_LANG_MAP),
        ):
            tree = ast.parse((directory / relative).read_text(encoding='utf-8'))
            vocabulary = next(ast.literal_eval(node.value) for node in tree.body
                              if isinstance(node, ast.Assign) and any(
                                  isinstance(target, ast.Name) and target.id == 'FAIRSEQ_LANGUAGE_CODES'
                                  for target in node.targets))
            if isinstance(vocabulary, dict):
                vocabulary = vocabulary['m2m100']
            self.assertTrue(set(sources.values()) <= set(vocabulary))
            self.assertTrue(set(targets.values()) <= set(vocabulary))

    def test_auto_defaults_and_missing_metadata_are_unresolved(self):
        for selected in ('auto', None, ' AUTO '):
            source = policy.resolve_source_language(selected)
            self.assertIsNone(source.code)
            self.assertFalse(source.resolved)

    def test_manual_overrides_detection_and_does_not_invent_confidence(self):
        source = policy.resolve_source_language('French', 'hi', 0.99)
        self.assertEqual(source.code, 'fr')
        self.assertEqual(source.origin, 'manual')
        self.assertIsNone(source.probability)
        self.assertTrue(source.resolved)

    def test_known_codes_names_and_script_tokens_normalize(self):
        for label, code in (('HI', 'hi'), ('english', 'en'), ('Arabic', 'ar'), ('hin_Deva', 'hi'), ('zho_Hant', 'zh-Hant'), ('pan_Guru', 'pa-Guru'), ('Punjabi', 'pa')):
            self.assertEqual(policy.resolve_source_language('auto', label, 0.9).code, code)

    def test_auto_threshold_boundaries(self):
        for probability, accepted in ((0.7999, False), (0.80, True), (1, True), (0, False), (None, False)):
            self.assertEqual(policy.resolve_source_language('auto', 'hi', probability).resolved, accepted)

    def test_malformed_confidence_cannot_enable_fixed_translation(self):
        for probability in (True, '0.99', float('nan'), float('inf'), -1, 2, [], 10**400):
            self.assertFalse(policy.resolve_source_language('auto', 'hi', probability).resolved)

    def test_unknown_detected_label_is_not_english(self):
        source = policy.resolve_source_language('auto', 'unknown-label', 0.99)
        self.assertIsNone(source.code)
        self.assertEqual(source.detected_label, 'unknown-label')
        with self.assertRaisesRegex(ValueError, 'resolved source'):
            policy.require_fixed_source('M2M100', policy.M2M100_SOURCE_MAP, source)

    def test_invalid_manual_selection_is_an_error(self):
        for selection in ('unknown', '', '  ', True, [], {}):
            with self.assertRaises(ValueError):
                policy.resolve_source_language(selection)

    def test_fixed_source_rejects_low_or_absent_confidence(self):
        for probability in (0.79, None):
            source = policy.resolve_source_language('auto', 'hi', probability)
            with self.assertRaisesRegex(ValueError, '0.80'):
                policy.require_fixed_source('NLLB', policy.NLLB_SOURCE_MAP, source)

    def test_manual_selection_bypasses_confidence_but_not_exact_map(self):
        self.assertEqual(policy.require_fixed_source('NLLB', policy.NLLB_SOURCE_MAP, 'Hindi'), 'hin_Deva')
        for source in ('hi-en', 'pa', 'zh'):
            with self.assertRaisesRegex(ValueError, 'exact source'):
                policy.require_fixed_source('NLLB', policy.NLLB_SOURCE_MAP, source)

    def test_explicit_chinese_and_punjabi_scripts_have_separate_tokens(self):
        for source, token in (('zh-Hans', 'zho_Hans'), ('zh-Hant', 'zho_Hant'), ('pa-Guru', 'pan_Guru')):
            self.assertEqual(policy.require_fixed_source('NLLB', policy.NLLB_SOURCE_MAP, source), token)
        for source in ('pnb', 'pcm'):
            with self.assertRaises(ValueError):
                policy.require_fixed_source('NLLB', policy.NLLB_SOURCE_MAP, source)
        with self.assertRaises(ValueError):
            policy.require_fixed_source('M2M100', policy.M2M100_SOURCE_MAP, 'pnb')
        self.assertEqual(policy.require_fixed_source('M2M100', policy.M2M100_SOURCE_MAP, 'pa-Guru'), 'pa')

    def test_prompt_sources_infer_when_unknown_or_low_confidence(self):
        self.assertIn('French', policy.source_prompt('fr'))
        self.assertIn('Infer', policy.source_prompt(policy.resolve_source_language('auto', 'hi', 0.7)))
        self.assertIn('Infer', policy.source_prompt(None))

    def test_source_context_is_immutable_and_validated(self):
        with self.assertRaises(ValueError):
            policy.SourceLanguage('unknown', 'manual')
        with self.assertRaises(ValueError):
            policy.SourceLanguage('en', 'detected', True)
        source = policy.resolve_source_language('fr')
        with self.assertRaises(AttributeError):
            source.code = 'en'


class ProviderSourceTests(unittest.TestCase):
    def m2m(self):
        subject = llm_translator.LLMTranslator.__new__(llm_translator.LLMTranslator)
        subject.mode, subject.device = 'm2m100', 'cpu'
        subject.model, subject.tokenizer = Mock(), Mock()
        from dev.test_translation_completion import completed_model
        completed_model(subject.model, subject.tokenizer)
        subject.tokenizer.return_value.to.return_value = {'input_ids': [1]}
        subject.tokenizer.batch_decode.return_value = ['translated']
        subject.tokenizer.get_lang_id.side_effect = lambda code: {'en': 1, 'hi': 2, 'fr': 3, 'zh': 4, 'pa': 5}[code]
        return subject

    def nllb(self):
        subject = nllb_local.NLLBLocalProvider('mock')
        subject._model, subject._tokenizer = Mock(), Mock()
        from dev.test_translation_completion import completed_model
        completed_model(subject._model, subject._tokenizer)
        subject._tokenizer.unk_token_id = 0
        subject._tokenizer.convert_tokens_to_ids.return_value = 1
        subject._tokenizer.return_value.to.return_value = {'input_ids': [1]}
        subject._tokenizer.batch_decode.return_value = ['translated']
        return subject

    def test_m2m_sets_each_source_before_tokenization(self):
        subject = self.m2m()
        sources = []
        subject.tokenizer.side_effect = lambda *a, **k: sources.append(subject.tokenizer.src_lang) or Mock(to=Mock(return_value={'input_ids': [1]}))
        for source in ('hi', 'fr'):
            self.assertEqual(subject.translate('Hello', 'English', source_language=source), 'translated')
        self.assertEqual(sources, ['hi', 'fr'])

    def test_m2m_unknown_source_rejects_before_tokenization(self):
        subject = self.m2m()
        with self.assertRaisesRegex(ValueError, 'resolved source'):
            subject.translate('Hello', 'English')
        subject.tokenizer.assert_not_called()
        subject.model.generate.assert_not_called()

    def test_m2m_loaded_tokenizer_missing_source_is_error(self):
        subject = self.m2m()
        subject.tokenizer.get_lang_id.side_effect = KeyError('hi')
        with self.assertRaisesRegex(RuntimeError, 'M2M100 translation failed'):
            subject.translate('Hello', source_language='hi')
        subject.tokenizer.assert_not_called()

    def test_m2m_invalid_source_token_ids_do_not_generate(self):
        for token_id in (None, -1, True, '1'):
            subject = self.m2m()
            subject.tokenizer.get_lang_id.return_value = token_id
            subject.tokenizer.get_lang_id.side_effect = None
            with self.assertRaisesRegex(RuntimeError, 'no real source token'):
                subject.translate('Hello', source_language='hi')
            subject.model.generate.assert_not_called()

    def test_nllb_checks_source_before_loading(self):
        subject = nllb_local.NLLBLocalProvider('mock')
        for source in (None, 'zh', 'pa', policy.resolve_source_language('auto', 'hi', 0.79)):
            with patch.object(subject, '_ensure_loaded') as load, self.assertRaises(ValueError):
                subject.translate('Hello', 'English', source_language=source)
            load.assert_not_called()

    def test_nllb_absent_target_tokens_reject_before_loading(self):
        subject = nllb_local.NLLBLocalProvider('mock')
        for target in ('Nigerian Pidgin', 'Western Punjabi'):
            with patch.object(subject, '_ensure_loaded') as load, self.assertRaisesRegex(ValueError, 'exact target'):
                subject.translate('Hello', target, source_language='en')
            load.assert_not_called()

    def test_nllb_sets_each_source_before_tokenization(self):
        subject = self.nllb()
        seen = []
        subject._tokenizer.side_effect = lambda *a, **k: seen.append(subject._tokenizer.src_lang) or Mock(to=Mock(return_value={'input_ids': [1]}))
        for source in ('hi', 'zh-Hant'):
            self.assertEqual(subject.translate('Hello', 'English', source_language=source), 'translated')
        self.assertEqual(seen, ['hin_Deva', 'zho_Hant'])

    def test_nllb_missing_source_token_does_not_generate(self):
        subject = self.nllb()
        subject._tokenizer.convert_tokens_to_ids.side_effect = lambda code: 0 if code == 'hin_Deva' else 1
        with self.assertRaisesRegex(ValueError, 'source token'):
            subject.translate('Hello', 'English', source_language='hi')
        subject._model.generate.assert_not_called()

    def pending(self):
        subject = llm_translator.LLMTranslator.__new__(llm_translator.LLMTranslator)
        subject.mode, subject.fallback_reason = 'fallback_pending', 'Ollama offline'
        subject.warning_callback = Mock()
        return subject

    def test_startup_fallback_rejects_unresolved_source_before_loading(self):
        for source in (None, policy.resolve_source_language('auto', 'hi', 0.79), 'pcm'):
            subject = self.pending()
            with patch.object(subject, 'init_m2m100') as load, self.assertRaisesRegex(ValueError, 'fallback rejected'):
                subject.translate('Hello', 'English', source_language=source)
            load.assert_not_called()
            subject.warning_callback.assert_not_called()

    def test_runtime_fallback_rejects_missing_source_without_switching(self):
        subject = self.pending()
        subject.mode, subject.ollama_host, subject.ollama_model = 'ollama', 'http://example.invalid', 'mock'
        with patch.object(llm_translator.requests, 'post', side_effect=requests.Timeout('offline')), patch.object(subject, 'init_m2m100') as load, self.assertRaisesRegex(ValueError, 'offline.*fallback rejected'):
            subject.translate('Hello', 'English')
        load.assert_not_called()
        self.assertEqual(subject.mode, 'ollama')

    def test_runtime_fallback_accepts_high_confidence_source(self):
        subject = self.pending()
        subject.mode, subject.ollama_host, subject.ollama_model = 'ollama', 'http://example.invalid', 'mock'
        def load():
            loaded = self.m2m()
            subject.mode, subject.device, subject.model, subject.tokenizer = loaded.mode, loaded.device, loaded.model, loaded.tokenizer
        with patch.object(llm_translator.requests, 'post', side_effect=requests.Timeout('offline')), patch.object(subject, 'init_m2m100', side_effect=load), self.assertLogs(level='WARNING'):
            self.assertEqual(subject.translate('Hello', source_language=policy.resolve_source_language('auto', 'hi', 0.8)), 'translated')
        self.assertEqual(subject.tokenizer.src_lang, 'hi')

    def test_ollama_prompt_receives_manual_source(self):
        subject = self.pending()
        subject.mode, subject.ollama_host, subject.ollama_model = 'ollama', 'http://example.invalid', 'mock'
        with patch.object(llm_translator.requests, 'post', return_value=response({'response': 'translated'})) as post:
            subject.translate('Hello', source_language='fr')
        self.assertIn('Source language: French', post.call_args.kwargs['json']['prompt'])

    def test_wrapper_forwards_context_and_rejects_invalid_override_before_discovery(self):
        with patch.object(ollama_m2m100_local, 'LLMTranslator') as factory:
            subject = ollama_m2m100_local.OllamaM2M100LocalProvider()
            with self.assertRaises(ValueError):
                subject.translate('Hello', 'English', source_language='unknown')
            factory.assert_not_called()
            subject.translate('Hello', 'English', source_language='fr')
        self.assertEqual(factory.return_value.translate.call_args.kwargs['source_language'].code, 'fr')

    def test_airllm_prompt_receives_source(self):
        subject = airllm_local.AirLLMTranslationProvider('mock')
        subject._model = Mock()
        subject._model.tokenizer.return_value = {'input_ids': Mock(shape=[1, 2])}
        subject._model.generate.return_value.sequences = [[1, 2, 3]]
        subject._model.tokenizer.decode.return_value = 'translated'
        subject.translate('Hello', 'English', source_language='fr')
        self.assertIn('Source language: French', subject._model.tokenizer.call_args.args[0][0])

    def test_cloud_chat_manual_and_unresolved_source_prompts(self):
        for source, expected in (('hi', 'Source language: Hindi'), (None, 'Infer the source')):
            with patch.object(cloud_rest, 'request', return_value=response({'choices': [{'message': {'content': 'translated'}}]})) as request:
                cloud_rest._openai_chat_request('http://example.invalid', None, 'Hello', 'English', {}, source_language=source)
            self.assertIn(expected, request.call_args.kwargs['json_body']['messages'][0]['content'])

    def test_custom_cloud_requires_real_source_placeholder(self):
        for extra in ({}, {'body': {'source': '{{source_language}}'}}, {'body': {'source': {'value': '{source_language}'}}}):
            with patch.object(cloud_rest, 'request') as request, self.assertRaisesRegex(ValueError, 'cannot transmit'):
                cloud_rest._custom_request('http://example.invalid', None, 'Hello', 'English', extra, source_language='hi')
            request.assert_not_called()

    def test_custom_cloud_forwards_source_code_or_name(self):
        for placeholder, value in (('source_language', 'hi'), ('source_language_name', 'Hindi')):
            extra = {'body': {'source': '{'+placeholder+'}', 'text': '{text}'}}
            with patch.object(cloud_rest, 'request', return_value=response({'text': 'translated'})) as request:
                cloud_rest._custom_request('http://example.invalid', None, 'Hello', 'English', extra, source_language='hi')
            self.assertEqual(request.call_args.kwargs['json_body']['source'], value)

    def test_custom_cloud_rejects_modified_source_placeholders(self):
        extra = {'body': {'text': '{text}', 'source': '{source_language:.0s}'}}
        with patch.object(cloud_rest, 'request') as request, self.assertRaisesRegex(ValueError, 'truncate'):
            cloud_rest._custom_request('http://example.invalid', None, 'hi', 'English', extra, source_language='hi')
        request.assert_not_called()

    def test_resolver_forwards_registry_request_configuration(self):
        config = {'body': {'source': '{source_language}'}}
        registry = Mock()
        registry.get_active.return_value = {'kind': 'cloud_api', 'api_base_url': 'http://example.invalid', 'meta': {'translation_request': config}, 'request_preset': 'custom'}
        provider = resolve.resolve_translation(registry, 'unused')
        self.assertEqual(provider.extra, config)


class PipelineSourceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        self.subject.registry = Mock()
        self.subject.registry.get_active.return_value = None
        self.subject.registry.list.return_value = []
        self.subject.temp_dir = self.subject.output_dir = str(self.directory)
        self.stt, self.translator = Mock(), Mock()
        self.stt.transcribe.return_value = {'segments': SEGMENTS, 'language': 'hi', 'language_probability': 0.9}
        self.translator.translate.return_value = 'translated'
        self.stack.enter_context(patch.object(pipeline.providers, 'resolve_stt', return_value=self.stt))
        self.stack.enter_context(patch.object(self.subject, '_resolve_translation_and_filter', return_value=(self.translator, '', None, '')))

    def test_audio_helper_passes_detected_source_and_manual_override(self):
        for selected, expected, origin in (('auto', 'hi', 'detected'), ('fr', 'fr', 'manual')):
            self.subject._transcribe_and_translate('unused', 'en', {}, selected)
            source = self.translator.translate.call_args.kwargs['source_language']
            self.assertEqual((source.code, source.origin), (expected, origin))

    def test_feedback_keeps_detection_separate_from_manual_selection(self):
        self.subject.source_language_callback = Mock()
        self.subject._transcribe_and_translate('unused', 'en', {}, 'fr')
        payload = self.subject.source_language_callback.call_args.args[0]
        self.assertEqual(payload['source_name'], 'French')
        self.assertEqual(payload['origin'], 'manual')
        self.assertEqual(payload['detected_name'], 'Hindi')
        self.assertEqual(payload['probability'], 0.9)
        self.assertTrue(payload['resolved'])

    def test_feedback_reports_low_confidence_without_marking_source_resolved(self):
        self.subject.source_language_callback = Mock()
        self.stt.transcribe.return_value = {'segments': SEGMENTS, 'language': 'hi', 'language_probability': 0.79}
        self.subject._transcribe_and_translate('unused', 'en', {})
        payload = self.subject.source_language_callback.call_args.args[0]
        self.assertFalse(payload['resolved'])
        self.assertEqual(payload['probability'], 0.79)
        self.assertEqual(payload['minimum_confidence'], 0.8)

    def test_feedback_callback_failure_does_not_abort_translation(self):
        self.subject.source_language_callback = Mock(side_effect=RuntimeError('UI unavailable'))
        with self.assertLogs(level='WARNING'):
            result = self.subject._transcribe_and_translate('unused', 'en', {})
        self.assertEqual(result[0]['text'], 'translated')

    def test_subtitle_feedback_has_no_fabricated_detection(self):
        self.subject.source_language_callback = Mock()
        self.subject._report_source_language(policy.resolve_source_language('fr'))
        payload = self.subject.source_language_callback.call_args.args[0]
        self.assertEqual(payload['source_name'], 'French')
        self.assertIsNone(payload['detected_language'])
        self.assertIsNone(payload['probability'])

    def test_legacy_stt_source_stays_unknown_for_prompt_provider(self):
        self.stt.transcribe.return_value = SEGMENTS
        self.subject._transcribe_and_translate('unused', 'en', {})
        self.assertFalse(self.translator.translate.call_args.kwargs['source_language'].resolved)

    def test_invalid_manual_override_stops_before_stt(self):
        with self.assertRaises(ValueError):
            self.subject._transcribe_and_translate('unused', 'en', {}, 'invalid')
        self.stt.transcribe.assert_not_called()

    def test_pipeline_run_rejects_invalid_source_before_template(self):
        with patch.object(self.subject, 'process_video_gen') as run, self.assertRaises(ValueError):
            list(self.subject.run('video_dub', 'unused', {'source_language': 'invalid'}))
        run.assert_not_called()

    def test_subtitle_manual_selection_passes_source_and_publishes(self):
        path = self.directory / 'input.srt'
        path.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello\n\n', encoding='utf-8')
        result = list(self.subject.process_subtitle_translate_gen(str(path), 'en', 'fr'))[-1][2]
        self.assertTrue(Path(result).is_file())
        self.assertIn('translated', Path(result).read_text(encoding='utf-8'))
        self.assertEqual(self.translator.translate.call_args.kwargs['source_language'].code, 'fr')

    def test_subtitle_auto_nllb_rejects_without_publishing_output(self):
        path = self.directory / 'input.srt'
        path.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello\n\n', encoding='utf-8')
        self.translator = nllb_local.NLLBLocalProvider('mock')
        with patch.object(self.subject, '_resolve_translation_and_filter', return_value=(self.translator, '', None, '')), patch.object(self.translator, '_ensure_loaded') as load, self.assertRaisesRegex(RuntimeError, 'Subtitle cue 1.*resolved source'):
            list(self.subject.process_subtitle_translate_gen(str(path), 'en'))
        load.assert_not_called()
        self.assertFalse((self.directory / 'input_TRANSLATED_EN.srt').exists())

    def media_to_translation(self, kind, selection):
        path = self.directory / ('input.mp4' if kind == 'video' else 'input.wav')
        path.write_bytes(b'mocked-media')
        self.stack.enter_context(patch('core.janitor.Janitor'))
        self.stack.enter_context(patch('audio_utils.AudioEngineer'))
        self.stack.enter_context(patch.object(pipeline, '_run_ffmpeg'))
        self.stack.enter_context(patch.object(self.subject, 'get_duration', return_value=2))
        self.stack.enter_context(patch.object(pipeline.providers, 'resolve_tts'))
        self.stack.enter_context(patch.object(pipeline.providers, 'resolve_voice_for_actor'))
        self.stack.enter_context(patch.object(self.subject, '_dub_all_segments', side_effect=RuntimeError('stop before synthesis')))
        method = self.subject.process_video_gen if kind == 'video' else self.subject.process_audio_dub_gen
        with self.assertRaisesRegex(RuntimeError, 'stop before synthesis'):
            list(method(str(path), ['actor'], keep_background=False, target_lang='en', source_language=selection))
        return self.translator.translate.call_args.kwargs['source_language']

    def test_actual_video_generator_forwards_detected_source(self):
        source = self.media_to_translation('video', 'auto')
        self.assertEqual((source.code, source.probability), ('hi', 0.9))

    def test_actual_audio_generator_forwards_manual_source(self):
        source = self.media_to_translation('audio', 'fr')
        self.assertEqual((source.code, source.origin), ('fr', 'manual'))

    def test_source_bypass_skips_translation(self):
        self.subject._transcribe_and_translate('unused', 'source', {}, 'fr')
        self.translator.translate.assert_not_called()

    def test_bridge_all_templates_forward_manual_and_default_auto(self):
        bridge = PythonBridge.__new__(PythonBridge)
        bridge._resolve_cast_list = Mock(return_value=['actor'])
        for template in ('video_dub', 'video_dub_lipsync', 'audio_dub', 'subtitle_translate'):
            self.assertEqual(bridge._template_kwargs(template, {'lang': 'en', 'source_language': 'fr'})['source_language'], 'fr')
            self.assertEqual(bridge._template_kwargs(template, {'lang': 'en'})['source_language'], 'auto')

    def test_bridge_exposes_script_specific_source_catalog(self):
        result = PythonBridge.__new__(PythonBridge).list_source_languages()
        self.assertIn('zh-Hant', [item['code'] for item in result])
        self.assertIn('pa-Guru', [item['code'] for item in result])

    def test_interrupted_job_parameters_preserve_manual_selection(self):
        with patch.object(render_state, 'STATE_PATH', str(self.directory / 'state.json')):
            render_state.mark_started('unused', {'lang': 'en', 'source_language': 'fr'}, 'subtitle_translate')
            state = render_state.get_interrupted()
        self.assertEqual(state['params']['source_language'], 'fr')


if __name__ == '__main__':
    unittest.main(verbosity=2)
