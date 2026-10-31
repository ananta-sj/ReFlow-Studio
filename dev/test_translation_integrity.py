"""Translation boundaries tested with mocked HTTP/models; no network/downloads."""
from contextlib import ExitStack
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
import llm_translator as local
import pipeline
from core.providers.base import require_translation_text
from dev.test_translation_completion import completed_model
from core.providers.translation import cloud_rest as cloud
from core.providers.translation import ollama_m2m100_local as wrapper
from core.providers.translation import nllb_local, airllm_local


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


class LocalTranslationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.get = self.stack.enter_context(patch.object(local.requests, 'get', return_value=response({'models': [{'name': 'llama3:latest'}]})))
        self.post = self.stack.enter_context(patch.object(local.requests, 'post', return_value=response({'response': 'Namaste'})))
        self.stack.enter_context(patch.object(local.time, 'sleep'))
        self.real_initializer = local.LLMTranslator.init_m2m100
        self.init = self.stack.enter_context(patch.object(local.LLMTranslator, 'init_m2m100'))

    def translator(self):
        return local.LLMTranslator()

    def test_exact_default_tag_is_selected(self):
        translator = self.translator()
        self.assertEqual(translator.ollama_model, 'llama3:latest')
        self.assertEqual(self.get.call_args.kwargs['timeout'], (3, 3))

    def test_missing_requested_model_does_not_pick_first_or_fallback(self):
        self.get.return_value = response({'models': [{'name': 'different-model:latest'}, {'name': 'llama3:8b'}]})
        with self.assertRaisesRegex(RuntimeError, 'not installed'):
            self.translator()
        self.init.assert_not_called()

    def test_malformed_inventory_is_error(self):
        for payload in ([], {}, {'models': [None]}, {'models': [{'name': 42}]}):
            self.get.return_value = response(payload)
            with self.subTest(payload=payload), self.assertRaisesRegex(RuntimeError, 'invalid model inventory'):
                self.translator()

    def test_discovery_http_failure_is_explicit(self):
        self.get.return_value.raise_for_status.side_effect = requests.HTTPError('HTTP 401')
        with self.assertRaisesRegex(RuntimeError, 'HTTP 401'):
            self.translator()
        self.init.assert_not_called()

    def test_unreachable_discovery_warns_before_fallback(self):
        self.get.side_effect = requests.ConnectionError('offline')
        notify = Mock()
        translator = local.LLMTranslator(warning_callback=notify)
        self.init.assert_not_called()
        self.assertEqual(translator.mode, 'fallback_pending')
        with self.assertLogs(level='WARNING'):
            with self.assertRaisesRegex(RuntimeError, 'not ready'):
                translator.translate('Hello', source_language='en')  # mock initializer leaves mode pending
        self.assertEqual(self.get.call_count, 3)
        self.init.assert_called_once()
        self.assertIn('switching translation to M2M100', notify.call_args.args[0])

    def test_fallback_initialization_failure_propagates_both_causes(self):
        self.get.side_effect = requests.Timeout('server timed out')
        self.init.side_effect = RuntimeError('weights unavailable')
        with self.assertLogs(level='WARNING'), self.assertRaisesRegex(RuntimeError, 'server timed out.*weights unavailable'):
            self.translator().translate('Hello', source_language='en')

    def test_success_has_generation_timeout_and_status_check(self):
        self.assertEqual(self.translator().translate('Hello', 'Hindi'), 'Namaste')
        self.assertEqual(self.post.call_args.kwargs['timeout'], (5, 120))
        self.post.return_value.raise_for_status.assert_called_once()

    def test_colons_survive_prefix_removal(self):
        self.post.return_value = response({'response': 'Here is the translation: Meet at 10:30'})
        self.assertEqual(self.translator().translate('Hello'), 'Meet at 10:30')

    def test_prefix_is_removed_only_at_start(self):
        original = 'The sign says Here is the translation: 10:30'
        self.post.return_value = response({'response': original})
        self.assertEqual(self.translator().translate('Hello'), original)

    def test_unchanged_translation_is_valid(self):
        self.post.return_value = response({'response': 'London'})
        self.assertEqual(self.translator().translate('London'), 'London')

    def test_invalid_response_values_are_not_source_text_fallback(self):
        translator = self.translator()
        for value in ('', ' ', None, 42, ['text'], {}):
            self.post.return_value = response({'response': value})
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'nonempty string'):
                translator.translate('Hello')
        self.init.assert_not_called()

    def test_invalid_json_and_error_payload_raise(self):
        translator = self.translator()
        self.post.return_value.json.side_effect = ValueError('bad JSON')
        with self.assertRaisesRegex(RuntimeError, 'invalid JSON'):
            translator.translate('Hello')
        self.post.return_value = response({'error': 'model crashed'})
        with self.assertRaisesRegex(RuntimeError, 'error response'):
            translator.translate('Hello')

    def test_http_failure_falls_back_visibly_instead_of_returning_input(self):
        translator = self.translator()
        self.post.return_value.raise_for_status.side_effect = requests.HTTPError('HTTP 503')
        def recovered():
            translator.mode = 'm2m100'
            translator.device = 'cpu'
            translator.tokenizer = Mock()
            translator.tokenizer.get_lang_id.return_value = 1
            translator.tokenizer.return_value.to.return_value = {'input_ids': [1]}
            translator.tokenizer.batch_decode.return_value = ['Recovered translation']
            translator.model = Mock()
            completed_model(translator.model, translator.tokenizer)
        self.init.side_effect = recovered
        with self.assertLogs(level='WARNING'):
            self.assertEqual(translator.translate('Hello', source_language='en'), 'Recovered translation')

    def test_unknown_target_is_not_defaulted_to_english(self):
        with self.assertRaisesRegex(ValueError, 'Unknown translation target'):
            self.translator().translate('Hello', 'Unknown language')
        self.post.assert_not_called()

    def test_blank_input_does_not_make_generation_request(self):
        self.assertEqual(self.translator().translate(' '), ' ')
        self.post.assert_not_called()

    def test_broken_engine_raises_instead_of_returning_source(self):
        translator = self.translator()
        translator.mode = 'broken'
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            translator.translate('Hello')

    def test_m2m_generation_failure_propagates(self):
        translator = self.translator()
        translator.mode, translator.device = 'm2m100', 'cpu'
        translator.tokenizer, translator.model = Mock(), Mock()
        completed_model(translator.model, translator.tokenizer)
        translator.tokenizer.get_lang_id.return_value = 1
        translator.tokenizer.return_value.to.return_value = {'input_ids': [1]}
        translator.model.generate.side_effect = RuntimeError('out of memory')
        with self.assertRaisesRegex(RuntimeError, 'M2M100 translation failed.*out of memory'):
            translator.translate('Hello', source_language='en')

    def test_real_initializer_logic_propagates_mocked_loader_failure(self):
        factory = Mock()
        factory.from_pretrained.side_effect = RuntimeError('cannot load weights')
        with patch('core.model_assets.ensure_assets'), patch.dict(sys.modules, {'transformers': SimpleNamespace(M2M100Tokenizer=factory, M2M100ForConditionalGeneration=factory)}):
            translator = self.translator()
            with self.assertRaisesRegex(RuntimeError, 'initialization failed.*cannot load weights'):
                self.real_initializer(translator)
        self.assertEqual(translator.mode, 'broken')


