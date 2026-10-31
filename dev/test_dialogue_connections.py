"""Opt-in connections, consent scope, bounded transport and no fallback."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from core.dialogue_connections import connection, fingerprint, readiness, resolve
from core.providers.dialogue_chat import DialogueChatProvider
from core.pipeline_contracts import RegistrySnapshot
from core import settings


def entry(identifier='writer', endpoint='http://localhost:11434', credential=None):
    return dict(id=identifier,stage_type='translation',kind='local_api',status='installed',
        display_name='Test connection',api_base_url=endpoint,credential_ref=credential,
        request_preset='openai_chat',meta={'translation_request':{'model':'explicit-test-model'}})


class ConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.entries=[entry(),entry('reviewer')]
        self.registry=RegistrySnapshot({'entries':self.entries,'active':{}})
        self.values=dict(dialogue_mode='local',dialogue_writer_id='writer',dialogue_reviewer_id='reviewer')

    def test_off_is_default_and_does_not_resolve_or_query(self):
        registry=Mock()
        self.assertEqual(settings.DEFAULTS['dialogue_mode'],'off')
        self.assertEqual(readiness({},registry)['status'],'off')
        registry.get.assert_not_called()
        with self.assertRaises(ValueError):resolve({},registry)

    def test_local_configuration_selects_roles_without_changing_active_translation(self):
        self.assertTrue(readiness(self.values,self.registry)['ready'])
        writer,reviewer=resolve(self.values,self.registry)
        self.assertEqual(writer.service_model,'explicit-test-model')
        self.assertIsNone(self.registry.get_active('translation'))

    def test_explicit_model_and_installed_chat_connection_required(self):
        for changes in ({'status':'not_downloaded'},{'request_preset':'custom'},
                        {'kind':'local_file'},{'meta':{}},{'stage_type':'tts'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):connection({**entry(),**changes},'local')

    def test_local_mode_never_permits_remote_host(self):
        with self.assertRaises(ValueError):connection(entry(endpoint='https://api.example.test',credential='stored-ref'),'local')

    def test_remote_requires_https_credentials_and_clean_url(self):
        for url in ('http://api.example.test','https://user:secret@api.example.test',
                    'https://api.example.test?api_key=secret','https://api.example.test#fragment','https://localhost:bad'):
            with self.subTest(url=url),self.assertRaises(ValueError):connection(entry(endpoint=url,credential='ref'),'hybrid')
        with self.assertRaises(ValueError):connection(entry(endpoint='https://api.example.test'),'hybrid')

    def test_hybrid_consent_is_bound_to_roles_endpoint_and_model(self):
        self.values['dialogue_mode']='hybrid'
        self.assertEqual(readiness(self.values,self.registry)['status'],'needs_consent')
        self.values.update(dialogue_text_consent=True,dialogue_consent_fingerprint=fingerprint(self.values,self.registry))
        self.assertTrue(readiness(self.values,self.registry)['ready'])
        changed=deepcopy(self.entries);changed[0]['api_base_url']='http://localhost:12345'
        registry=RegistrySnapshot({'entries':changed,'active':{}})
        self.assertEqual(readiness(self.values,registry)['status'],'needs_consent')
        changed=deepcopy(self.entries);changed[1]['meta']['translation_request']['model']='different'
        self.assertEqual(readiness(self.values,RegistrySnapshot({'entries':changed,'active':{}}))['status'],'needs_consent')

    def test_offline_blocks_remote_but_keeps_loopback(self):
        self.values['dialogue_mode']='hybrid'
        remote=[entry(endpoint='https://api.example.test',credential='ref'),entry('reviewer')]
        registry=RegistrySnapshot({'entries':remote,'active':{}})
        self.values.update(dialogue_text_consent=True,dialogue_consent_fingerprint=fingerprint(self.values,registry))
        with patch.dict(os.environ,REFLOW_OFFLINE='1'):
            self.assertEqual(readiness(self.values,registry)['status'],'offline')
            self.assertTrue(readiness(dict(self.values,dialogue_mode='local'),self.registry)['ready'])

    def test_settings_reset_consent_when_selection_changes(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(settings,'SETTINGS_PATH',str(Path(folder)/'settings.json')):
            store=settings.Settings()
            store.update({'dialogue_text_consent':True,'dialogue_consent_fingerprint':'old'})
            changed=store.update({'dialogue_writer_id':'new'})
            self.assertFalse(changed['dialogue_text_consent'])
            self.assertEqual(changed['dialogue_consent_fingerprint'],'')
            with self.assertRaises(ValueError):store.update({'dialogue_mode':'automatic-cloud'})

    def test_bridge_computes_consent_and_ignores_forged_fingerprint(self):
        from bridge.api import PythonBridge
        bridge=PythonBridge.__new__(PythonBridge)
        bridge.registry=self.registry
        with tempfile.TemporaryDirectory() as folder,patch.object(settings,'SETTINGS_PATH',str(Path(folder)/'settings.json')):
            bridge.settings=settings.Settings()
            values=dict(self.values,dialogue_mode='hybrid',dialogue_text_consent=True,dialogue_consent_fingerprint='forged')
            saved=bridge.update_settings(values)
            self.assertEqual(saved['dialogue_consent_fingerprint'],fingerprint(saved,self.registry))
            saved=bridge.update_settings({'dialogue_consent_fingerprint':'forged-again'})
            self.assertNotEqual(saved['dialogue_consent_fingerprint'],'forged-again')
            self.assertTrue(bridge.get_dialogue_readiness()['ready'])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.provider=DialogueChatProvider(connection(entry(),'local'))

    def response(self, result, finish='stop'):
        raw=json.dumps({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(result)}}]}).encode()
        response=Mock();response.iter_content.return_value=[raw]
        return response

    def test_writer_sends_text_only_json_with_explicit_model_and_closes_response(self):
        response=self.response({'candidates':['यह ठीक है।']})
        with patch('core.providers.dialogue_chat.request',return_value=response) as request:
            result=self.provider.rewrite_dialogue(source_text='Original',current_text='अनुवाद',available_seconds=2,max_candidates=3)
        self.assertEqual(result,['यह ठीक है।'])
        body=request.call_args.kwargs['json_body']
        self.assertEqual(body['model'],'explicit-test-model')
        self.assertEqual(body['response_format'],{'type':'json_object'})
        self.assertNotIn('files',request.call_args.kwargs)
        self.assertIn('Original',body['messages'][1]['content'])
        self.assertEqual(request.call_count,1)
        response.close.assert_called_once()

    def test_reviewer_keeps_ids_and_original_source(self):
        response=self.response({'opinions':[{'id':'candidate-1','status':'uncertain','reasons':['Missing context']}]})
        with patch('core.providers.dialogue_chat.request',return_value=response) as request:
            result=self.provider.review_dialogue(source_text='English',candidates=[{'id':'candidate-1','text':'हिंदी'}])
        self.assertEqual(result[0]['status'],'uncertain')
        self.assertIn('English',request.call_args.kwargs['json_body']['messages'][1]['content'])

    def test_incomplete_malformed_and_oversized_responses_fail_closed(self):
        responses=[self.response({'candidates':[]},finish='length'),self.response({'candidates':['x']*4})]
        bad=Mock();bad.iter_content.return_value=[b'not JSON'];responses.append(bad)
        big=Mock();big.iter_content.return_value=[b'x'*65537];responses.append(big)
        for response in responses:
            with self.subTest(response=response),patch('core.providers.dialogue_chat.request',return_value=response),self.assertRaises(ValueError):
                self.provider.rewrite_dialogue(source_text='Original')
            response.close.assert_called_once()

    def test_failure_is_not_retried_or_substituted(self):
        with patch('core.providers.dialogue_chat.request',side_effect=RuntimeError('Unavailable')) as request:
            with self.assertRaisesRegex(RuntimeError,'Unavailable'):self.provider.rewrite_dialogue(source_text='Original')
        self.assertEqual(request.call_count,1)

    def test_remote_credential_only_resolved_at_request_time(self):
        provider=DialogueChatProvider(connection(entry(endpoint='https://api.example.test',credential='ref'),'hybrid'))
        response=self.response({'candidates':[]})
        with patch('core.providers.dialogue_chat.resolve_credential',return_value='fixture-secret') as credential,patch('core.providers.dialogue_chat.request',return_value=response) as request:
            provider.rewrite_dialogue(source_text='Original')
        credential.assert_called_once_with('ref')
        self.assertEqual(request.call_args.kwargs['headers']['Authorization'],'Bearer fixture-secret')

    def test_v1_base_is_not_duplicated(self):
        provider=DialogueChatProvider(connection(entry(endpoint='http://localhost:11434/v1'),'local'))
        with patch('core.providers.dialogue_chat.request',return_value=self.response({'candidates':[]})) as request:
            provider.rewrite_dialogue(source_text='Original')
        self.assertEqual(request.call_args.args[1],'http://localhost:11434/v1/chat/completions')

    def test_elapsed_response_limit_closes_without_retry(self):
        response=self.response({'candidates':[]})
        with patch('core.providers.dialogue_chat.time.monotonic',side_effect=[0,61]),patch('core.providers.dialogue_chat.request',return_value=response) as request:
            with self.assertRaises(TimeoutError):self.provider.rewrite_dialogue(source_text='Original')
        response.close.assert_called_once()
        self.assertEqual(request.call_count,1)

    def test_missing_stored_credential_stops_before_http(self):
        provider=DialogueChatProvider(connection(entry(endpoint='https://api.example.test',credential='ref'),'hybrid'))
        with patch('core.providers.dialogue_chat.resolve_credential',side_effect=ValueError('Missing key')),patch('core.providers.dialogue_chat.request') as request:
            with self.assertRaisesRegex(ValueError,'Missing key'):provider.rewrite_dialogue(source_text='Original')
        request.assert_not_called()

    def test_actual_loopback_writer_and_reviewer_with_no_remote_calls(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        from core.dialogue_supervision import supervise
        from types import SimpleNamespace
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append(body)
                payload=json.loads(body['messages'][1]['content'])
                if 'max_candidates' in payload:
                    result={'candidates':['यह ठीक है।']}
                else:
                    result={'opinions':[{'id':c['id'],'status':'preserved','reasons':['Fixture opinion only.'],
                        'evidence':[dict(source_quote=payload['source_text'],candidate_quote=c['text'],relation='equivalent')]} for c in payload['candidates']]}
                raw=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True)
        thread.start()
        try:
            provider=DialogueChatProvider(connection(entry(endpoint=f'http://127.0.0.1:{server.server_port}'),'local'))
            estimate=SimpleNamespace(preserves_native_delivery=True,estimate_duration_seconds=lambda text:len(text)/10)
            result=supervise(estimate,provider,provider,'Original English evidence.',
                'यह मूल अनुवाद बहुत लंबा है और इसका अर्थ कायम रखा जाना चाहिए।',2)
            self.assertEqual(len(received),2)
            self.assertEqual(result['status'],'needs_review')
            self.assertFalse(result['candidates'][0]['approved'])
            self.assertEqual(result['engines']['writer']['service_model'],'explicit-test-model')
            self.assertEqual(received[0]['model'],received[1]['model'])
        finally:
            server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
