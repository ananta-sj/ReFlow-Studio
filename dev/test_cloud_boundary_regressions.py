"""Real provider functions, mocked transport/audio/OS boundaries; no installs or API calls."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import traceback
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(relative, overrides):
    specification = importlib.util.spec_from_file_location('_boundary_fixture', ROOT / relative)
    module = importlib.util.module_from_spec(specification)
    with patch.dict(sys.modules, overrides):
        specification.loader.exec_module(module)
    return module


class TransportFailure(Exception):
    pass


class CloudBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.http = types.ModuleType('requests')
        self.http.RequestException = TransportFailure
        self.http.request = Mock()
        self.response = Mock(status_code=200, headers={})
        self.response.raise_for_status.return_value = None
        self.http.request.return_value = self.response
        self.common = load('core/providers/cloud_rest_common.py', {
            'requests': self.http,
            'core.render_context': types.SimpleNamespace(check_cancelled=lambda: None, wait_or_cancel=lambda _: None),
            'core.credential_store': types.SimpleNamespace(get_credential=lambda _: 'fixture-key'),
        })
        context = patch.dict(os.environ, {'REFLOW_OFFLINE': '0'})
        context.start()
        self.addCleanup(context.stop)

    def test_scalar_timeout_keeps_existing_connect_cap(self):
        self.assertIs(self.common.request('GET', 'https://service.test/file', timeout=120), self.response)
        self.assertEqual(self.http.request.call_args.kwargs['timeout'], (15, 120))

    def test_translation_connect_read_pair_reaches_transport_unchanged(self):
        self.common.request('POST', 'https://service.test/translate', timeout=(5, 120))
        self.assertEqual(self.http.request.call_args.kwargs['timeout'], (5, 120))

    def test_network_failure_never_prints_signed_url_or_unsafe_cause(self):
        self.http.request.side_effect = TransportFailure('upstream echoed fixture-private-header')
        try:
            url = 'https://service.test/file?token=fixture-private-query'
            self.common.request('GET', url)
        except self.common.CloudRestError as error:
            rendered = ''.join(traceback.format_exception(error))
            self.assertNotIn('fixture-private-query', rendered)
            self.assertNotIn('fixture-private-header', rendered)
            self.assertIn('failed', str(error).lower())
        else:
            self.fail('Transport failure was swallowed')

    def test_http_error_closes_response_and_does_not_echo_remote_detail(self):
        self.response.status_code = 404
        self.response.raise_for_status.side_effect = TransportFailure('fixture-private-response')
        with self.assertRaises(self.common.CloudRestError) as caught:
            self.common.request('GET', 'https://service.test/file')
        self.response.close.assert_called_once()
        self.assertNotIn('fixture-private-response', str(caught.exception))
        self.assertIn('HTTP 404', str(caught.exception))

    def test_failed_job_does_not_echo_arbitrary_service_payload(self):
        self.response.json.return_value = {'state': 'failed', 'debug': 'fixture-private-payload'}
        with self.assertRaises(self.common.CloudRestError) as caught:
            self.common.poll_until_done('https://service.test/status', {}, 'state', 'done', 'url')
        self.assertNotIn('fixture-private-payload', str(caught.exception))

    def test_poll_timeout_does_not_echo_signed_status_url(self):
        with self.assertRaises(self.common.CloudRestError) as caught:
            self.common.poll_until_done('https://service.test/status?token=fixture-private-query', {},
                                        'state', 'done', 'url', timeout=0)
        self.assertNotIn('fixture-private-query', str(caught.exception))

    def test_offline_url_validation_does_not_expose_parser_detail(self):
        with patch.dict(os.environ, {'REFLOW_OFFLINE': '1'}):
            url = 'https://[fixture-private-host]/file'
            with self.assertRaises(self.common.CloudRestError) as caught:
                self.common.request('GET', url)
        self.assertNotIn('fixture-private-host', str(caught.exception))
        self.http.request.assert_not_called()

    def test_stream_cancel_exception_is_not_reclassified_as_network_failure(self):
        class Cancelled(RuntimeError):
            pass
        self.response.iter_content.side_effect = Cancelled('Stopped')
        with self.assertRaises(Cancelled):
            list(self.common.iter_response(self.response, 1024))

    def test_invalid_service_port_does_not_echo_remote_data(self):
        url = 'https://service.test:fixture-private-port/path'
        with self.assertRaises(self.common.CloudRestError) as caught:
            self.common._origin(url)
        self.assertNotIn('fixture-private-port', ''.join(traceback.format_exception(caught.exception)))

    def test_poll_body_read_failure_is_sanitized(self):
        self.response.json.side_effect = TransportFailure('fixture-private-response-body')
        with self.assertRaises(self.common.CloudRestError) as caught:
            self.common.poll_until_done('https://service.test/status', {}, 'state', 'done', 'url')
        self.assertNotIn('fixture-private-response-body', str(caught.exception))
        self.response.close.assert_called_once()

    def test_invalid_media_length_does_not_echo_header_data(self):
        media = load('core/http_media.py', {
            'core.render_context': types.SimpleNamespace(check_cancelled=lambda: None),
            'core.providers.cloud_rest_common': self.common,
        })
        self.response.headers = {'Content-Type': 'audio/wav', 'Content-Length': 'fixture-private-length'}
        pipeline = types.SimpleNamespace(_staged_output=Mock(), _validate_media=Mock())
        with patch.dict(sys.modules, {'core.pipeline': pipeline}):
            with self.assertRaisesRegex(RuntimeError, 'Invalid media Content-Length') as caught:
                media.write_media(self.response, 'unused-output.wav', {'audio'})
        self.assertNotIn('fixture-private-length', ''.join(traceback.format_exception(caught.exception)))
        pipeline._staged_output.assert_not_called()
        self.response.close.assert_called_once()

    def test_media_read_failure_is_sanitized_and_old_output_is_preserved(self):
        media = load('core/http_media.py', {
            'core.render_context': types.SimpleNamespace(check_cancelled=lambda: None),
            'core.providers.cloud_rest_common': self.common,
        })
        self.response.headers = {'Content-Type': 'audio/wav'}
        self.response.iter_content.side_effect = TransportFailure('fixture-private-stream-data')
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'result.wav'
            output.write_bytes(b'previous-result')
            pending = Path(temporary) / 'pending.wav'
            @contextmanager
            def staged(_):
                try:
                    yield str(pending)
                    pending.replace(output)
                finally:
                    pending.unlink(missing_ok=True)
            pipeline = types.SimpleNamespace(_staged_output=staged, _validate_media=Mock())
            with patch.dict(sys.modules, {'core.pipeline': pipeline}):
                with self.assertRaises(self.common.CloudRestError) as caught:
                    media.write_media(self.response, str(output), {'audio'})
            self.assertNotIn('fixture-private-stream-data', str(caught.exception))
            self.assertEqual(output.read_bytes(), b'previous-result')
            self.assertFalse(pending.exists())
        self.response.close.assert_called_once()

    def test_foreign_get_redirect_still_strips_service_credentials(self):
        redirect = Mock(status_code=302, headers={'Location': 'https://assets.test/file'})
        self.http.request.side_effect = [redirect, self.response]
        self.assertIs(self.common.request('GET', 'https://service.test/file', headers={'X-Key': 'fixture-key'}), self.response)
        self.assertEqual(self.http.request.call_args.kwargs['headers'], {})
        redirect.close.assert_called_once()


class PresetPolicyTests(unittest.TestCase):
    def setUp(self):
        self.send = Mock()
        self.send.return_value.json.return_value = {'text': 'clean dialogue'}
        common = types.SimpleNamespace(request=self.send, resolve_credential=Mock(), read_json=lambda response: response.json())
        self.translation = load('core/providers/translation/cloud_rest.py', {
            'core.providers.cloud_rest_common': common,
        })
        self.recognition = load('core/providers/stt/cloud_rest.py', {
            'core.providers.cloud_rest_common': common,
        })
        self.profanity = load('core/providers/profanity_filter/cloud_rest.py', {
            'core.providers.cloud_rest_common': common,
        })
        self.speech = load('core/providers/tts/cloud_rest.py', {
            'core.providers.cloud_rest_common': common,
            'core.http_media': types.SimpleNamespace(write_media=Mock()),
            'core.audio_utils': types.SimpleNamespace(load_speech_audio=Mock()),
        })

    def test_custom_filter_refuses_silent_instruction_omission(self):
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.profanity._custom_request('https://service.test', None, 'dialogue', {}, 'keep the language')
        self.send.assert_not_called()

    def test_custom_filter_refuses_truncated_instruction_placeholder(self):
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.profanity._custom_request('https://service.test', None, 'dialogue',
                {'body': {'text': '{text}', 'policy': '{custom_instructions:.3}'}}, 'keep the language')
        self.send.assert_not_called()

    def test_custom_filter_transmits_exact_policy_and_preserves_text(self):
        result = self.profanity._custom_request('https://service.test', None, 'dialogue',
            {'body': {'text': '{text}', 'policy': '{custom_instructions}'}}, 'keep the language')
        self.assertEqual(result, 'clean dialogue')
        self.assertEqual(self.send.call_args.kwargs['json_body'], {'text': 'dialogue', 'policy': 'keep the language'})

    def test_custom_filter_without_policy_keeps_legacy_body(self):
        self.profanity._custom_request('https://service.test', None, 'dialogue', {})
        self.assertEqual(self.send.call_args.kwargs['json_body'], {'text': 'dialogue'})

    def test_translation_policy_cannot_be_faked_by_matching_source_text(self):
        policy = 'keep the language'
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.translation._custom_request('https://service.test', None, policy, 'Hindi',
                {'body': {'text': '{text}', 'policy': '{text}{custom_instructions:.0}'}}, policy)
        self.send.assert_not_called()

    def test_anonymous_compatible_recognition_omits_fake_authentication(self):
        self.send.return_value.json.return_value = [{'start': 0, 'end': 1, 'text': 'fixture'}]
        with tempfile.TemporaryDirectory() as temporary:
            audio = Path(temporary) / 'fixture.wav'
            audio.write_bytes(b'fixture')
            self.recognition._openai_whisper_request('http://localhost:8000', None, str(audio), {})
        self.assertEqual(self.send.call_args.kwargs['headers'], {})

    def test_anonymous_compatible_tts_omits_fake_authentication(self):
        self.speech._openai_tts_request('http://localhost:8000', None, 'dialogue', 'en', None, {})
        self.assertEqual(self.send.call_args.kwargs['headers'], {})

    def test_authenticated_tts_keeps_real_authorization(self):
        self.speech._openai_tts_request('https://service.test', 'fixture-key', 'dialogue', 'en', None, {})
        self.assertEqual(self.send.call_args.kwargs['headers'], {'Authorization': 'Bearer fixture-key'})


if __name__ == '__main__':
    unittest.main()
