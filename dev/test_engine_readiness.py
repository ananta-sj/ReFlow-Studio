"""Inspect route contracts without model inference, installation or HTTP."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from core.engine_readiness import inspect


class EngineReadinessTests(unittest.TestCase):
    def test_isolated_xtts_inspection_binds_recipe_without_inference(self):
        with patch.dict('os.environ', {'REFLOW_XTTS_RUNTIME': 'isolated'}), patch('core.xtts_runtime.validate', return_value={'identity': 'recipe'}), patch('core.engine_readiness.preflight_speech'), patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.runtime_probe.probe') as probe:
            result = inspect(self.registry(), 'audio_dub', {'target_lang': 'en', 'source_language': 'en', 'keep_background': False, 'compute_device': 'cpu'}, verify_runtime=True)
        row = next(row for row in result['checks'] if row['stage'] == 'speech')
        self.assertEqual(row['runtime']['identity'], 'recipe')
        self.assertEqual(row['runtime']['status'], 'unverified')
        probe.assert_not_called()

    def test_unavailable_isolated_xtts_reports_setup_problem(self):
        with patch.dict('os.environ', {'REFLOW_XTTS_RUNTIME': 'isolated'}), patch('core.xtts_runtime.validate', side_effect=RuntimeError('Runtime missing')), patch('core.engine_readiness.shutil.which', return_value='fixture'):
            result = inspect(self.registry(), 'audio_dub', {'target_lang': 'en', 'keep_background': False, 'compute_device': 'cpu'})
        row = next(row for row in result['checks'] if row['stage'] == 'speech')
        self.assertEqual(row['status'], 'needs_setup')

    def test_isolated_xtts_inspection_rejects_gpu(self):
        with patch.dict('os.environ', {'REFLOW_XTTS_RUNTIME': 'isolated'}), patch('core.engine_readiness.shutil.which', return_value='fixture'):
            result = inspect(self.registry(), 'audio_dub', {'target_lang': 'en', 'keep_background': False, 'compute_device': 'cuda:0'})
        row = next(row for row in result['checks'] if row['stage'] == 'speech')
        self.assertEqual(row['status'], 'needs_setup')
        self.assertIn('CPU only', row['details'][0])

    def registry(self, entries=None, voices=()):
        entries = entries or {}
        return Mock(get_active=Mock(side_effect=lambda stage: entries.get(stage)),
                    list=Mock(return_value=list(voices)))

    def entry(self, stage, **values):
        return dict(stage_type=stage, display_name=stage, status='installed', kind='local_file', **values)

    def test_subtitles_do_not_inspect_media_speech_or_recognition(self):
        with patch('core.engine_readiness.shutil.which') as which:
            result = inspect(self.registry(), 'subtitle_translate', {'target_lang': 'source'})
        self.assertEqual(result['checks'], [])
        which.assert_not_called()
        self.assertFalse(result['live_checks'])

    def test_missing_media_is_reported_without_aborting_other_checks(self):
        with patch('core.engine_readiness.shutil.which', return_value=None):
            result = inspect(self.registry(), 'audio_dub', {'target_lang': 'hi', 'keep_background': False})
        self.assertEqual(result['status'], 'needs_setup')
        self.assertEqual(result['checks'][0]['status'], 'needs_setup')
        self.assertIn('speech', [row['stage'] for row in result['checks']])

    def test_cloud_configuration_does_not_contact_or_resolve_credentials(self):
        entry = self.entry('translation', api_base_url='https://example.test', request_preset='openai_chat')
        entry['kind'] = 'cloud_api'
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '0'}), patch('core.providers.cloud_rest_common.request') as request, patch('core.providers.cloud_rest_common.resolve_credential') as credential:
            result = inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi'})
        self.assertEqual(result['checks'][0]['status'], 'unverified')
        request.assert_not_called()
        credential.assert_not_called()

    def test_offline_remote_connection_is_blocked(self):
        entry = self.entry('translation', api_base_url='https://example.test', request_preset='openai_chat')
        entry['kind'] = 'cloud_api'
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '1'}):
            result = inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi'})
        self.assertEqual(result['checks'][0]['status'], 'needs_setup')

    def test_indictrans_route_rejects_unsupported_source_and_target(self):
        entry = self.entry('translation', local_path='fixture')
        with patch('core.engine_readiness.local_contract', return_value={'adapter': 'indictrans2'}):
            for params in ({'target_lang': 'fr'}, {'target_lang': 'hi', 'source_language': 'ta'}):
                result = inspect(self.registry({'translation': entry}), 'subtitle_translate', params)
                self.assertEqual(result['checks'][0]['status'], 'needs_setup')

    def test_absent_isolated_runtime_is_not_labelled_checked(self):
        entry = self.entry('translation', local_path='fixture')
        with patch('core.engine_readiness.local_contract', return_value={'adapter': 'indictrans2'}), patch('core.indictrans2_assets.isolated_interpreter', side_effect=RuntimeError('Runtime missing')):
            result = inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi', 'source_language': 'en'})
        self.assertEqual(result['checks'][0]['status'], 'needs_setup')

    def test_local_subtitles_require_explicit_source(self):
        entry = self.entry('translation', local_path='fixture')
        with patch('core.engine_readiness.local_contract', return_value={'adapter': 'nllb'}):
            result = inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi'})
        self.assertEqual(result['checks'][0]['status'], 'needs_setup')
        self.assertIn('source language', result['checks'][0]['details'][0])

    def test_file_inspection_never_launches_runtime_probe(self):
        entry = self.entry('translation', local_path='fixture')
        with patch('core.engine_readiness.local_contract', return_value={'adapter': 'indictrans2'}), patch('core.indictrans2_assets.isolated_interpreter', return_value='fixture'), patch('core.runtime_probe.probe') as probe:
            inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi', 'source_language': 'en'})
        probe.assert_not_called()

    def test_builtin_filter_routes_to_cpu_optional_runtime_without_loading_detector(self):
        with patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.optional_runtime.interpreter', return_value='vision-python'), patch('core.runtime_probe.probe', return_value={'status': 'passed'}) as probe:
            result = inspect(self.registry(), 'video_dub', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False, 'compute_device': 'cuda:0', 'content_filter_active': True}, verify_runtime=True)
        probe.assert_called_once_with('nudenet', 'vision-python', 'cpu')
        row = next(row for row in result['checks'] if row['stage'] == 'filter')
        self.assertEqual(row['runtime']['status'], 'passed')
        self.assertEqual(row['status'], 'unverified')  # No checkpoint/detector was opened.

    def test_enabled_builtin_features_are_scoped_and_api_routes_are_not_probed(self):
        entry = self.entry('enhancer', api_base_url='https://example.test', request_preset='custom')
        entry['kind'] = 'cloud_api'
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '0'}), patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.runtime_probe.probe') as probe:
            result = inspect(self.registry({'enhancer': entry}), 'video_dub', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False, 'enhance_active': True}, verify_runtime=True)
        probe.assert_not_called()
        self.assertEqual(next(row for row in result['checks'] if row['stage'] == 'enhancer')['status'], 'unverified')

    def test_rvc_dependency_probe_does_not_load_checkpoint_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'voice.pth'
            path.write_bytes(b'fixture')
            voice = self.entry('voice', id='speaker', local_path=str(path), request_preset='rvc')
            with patch('core.engine_readiness.local_contract') as contract, patch('core.engine_readiness.preflight_speech'), patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.python_runtime.inprocess_python', return_value='core-python'), patch('core.runtime_probe.probe', return_value={'status': 'passed'}) as probe:
                result = inspect(self.registry(voices=[voice]), 'audio_dub', {'target_lang': 'hi', 'keep_background': False, 'cast_list': ['speaker'], 'compute_device': 'cpu'}, verify_runtime=True)
            contract.assert_not_called()
            probe.assert_called_once_with('rvc', 'core-python', 'cpu')
            self.assertEqual(next(row for row in result['checks'] if row['stage'] == 'voice')['status'], 'unverified')

    def test_unsupported_probe_device_remains_unverified_rather_than_broken(self):
        with patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.python_runtime.worker_python', return_value='core-python'), patch('core.runtime_probe.probe') as probe:
            result = inspect(self.registry(), 'video_dub', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False, 'enhance_active': True, 'compute_device': 'cuda:1'}, verify_runtime=True)
        probe.assert_not_called()
        row = next(row for row in result['checks'] if row['stage'] == 'enhancer')
        self.assertEqual(row['status'], 'unverified')
        self.assertEqual(row['runtime']['status'], 'unverified')

    def test_shared_rvc_runtime_is_probed_once_per_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'voice.pth'
            path.write_bytes(b'fixture')
            voices = [self.entry('voice', id=identifier, local_path=str(path), request_preset='rvc') for identifier in ('one', 'two')]
            with patch('core.engine_readiness.preflight_speech'), patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.runtime_probe.probe', return_value={'status': 'passed', 'versions': {}}) as probe:
                result = inspect(self.registry(voices=voices), 'audio_dub', {'target_lang': 'hi', 'keep_background': False, 'cast_list': ['one', 'two']}, verify_runtime=True)
            self.assertEqual(probe.call_count, 1)
            rows = [row for row in result['checks'] if row['stage'] == 'voice']
            self.assertEqual(len(rows), 2)
            self.assertIsNot(rows[0]['runtime'], rows[1]['runtime'])

    def test_frozen_inprocess_dependencies_are_not_claimed_by_a_worker_override(self):
        with patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.python_runtime.inprocess_python', return_value=None), patch('core.runtime_probe.probe') as probe:
            result = inspect(self.registry(), 'video_dub', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False, 'enhance_active': True}, verify_runtime=True)
        probe.assert_not_called()
        self.assertEqual(next(row for row in result['checks'] if row['stage'] == 'enhancer')['runtime']['status'], 'unverified')

    def test_selected_musetalk_uses_optional_runtime_and_requested_device(self):
        entry = self.entry('lipsync', local_path='fixture')
        with patch('core.engine_readiness.shutil.which', return_value='fixture'), patch('core.engine_readiness.local_contract', return_value={'adapter': 'musetalk'}), patch('core.optional_runtime.interpreter', return_value='muse-python'), patch('core.runtime_probe.probe', return_value={'status': 'passed'}) as probe:
            result = inspect(self.registry({'lipsync': entry}), 'video_dub_lipsync', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False, 'compute_device': 'cpu'}, verify_runtime=True)
        probe.assert_called_once_with('musetalk', 'muse-python', 'cpu')
        self.assertEqual(next(row for row in result['checks'] if row['stage'] == 'lipsync')['runtime']['status'], 'passed')

    def test_failed_runtime_is_reported_with_setup_guidance(self):
        entry = self.entry('translation', local_path='fixture')
        with patch('core.engine_readiness.local_contract', return_value={'adapter': 'indictrans2'}), patch('core.indictrans2_assets.isolated_interpreter', return_value='fixture'), patch('core.runtime_probe.probe', return_value={'status': 'failed', 'problems': ['No GPU']}):
            result = inspect(self.registry({'translation': entry}), 'subtitle_translate', {'target_lang': 'hi', 'source_language': 'en'}, verify_runtime=True)
        self.assertEqual(result['status'], 'needs_setup')
        self.assertIn('No GPU', result['checks'][0]['details'])
        self.assertIn('no installation', result['checks'][0]['guidance'].lower())

    def test_rvc_inventory_does_not_load_tensor_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'voice.pth'
            path.write_bytes(b'fixture')
            voice = self.entry('voice', id='speaker', local_path=str(path), request_preset='rvc')
            with patch('core.engine_readiness.local_contract') as contract, patch('core.engine_readiness.preflight_speech'), patch('core.engine_readiness.shutil.which', return_value='fixture'):
                result = inspect(self.registry(voices=[voice]), 'audio_dub', {'target_lang': 'hi', 'keep_background': False, 'cast_list': ['speaker']})
            contract.assert_not_called()
            self.assertEqual(next(row for row in result['checks'] if row['stage'] == 'voice')['status'], 'unverified')

    def test_lipsync_template_forces_selected_stage(self):
        with patch('core.engine_readiness.shutil.which', return_value='fixture'):
            result = inspect(self.registry(), 'video_dub_lipsync', {'target_lang': 'source', 'source_language': 'auto', 'keep_background': False})
        self.assertIn('lipsync', [row['stage'] for row in result['checks']])
        speech = next(row for row in result['checks'] if row['stage'] == 'speech')
        self.assertEqual(speech['status'], 'unverified')

    def test_bridge_freezes_registry_and_reuses_execution_cast_mapping(self):
        from bridge.api import PythonBridge
        bridge = PythonBridge.__new__(PythonBridge)
        bridge.registry = Mock()
        bridge.settings = Mock()
        bridge.settings.get.return_value = 'legacy'
        bridge.get_cast_list = Mock(return_value=['one', 'two'])
        with patch('core.engine_readiness.inspect', return_value={'status': 'inspection_complete'}) as inspection:
            bridge.get_engine_readiness({'voice': 'CLONED_USER', 'lang': 'hi'}, 'video_dub_lipsync')
        args = inspection.call_args.args
        self.assertIs(args[0], bridge.registry.snapshot.return_value)
        self.assertEqual(args[2]['cast_list'], ['one', 'two'])
        # PipelineSpec performs the same forced lip-sync expansion as execution.
        self.assertEqual(args[1], 'video_dub_lipsync')
        self.assertEqual(inspection.call_args.kwargs['xtts_runtime'], 'legacy')


if __name__ == '__main__':
    unittest.main()
