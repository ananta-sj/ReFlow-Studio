"""Foundation tests with disposable state; no downloads or live inference."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
import pipeline
from core.pipeline_contracts import (PipelineSpec, RegistrySnapshot, SettingsSnapshot,
    identify_cues, finalize_grouped_cues, template_kwargs)
from core.run_manifest import RunManifest, observe_provider, bind_manifest, current_manifest
from core import run_manifest as run_records
from core.transcription import TranscriptionResult
from core.render_context import RenderCancelled


class PipelineFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.srt'
        self.source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello world.\n\n', encoding='utf-8')
        self.registry = RegistrySnapshot({'entries': [], 'active': {}})
        self.settings = SettingsSnapshot({'whisper_model_size': 'tiny', 'ollama_host': 'http://secret:token@localhost'})

    def manifest(self):
        return RunManifest(self.root / 'records', PipelineSpec('subtitle_translate'),
                           self.source, self.registry, self.settings)

    def subject(self):
        subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        subject.output_dir = str(self.root)
        subject.registry = Mock()
        subject.registry.snapshot.return_value = self.registry
        subject.clear_vram = Mock()
        return subject

    def test_plan_freezes_nested_parameters_and_returns_copies(self):
        params = {'cast_list': ['voice-one'], 'sub_style': {'font_size': 20}}
        spec = PipelineSpec('video_dub', params)
        params['cast_list'].append('voice-two')
        spec.parameters['sub_style']['font_size'] = 80
        self.assertEqual(spec.parameters['cast_list'], ['voice-one'])
        self.assertEqual(spec.parameters['sub_style']['font_size'], 20)

    def test_plan_routes_all_four_templates_and_forces_lipsync(self):
        for name, kind in [('video_dub', 'video'), ('video_dub_lipsync', 'video'),
                           ('audio_dub', 'audio'), ('subtitle_translate', 'subtitle')]:
            spec = PipelineSpec(name)
            self.assertEqual(spec.to_payload()['input_kind'], kind)
        self.assertTrue(PipelineSpec('video_dub_lipsync', {'lip_sync_active': False}).parameters['lip_sync_active'])
        self.assertNotIn('translation', PipelineSpec('audio_dub', {'target_lang': 'source'}).to_payload()['stages'])
        self.assertEqual(PipelineSpec('audio_dub', {'compute_device': 'other:adapter'}).parameters['compute_device'], 'cpu')
        fallback = PipelineSpec('audio_dub', {'compute_device': 'other:adapter'}).to_payload()
        self.assertEqual(fallback['requested_parameters']['compute_device'], 'other:adapter')
        self.assertIn('using CPU', fallback['warnings'][0])

    def test_unknown_template_and_parameter_fail_before_execution(self):
        with self.assertRaises(ValueError):
            PipelineSpec('invented')
        with self.assertRaises(TypeError):
            PipelineSpec('audio_dub', {'lip_sync_active': True})

    def test_shared_frontend_mapping_resolves_cast_only_for_media(self):
        resolver = Mock(return_value=['voice'])
        for name in ('video_dub', 'video_dub_lipsync', 'audio_dub'):
            mapped = template_kwargs(name, {'lang': 'hi', 'source_language': 'en'}, resolver)
            self.assertEqual(PipelineSpec(name, mapped).parameters['cast_list'], ['voice'])
        self.assertEqual(resolver.call_count, 3)
        template_kwargs('subtitle_translate', {'lang': 'hi'}, resolver)
        self.assertEqual(resolver.call_count, 3)

    def test_registry_and_settings_snapshot_cannot_drift(self):
        entry = dict(id='one', stage_type='tts', display_name='One', kind='local_file', meta={'speech_device': 'cpu'})
        data = {'entries': [entry], 'active': {'tts': 'one'}}
        frozen = RegistrySnapshot(data)
        data['active']['tts'] = None
        frozen.get_active('tts')['meta']['speech_device'] = 'cuda'
        self.assertEqual(frozen.get_active('tts')['meta']['speech_device'], 'cpu')
        self.settings.all()['whisper_model_size'] = 'large'
        self.assertEqual(self.settings.get('whisper_model_size'), 'tiny')

    def test_cue_identity_survives_reordering_and_group_has_lineage(self):
        raw = identify_cues([{'start': 0, 'end': 1, 'text': 'Hello'},
                             {'start': 1, 'end': 2, 'text': 'world.'}])
        self.assertEqual(identify_cues(list(reversed(raw)))[0]['cue_id'], raw[1]['cue_id'])
        merged = finalize_grouped_cues(pipeline.ReflowPipeline._merge_short_segments(raw))
        self.assertEqual(merged[0]['source_text'], 'Hello world.')
        self.assertEqual(merged[0]['parent_ids'], [cue['cue_id'] for cue in raw])
        self.assertNotIn(merged[0]['cue_id'], merged[0]['parent_ids'])
        self.assertEqual(raw[0]['text'], 'Hello')

    def test_sentence_grouping_keeps_raw_fragment_identity(self):
        from core.sentence_grouping import group_sentences
        raw = identify_cues([{'start': 0, 'end': 1, 'text': 'This is'},
                             {'start': 1, 'end': 3, 'text': 'one sentence.'}])
        grouped = finalize_grouped_cues(group_sentences(TranscriptionResult(raw, 'en')))
        self.assertEqual(grouped[0]['parent_ids'], [cue['cue_id'] for cue in raw])
        self.assertEqual(grouped[0]['source_fragments'][1]['text'], 'one sentence.')

    def test_cue_identity_is_scoped_to_source_and_untrusted_fields_do_not_replace_evidence(self):
        raw = [{'start': 0, 'end': 1, 'text': 'Actual source', 'source_text': 'Invented', 'cue_id': 'provider-one'}]
        first, second = identify_cues(raw, 'source-one')[0], identify_cues(raw, 'source-two')[0]
        self.assertNotEqual(first['cue_id'], second['cue_id'])
        self.assertEqual(first['source_text'], 'Actual source')
        self.assertEqual(first['provider_cue_id'], 'provider-one')

    def test_native_preflight_failure_records_the_cue_and_duration_budget(self):
        record = self.manifest()
        provider = Mock(preserves_native_delivery=True)
        provider.estimate_duration_seconds.return_value = 3.0
        cues = identify_cues([{'start': 0, 'end': 1, 'text': 'Too long'}])
        with bind_manifest(record), self.assertRaisesRegex(RuntimeError, 'predicted'):
            pipeline._preflight_native_cue_durations(provider, cues, ['CLONED_USER'])
        self.assertEqual(record.data['operations'][0]['stage'], 'dialogue')
        self.assertEqual(record.data['operations'][0]['status'], 'failed')
        self.assertTrue(record.data['review_required'])
        item = next(op for op in record.data['operations'] if op['stage']=='timing-preflight')
        self.assertEqual(item['status'], 'completed')
        self.assertEqual(item['evidence']['cue_id'], cues[0]['cue_id'])
        self.assertEqual(item['predicted_seconds'], 3.0)
        self.assertEqual(item['evidence']['available_seconds'], 1)

    def test_translation_and_moderation_keep_original_and_raw_translation(self):
        cue = identify_cues([{'start': 0, 'end': 2, 'text': 'Original'}])[0]
        translator, moderator = Mock(), Mock()
        translator.translate.return_value = 'Raw translation'
        moderator.filter_text.return_value = 'Moderated translation'
        output = pipeline.ReflowPipeline._translate_line(cue['text'], 'Hindi', translator, '', moderator, '', cue=cue)
        self.assertEqual(output, 'Moderated translation')
        self.assertEqual(cue['source_text'], 'Original')
        self.assertEqual(cue['translated_text'], 'Raw translation')
        self.assertEqual(cue['adapted_text'], 'Moderated translation')

    def test_provider_failure_and_partial_translation_evidence_survive(self):
        record = self.manifest()
        provider = Mock()
        provider.translate.side_effect = ['First translated', RuntimeError('token should not enter receipts')]
        with bind_manifest(record):
            observe_provider(record, 'translation', provider, 'translate', 'First', 'Hindi', cue_id='cue-one')
            with self.assertRaises(RuntimeError):
                observe_provider(record, 'translation', provider, 'translate', 'Second', 'Hindi', cue_id='cue-two')
        saved = json.loads(record.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['operations'][0]['result_text'], 'First translated')
        self.assertEqual(saved['operations'][1]['status'], 'failed')
        self.assertNotIn('token should', record.path.read_text(encoding='utf-8'))
        self.assertIsNone(current_manifest())

    def test_failed_recognition_retains_actual_worker_evidence(self):
        record = self.manifest()
        provider = Mock()
        provider.last_result = {'transcription': {'segments': [{'start': 0, 'end': 1, 'text': '...'}],
            'language': 'en', 'language_probability': .31}}
        provider.transcribe.side_effect = ValueError('No spoken words')
        with self.assertRaises(ValueError):
            observe_provider(record, 'stt', provider, 'transcribe', str(self.source))
        artifact = record.data['cue_artifacts'][0]
        self.assertEqual(artifact['phase'], 'recognition-worker-failed')
        self.assertEqual(json.loads(Path(artifact['path']).read_text(encoding='utf-8'))['segments'][0]['text'], '...')

    def test_selected_secrets_are_omitted_but_configuration_identity_retained(self):
        entry = dict(id='one', stage_type='translation', kind='cloud_api', display_name='Service',
            credential_ref='private-key', api_base_url='https://secret/token', meta={'headers': {'Authorization': 'secret'}},
            request_preset={'headers': {'Authorization': 'secret'}}, custom_instructions='private instruction')
        self.registry = RegistrySnapshot({'entries': [entry], 'active': {'translation': 'one'}})
        record = self.manifest()
        raw = record.path.read_text(encoding='utf-8')
        for secret in ('private-key', 'https://secret', 'Authorization', 'private instruction', 'secret:token'):
            self.assertNotIn(secret, raw)
        self.assertEqual(len(record.data['selected_engines']['translation']['configuration_sha256']), 64)

    def test_speech_observation_keeps_hash_and_pcm_duration_after_file_removal(self):
        record = self.manifest()
        path = self.root / 'speech.wav'
        def synthesize(text, output, **kwargs):
            with wave.open(str(output), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x01\x00' * 1600)
            return str(output)
        provider = Mock()
        provider.synthesize.side_effect = synthesize
        observe_provider(record, 'speech', provider, 'synthesize', 'Hello', str(path), cue_id='cue-one')
        expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        path.unlink()
        saved = record.data['operations'][0]['artifact']
        self.assertEqual(saved['sha256'], expected_hash)
        self.assertEqual(saved['duration_seconds'], .1)
        self.assertEqual(saved['retention'], 'temporary-unless-exported')

    def test_cue_artifacts_are_durable_copies(self):
        record = self.manifest()
        cues = identify_cues([{'start': 0, 'end': 1, 'text': 'Original'}])
        record.cues('source', cues)
        cues[0]['source_text'] = 'Changed'
        saved = json.loads(Path(record.data['cue_artifacts'][0]['path']).read_text(encoding='utf-8'))
        self.assertEqual(saved['segments'][0]['source_text'], 'Original')

    def test_parallel_observations_keep_all_operation_results(self):
        record = self.manifest()
        def run(index):
            with record.operation('speech', evidence={'cue_id': str(index)}) as item:
                item['result_text'] = 'result-' + str(index)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(run, range(16)))
        saved = json.loads(record.path.read_text(encoding='utf-8'))
        self.assertEqual(len(saved['operations']), 16)
        self.assertEqual({item['status'] for item in saved['operations']}, {'completed'})
        self.assertEqual({item['result_text'] for item in saved['operations']}, {'result-'+str(i) for i in range(16)})

    def test_actual_translation_fallback_is_recorded_after_call(self):
        record = self.manifest()
        class Provider:
            def translate(self, text, target):
                self._translator = type('Translator', (), {'mode': 'm2m100', 'model_name': 'fallback-model', 'device': 'cpu'})()
                return 'Translated'
        observe_provider(record, 'translation', Provider(), 'translate', 'Original', 'Hindi')
        self.assertEqual(record.data['operations'][0]['engine']['translation_mode'], 'm2m100')

    def test_durable_record_failure_prevents_unrecorded_inference(self):
        record = self.manifest()
        provider = Mock()
        with patch('core.run_manifest.atomic_bytes', side_effect=OSError('disk full')), self.assertRaises(OSError):
            observe_provider(record, 'translation', provider, 'translate', 'Original', 'Hindi')
        provider.translate.assert_not_called()

    def test_transient_windows_rename_denial_retries_and_publishes_complete_json(self):
        record = self.manifest()
        error = PermissionError('File temporarily held')
        error.winerror = 32
        real_publish = run_records.atomic_bytes
        calls = []
        def publish(path, content):
            calls.append(path)
            if len(calls) == 1:
                raise error
            real_publish(path, content)
        record.data['note'] = 'complete content'
        with patch('core.run_manifest.atomic_bytes', side_effect=publish), patch('core.run_manifest.os.name', 'nt'), \
                patch('core.run_manifest.time.sleep'):
            record.save()
        self.assertEqual(len(calls), 2)
        self.assertEqual(json.loads(record.path.read_text(encoding='utf-8'))['note'], 'complete content')

    def test_persistent_windows_rename_denial_is_bounded_and_keeps_previous_record(self):
        record = self.manifest()
        previous = record.path.read_bytes()
        error = PermissionError('Still held')
        error.winerror = 5
        with patch('core.run_manifest.atomic_bytes', side_effect=error) as publish, \
                patch('core.run_manifest.os.name', 'nt'), patch('core.run_manifest.time.sleep'), self.assertRaises(PermissionError):
            record.save()
        self.assertEqual(publish.call_count, 4)
        self.assertEqual(record.path.read_bytes(), previous)

    def test_real_subtitle_template_runs_through_plan_and_records_output(self):
        subject = self.subject()
        original_registry = subject.registry
        with patch.object(pipeline, 'Settings', return_value=self.settings), patch('core.runtime_checks.preflight'):
            events = list(subject.run('subtitle_translate', str(self.source), {'target_lang': 'source'}))
        output = Path(events[-1][2])
        self.assertTrue(output.is_file())
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['source']['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(record['output']['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertIs(subject.registry, original_registry)
        self.assertTrue(record['checkpoint_support'])

    def test_generator_close_records_cancellation_and_restores_selection(self):
        subject = self.subject()
        original_registry = subject.registry
        def render(*args, **kwargs):
            yield 10, 'Working', None
            raise AssertionError('Closed generator must not continue')
        subject.process_video_gen = render
        with patch.object(pipeline, 'Settings', return_value=self.settings):
            generator = subject.run('video_dub', str(self.source))
            next(generator)
            generator.close()
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'cancelled')
        self.assertIs(subject.registry, original_registry)
        self.assertIsNone(current_manifest())

    def test_no_output_is_a_failed_run_not_a_success(self):
        subject = self.subject()
        subject.process_video_gen = lambda *args, **kwargs: iter([(0, 'Failed', None)])
        with patch.object(pipeline, 'Settings', return_value=self.settings), self.assertRaisesRegex(RuntimeError, 'without output'):
            list(subject.run('video_dub', str(self.source)))
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'failed')
        self.assertIsNone(record['output'])

    def test_missing_source_failure_has_a_run_record(self):
        subject = self.subject()
        with patch.object(pipeline, 'Settings', return_value=self.settings), self.assertRaises(FileNotFoundError):
            list(subject.run('subtitle_translate', str(self.root/'missing.srt')))
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['operations'][0]['status'], 'failed')

    def test_failed_manifest_creation_leaves_pipeline_state_untouched(self):
        subject = self.subject()
        original_registry = subject.registry
        with patch.object(pipeline, 'Settings', return_value=self.settings), \
                patch.object(pipeline, 'RunManifest', side_effect=OSError('disk full')), self.assertRaises(OSError):
            list(subject.run('subtitle_translate', str(self.source)))
        self.assertIs(subject.registry, original_registry)
        self.assertFalse(hasattr(subject, '_manifest'))

    def test_run_cancel_exception_has_cancelled_status(self):
        subject = self.subject()
        def render(*args, **kwargs):
            raise RenderCancelled('Stopped')
            yield
        subject.process_audio_dub_gen = render
        with patch.object(pipeline, 'Settings', return_value=self.settings), self.assertRaises(RenderCancelled):
            list(subject.run('audio_dub', str(self.source)))
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'cancelled')

    def test_closing_subtitle_run_between_cues_releases_stage_worker(self):
        subject = self.subject()
        original_registry = subject.registry
        provider = Mock(engine_id='indictrans2')
        provider.translate.return_value = 'Hindi fixture translation'
        subject._resolve_translation_and_filter = Mock(return_value=(provider, '', None, ''))
        with patch.object(pipeline, 'Settings', return_value=self.settings), patch('core.runtime_checks.preflight'):
            running = subject.run('subtitle_translate', str(self.source), {'target_lang':'hi', 'source_language':'en'})
            self.assertEqual(next(running)[1], 'PARSING SUBTITLES')
            self.assertEqual(next(running)[1], 'AI TRANSLATING')
            self.assertIn('TRANSLATING CUE', next(running)[1])
            provider.release.assert_not_called()
            running.close()
        provider.release.assert_called_once()
        self.assertIs(subject.registry, original_registry)
        record = json.loads(Path(subject.last_manifest_path).read_text(encoding='utf-8'))
        self.assertEqual(record['status'], 'cancelled')
        self.assertIsNone(record['output'])
        self.assertFalse(list(self.root.glob('*_TRANSLATED_*.srt')))


if __name__ == '__main__':
    unittest.main()