class CloudAndPipelineTests(unittest.TestCase):
    def test_common_validator_rejects_nontext_and_accepts_same_text(self):
        for value in (None, 0, [], {}, '', ' '):
            with self.assertRaisesRegex(RuntimeError, 'nonempty string'):
                require_translation_text(value)
        self.assertEqual(require_translation_text(' London '), 'London')

    def test_chat_schema_and_content_are_checked(self):
        for payload in ({}, {'choices': []}, {'choices': [{'message': {'content': None}}]}):
            with patch.object(cloud, 'request', return_value=response(payload)), self.assertRaises(RuntimeError):
                cloud._openai_chat_request('http://example.invalid', None, 'Hello', 'Hindi', {})

    def test_chat_success_has_explicit_timeout(self):
        payload = {'choices': [{'message': {'content': 'Hello'}}]}
        with patch.object(cloud, 'request', return_value=response(payload)) as request:
            self.assertEqual(cloud._openai_chat_request('http://example.invalid', None, 'Hello', 'English', {}), 'Hello')
        self.assertEqual(request.call_args.kwargs['timeout'], (5, 120))

    def test_custom_json_list_or_number_is_not_stringified(self):
        for payload in (['not', 'text'], 42, None, {'text': []}, {}):
            with patch.object(cloud, 'request', return_value=response(payload)), self.assertRaises(RuntimeError):
                cloud._custom_request('http://example.invalid', None, 'Hello', 'Hindi', {})

    def test_custom_response_field_and_json_string_are_supported(self):
        for payload, extra in (({'translation': 'Namaste'}, {'response_field': 'translation'}), ('Namaste', {})):
            with patch.object(cloud, 'request', return_value=response(payload)):
                self.assertEqual(cloud._custom_request('http://example.invalid', None, 'Hello', 'Hindi', extra), 'Namaste')

    def test_pipeline_has_segment_and_cue_context(self):
        provider = Mock()
        provider.translate.side_effect = RuntimeError('HTTP failed')
        for context in ('Segment 3', 'Subtitle cue 4'):
            with self.assertRaisesRegex(RuntimeError, context + '.*Hindi.*HTTP failed'):
                pipeline.ReflowPipeline._translate_line('Hello', 'Hindi', provider, '', None, '', context=context)

    def test_pipeline_rejects_invalid_provider_output(self):
        provider = Mock()
        for value in ('', ' ', None, 42):
            provider.translate.return_value = value
            with self.assertRaisesRegex(RuntimeError, 'nonempty string'):
                pipeline.ReflowPipeline._translate_line('Hello', 'Hindi', provider, '', None, '')

    def test_pipeline_preserves_blank_and_unchanged_text(self):
        provider = Mock()
        provider.translate.return_value = 'London'
        self.assertEqual(pipeline.ReflowPipeline._translate_line('London', 'English', provider, '', None, ''), 'London')
        provider.reset_mock()
        self.assertEqual(pipeline.ReflowPipeline._translate_line(' ', 'English', provider, '', None, ''), ' ')
        provider.translate.assert_not_called()

    def test_pipeline_rejects_unknown_code(self):
        with self.assertRaisesRegex(ValueError, 'Unknown translation target code'):
            pipeline.ReflowPipeline._translation_target('invalid-code')

    def test_unknown_code_stops_before_running_template(self):
        subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        subject.process_video_gen = Mock()
        with self.assertRaisesRegex(ValueError, 'Unknown translation target code'):
            list(subject.run('video_dub', 'unused.mp4', {'target_lang': 'invalid-code'}))
        subject.process_video_gen.assert_not_called()

    def test_wrapper_emits_fallback_warning(self):
        with patch.object(wrapper, 'LLMTranslator') as factory, patch('bridge.push.emit') as emit:
            wrapper.OllamaM2M100LocalProvider().translate('Hello', 'Hindi')
            factory.call_args.kwargs['warning_callback']('Using M2M100')
        emit.assert_called_once_with('log', {'level': 'warning', 'message': 'Using M2M100'})

    def test_empty_nllb_output_is_rejected(self):
        provider = nllb_local.NLLBLocalProvider('mocked-path')
        provider._model, provider._tokenizer = Mock(), Mock()
        completed_model(provider._model, provider._tokenizer)
        provider._tokenizer.batch_decode.return_value = [' ']
        provider._tokenizer.return_value.to.return_value = {'input_ids': [1]}
        provider._tokenizer.convert_tokens_to_ids.return_value = 1
        provider._tokenizer.unk_token_id = 0
        with self.assertRaisesRegex(RuntimeError, 'nonempty string'):
            provider.translate('Hello', 'Hindi', source_language='en')

    def test_empty_airllm_output_is_rejected(self):
        provider = airllm_local.AirLLMTranslationProvider('mocked-id')
        provider._model = Mock()
        provider._model.tokenizer.return_value = {'input_ids': Mock(shape=[1, 2])}
        provider._model.generate.return_value = SimpleNamespace(sequences=[[1, 2, 3]])
        provider._model.tokenizer.decode.return_value = ' '
        with self.assertRaisesRegex(RuntimeError, 'nonempty string'):
            provider.translate('Hello', 'Hindi')


class TranslationCapabilityTests(unittest.TestCase):
    def test_fixed_maps_have_no_approximate_targets(self):
        from core.languages import M2M100_LANG_MAP, NLLB_LANG_MAP
        for target in ('Hinglish', 'Nigerian Pidgin', 'Western Punjabi', 'Telugu'):
            self.assertNotIn(target, M2M100_LANG_MAP)
        for target in ('Hinglish', 'Nigerian Pidgin', 'Western Punjabi'):
            self.assertNotIn(target, NLLB_LANG_MAP)
        self.assertEqual(NLLB_LANG_MAP['Telugu'], 'tel_Telu')

    def pending(self):
        translator = local.LLMTranslator.__new__(local.LLMTranslator)
        translator.mode = 'fallback_pending'
        translator.fallback_reason = 'Ollama offline'
        translator.warning_callback = Mock()
        return translator

    def test_startup_fallback_rejects_incompatible_requests_before_loading(self):
        for target, instructions in (('Hinglish', ''), ('Nigerian Pidgin', ''), ('Western Punjabi', ''), ('Telugu', ''), ('Hindi', 'Keep it formal')):
            translator = self.pending()
            with patch.object(translator, 'init_m2m100') as load, self.subTest(target=target), self.assertRaises(ValueError):
                translator.translate('Hello', target, instructions)
            load.assert_not_called()
            translator.warning_callback.assert_not_called()
            self.assertEqual(translator.mode, 'fallback_pending')

    def test_runtime_fallback_rejects_incompatible_requests_before_loading(self):
        for target, instructions in (('Telugu', ''), ('Hindi', 'Keep it formal')):
            translator = self.pending()
            translator.mode, translator.ollama_host, translator.ollama_model = 'ollama', 'http://example.invalid', 'mock'
            with patch.object(local.requests, 'post', side_effect=requests.Timeout('offline')), patch.object(translator, 'init_m2m100') as load, self.assertRaises(ValueError):
                translator.translate('Hello', target, instructions)
            load.assert_not_called()
            self.assertEqual(translator.mode, 'ollama')

    def test_loaded_m2m_rechecks_each_request_before_tokenization(self):
        translator = self.pending()
        translator.mode, translator.tokenizer = 'm2m100', Mock()
        for target, instructions in (('Telugu', ''), ('Hindi', 'Formal')):
            with self.assertRaises(ValueError):
                translator.translate('Hello', target, instructions)
        translator.tokenizer.assert_not_called()

    def test_compatible_startup_fallback_loads_and_translates(self):
        translator = self.pending()
        def load():
            translator.mode, translator.device = 'm2m100', 'cpu'
            translator.tokenizer, translator.model = Mock(), Mock()
            completed_model(translator.model, translator.tokenizer)
            translator.tokenizer.get_lang_id.return_value = 1
            translator.tokenizer.return_value.to.return_value = {'input_ids': [1]}
            translator.tokenizer.batch_decode.return_value = ['Namaste']
        with patch.object(translator, 'init_m2m100', side_effect=load) as loader, self.assertLogs(level='WARNING'):
            self.assertEqual(translator.translate('Hello', 'Hindi', '  ', source_language='en'), 'Namaste')
        loader.assert_called_once()
        translator.tokenizer.get_lang_id.assert_any_call('hi')
        translator.tokenizer.get_lang_id.assert_any_call('en')

    def test_ollama_accepts_product_targets_and_sends_instructions(self):
        translator = self.pending()
        translator.mode, translator.ollama_host, translator.ollama_model = 'ollama', 'http://example.invalid', 'mock'
        with patch.object(local.requests, 'post', return_value=response({'response': 'translated'})) as post:
            self.assertEqual(translator.translate('Hello', 'Hinglish', 'Keep it formal'), 'translated')
        prompt = post.call_args.kwargs['json']['prompt']
        self.assertIn('Hinglish', prompt)
        self.assertIn('Keep it formal', prompt)

    def test_blank_pending_fallback_does_not_load_or_validate(self):
        translator = self.pending()
        with patch.object(translator, 'init_m2m100') as load:
            self.assertEqual(translator.translate(' ', 'Telugu', 'Formal'), ' ')
        load.assert_not_called()

    def test_nllb_rejects_before_loading(self):
        provider = nllb_local.NLLBLocalProvider('mock')
        for target, instructions in (('Hinglish', ''), ('Hindi', 'Formal'), ('Unknown', '')):
            with patch.object(provider, '_ensure_loaded') as load, self.assertRaises(ValueError):
                provider.translate('Hello', target, instructions)
            load.assert_not_called()

    def test_nllb_exact_languages_use_dedicated_tokens(self):
        provider = nllb_local.NLLBLocalProvider('mock')
        provider._model, provider._tokenizer = Mock(), Mock()
        completed_model(provider._model, provider._tokenizer)
        provider._tokenizer.return_value.to.return_value = {'input_ids': [1]}
        provider._tokenizer.unk_token_id = 0
        provider._tokenizer.convert_tokens_to_ids.return_value = 1
        provider._tokenizer.batch_decode.return_value = ['translated']
        for target, code in (('Telugu', 'tel_Telu'), ('Hindi', 'hin_Deva')):
            self.assertEqual(provider.translate('Hello', target, '  ', source_language='en'), 'translated')
            provider._tokenizer.convert_tokens_to_ids.assert_called_with(code)

    def test_custom_template_missing_or_escaped_placeholder_rejects_before_http(self):
        for extra in ({}, {'body': {'text': '{text}', 'instructions': '{{custom_instructions}}'}}, {'body': {'nested': {'instructions': '{custom_instructions}'}}}):
            with patch.object(cloud, 'request') as request, self.assertRaisesRegex(ValueError, 'cannot transmit'):
                cloud._custom_request('http://example.invalid', None, 'Hello', 'Hindi', extra, 'Formal')
            request.assert_not_called()

    def test_custom_template_transmits_full_instructions(self):
        extra = {'body': {'text': '{text}', 'instructions': 'Policy: {custom_instructions}'}}
        with patch.object(cloud, 'request', return_value=response({'text': 'translated'})) as request:
            cloud._custom_request('http://example.invalid', None, 'Hello', 'Hindi', extra, 'Formal')
        self.assertEqual(request.call_args.kwargs['json_body']['instructions'], 'Policy: Formal')

    def test_custom_template_truncation_rejects_before_http(self):
        extra = {'body': {'text': '{text}', 'instructions': '{custom_instructions:.0s}'}}
        with patch.object(cloud, 'request') as request, self.assertRaisesRegex(ValueError, 'truncated'):
            cloud._custom_request('http://example.invalid', None, 'Formal', 'Hindi', extra, 'Formal')
        request.assert_not_called()

    def test_chat_sends_custom_instructions(self):
        with patch.object(cloud, 'request', return_value=response({'choices': [{'message': {'content': 'translated'}}]})) as request:
            cloud._openai_chat_request('http://example.invalid', None, 'Hello', 'Hinglish', {}, 'Formal')
        self.assertIn('Formal', request.call_args.kwargs['json_body']['messages'][0]['content'])

    def test_unknown_targets_reject_before_provider_side_effects(self):
        with patch.object(wrapper, 'LLMTranslator') as factory, self.assertRaises(ValueError):
            wrapper.OllamaM2M100LocalProvider().translate('Hello', 'Unknown')
        factory.assert_not_called()
        provider = airllm_local.AirLLMTranslationProvider('mock')
        with patch.object(provider, '_load') as load, self.assertRaises(ValueError):
            provider.translate('Hello', 'Unknown')
        load.assert_not_called()
        for function in (cloud._custom_request, cloud._openai_chat_request):
            with patch.object(cloud, 'request') as request, self.assertRaises(ValueError):
                function('http://example.invalid', None, 'Hello', 'Unknown', {})
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
