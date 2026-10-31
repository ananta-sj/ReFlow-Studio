"""Architecture repair contracts with disposable media and simulated services."""
from contextlib import ExitStack
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile
import threading
import time
import sys
from concurrent.futures import ThreadPoolExecutor

from core import downloader, integrity, srt_utils
from core.providers import cloud_rest_common as cloud
from core.providers.label_contract import positive_index
from dev.test_render_queue import api
import pipeline


class ArchitectureContracts(unittest.TestCase):
    def test_graph_recognition_label_tracks_selection_without_mutating_saved_values(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock = threading.RLock()
        bridge.graph = api.build_default_graph()
        bridge.registry = Mock()
        bridge.registry.list.return_value = []
        bridge.registry.get_active.return_value = {'display_name': 'Pinned GPU recognition'}
        original = dict(bridge.graph.nodes['stt'].values)
        definition = bridge.get_graph_definition()
        recognition = next(node for node in definition['nodes'] if node['id'] == 'stt')
        self.assertEqual(recognition['params'][0]['default'], 'Pinned GPU recognition')
        self.assertEqual(bridge.graph.nodes['stt'].values, original)
        bridge.registry.get_active.return_value = None
        definition = bridge.get_graph_definition()
        recognition = next(node for node in definition['nodes'] if node['id'] == 'stt')
        self.assertEqual(recognition['params'][0]['default'], 'Built-in Whisper (CPU)')

    def test_estimate_counts_separation_and_always_counts_audio_mastering(self):
        without = api._active_stages({'lang': 'source', 'keep_bg': False})
        self.assertIn('mix', without)
        self.assertNotIn('translate', without)
        self.assertNotIn('separate', without)
        with_background = api._active_stages({'lang': 'en', 'keep_bg': True})
        self.assertIn('mix', with_background)
        self.assertIn('separate', with_background)
        with patch('subprocess.check_output', return_value=b'nan'):
            self.assertEqual(api._probe_duration('fixture'), 0)

    def test_frozen_worker_requires_real_python_instead_of_relaunching_app(self):
        from core import python_runtime
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'REFLOW_WORKER_PYTHON': ''}), \
             patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(Path(folder) / 'ReflowStudio.exe')):
            with self.assertRaisesRegex(RuntimeError, 'worker runtime'):
                python_runtime.worker_python()
            interpreter = Path(folder) / 'build/windows-portable/python.exe'
            interpreter.parent.mkdir(parents=True)
            interpreter.write_bytes(b'fixture')
            self.assertEqual(python_runtime.worker_python(), str(interpreter))
            with patch.dict('os.environ', {'REFLOW_WORKER_PYTHON': sys.executable}):
                with self.assertRaisesRegex(RuntimeError, 'real, absolute'):
                    python_runtime.worker_python()

    def test_offline_remote_request_and_redirect_are_blocked_before_http(self):
        from core.network_policy import require_network_allowed
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '1'}):
            for url in ('http://localhost:11434', 'http://127.0.0.1:8000', 'http://[::1]:8000'):
                require_network_allowed(url)
            with patch.object(cloud.requests, 'request') as request:
                with self.assertRaisesRegex(RuntimeError, 'Offline'):
                    cloud.request('GET', 'https://remote.example/status')
                request.assert_not_called()
            response = Mock(status_code=302, headers={'Location': 'https://remote.example/file'})
            with patch.object(cloud.requests, 'request', return_value=response) as request:
                with self.assertRaisesRegex(RuntimeError, 'Offline'):
                    cloud.request('GET', 'http://localhost:8000/file')
                self.assertEqual(request.call_count, 1)

    def test_cloud_completion_requires_result_and_resolves_relative_url(self):
        response = Mock()
        response.json.return_value = {'status': 'done', 'url': '/files/output.mp4'}
        with patch.object(cloud, 'request', return_value=response):
            self.assertEqual(cloud.poll_until_done('/status', {}, 'status', 'done', 'url',
                service_url='https://service.example'), 'https://service.example/files/output.mp4')
        response.json.return_value = {'status': 'done'}
        with patch.object(cloud, 'request', return_value=response), self.assertRaisesRegex(cloud.CloudRestError, 'result URL'):
            cloud.poll_until_done('/status', {}, 'status', 'done', 'url', service_url='https://service.example')

    def test_gpu_discount_applies_only_to_routed_gpu_stages(self):
        from core.hardware_monitor import HardwareMonitor, GPUDevice
        monitor = HardwareMonitor.__new__(HardwareMonitor)
        monitor.devices = [GPUDevice('cpu', 'CPU', 'cpu', 'cpu'), GPUDevice('cuda:0', 'GPU', 'dedicated', 'cuda')]
        result = monitor.estimate_eta_seconds(100, ['stt', 'tts_rvc'], 'cuda:0',
            stage_device_overrides={'stt': 'cpu'})
        self.assertEqual(result, 80)  # 100*(0.5 CPU + 1.5*0.2 GPU).

    def test_workers_increase_ram_buffers_without_vram_or_speed_discount(self):
        from core.hardware_monitor import HardwareMonitor, GPUDevice
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        monitor = HardwareMonitor.__new__(HardwareMonitor)
        monitor.devices = [GPUDevice('cuda:0', 'GPU', 'dedicated', 'cuda')]
        bridge.monitor = monitor
        bridge.registry = Mock()
        bridge.registry.get_active.return_value = None
        bridge.registry.get_active_map.return_value = {}
        one = bridge._resource_estimate(100, ['tts_rvc'], 'cuda:0', {'parallel_workers': 1})
        four = bridge._resource_estimate(100, ['tts_rvc'], 'cuda:0', {'parallel_workers': 4})
        self.assertEqual(one['eta_seconds'], four['eta_seconds'])
        self.assertEqual(one['peak_vram_mb'], four['peak_vram_mb'])
        self.assertGreater(four['audio_buffer_ram_mb'], one['audio_buffer_ram_mb'])
        with self.assertRaises(ValueError):
            bridge._resource_estimate(100, [], 'cuda:0', {'parallel_workers': True})

    def test_resource_estimate_uses_cast_and_counts_unique_models(self):
        from core.hardware_monitor import HardwareMonitor
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge.monitor = HardwareMonitor.__new__(HardwareMonitor)
        bridge.registry = Mock()
        active = {'id': 'unselected', 'kind': 'local_file', 'meta': {'file_size_bytes': 9 * 1024 ** 3}}
        selected = {'id': 'chosen', 'display_name': 'Chosen', 'kind': 'local_file',
                    'request_preset': 'f5tts', 'meta': {'file_size_bytes': 1024 ** 3}}
        bridge.registry.list.return_value = [selected]
        bridge.registry.get_active_map.return_value = {'voice': active}
        _, one = bridge._estimate_overrides('cpu', 1, ['chosen'])
        _, repeated = bridge._estimate_overrides('cpu', 1, ['chosen', 'chosen'])
        self.assertAlmostEqual(one['tts_rvc'], 1024 * 1.3)
        self.assertEqual(one['tts_rvc'], repeated['tts_rvc'])

    def test_invalid_model_size_cannot_poison_resource_estimate(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        for value in ('huge', True, -1, float('nan'), float('inf')):
            entry = {'kind': 'local_file', 'meta': {'file_size_bytes': value}}
            self.assertIsNone(bridge._model_resource_override(entry, 1, 100))

    def test_remote_stages_do_not_receive_local_gpu_speedup(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge.registry = Mock()
        remote = {'kind': 'cloud_api', 'request_preset': 'rest'}
        bridge.registry.get_active.return_value = remote
        bridge.registry.list.return_value = []
        routes = bridge._estimate_routes('cuda:0', {'cast_list': ['CLONED_USER']})
        for stage in ('tts_rvc', 'lipsync', 'enhance', 'content_filter'):
            self.assertEqual(routes[stage], 'cpu')
        # A local voice conversion after remote TTS still uses the selected GPU.
        bridge.registry.list.return_value = [{'id': 'local', 'display_name': 'Local', 'kind': 'local_file'}]
        routes = bridge._estimate_routes('cuda:0', {'cast_list': ['local']})
        self.assertNotIn('tts_rvc', routes)

    def test_model_discovery_respects_offline_and_implemented_adapters(self):
        from core import model_detect
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '1'}), patch.object(model_detect.requests, 'get') as get:
            self.assertEqual(model_detect.find_best_hf_model('tts'), [])
            model_detect.detect_from_url('https://huggingface.co/coqui/XTTS-v2')
            get.assert_not_called()
        response = Mock(ok=True)
        response.json.return_value = {'downloads': 1, 'likes': 2}
        with patch.object(model_detect.requests, 'get', return_value=response) as get:
            results = model_detect.find_best_hf_model('tts')
        self.assertEqual([result['repo_id'] for result in results], ['coqui/XTTS-v2'])
        self.assertEqual(get.call_count, 1)

    def test_repository_progress_excludes_preallocated_cache(self):
        (self.root / 'model.bin').write_bytes(b'abc')
        cache = self.root / '.cache/huggingface/download'
        cache.mkdir(parents=True)
        with (cache / 'model.incomplete').open('wb') as stream:
            stream.truncate(1024 * 1024)
        self.assertEqual(downloader._dir_size(str(self.root)), 3)

    def test_repository_cancel_stops_actual_owned_process(self):
        from core.render_context import RenderContext, bind_job, run_process, RenderCancelled
        job = RenderContext(self.root)
        metadata = SimpleNamespace(model_info=lambda *args, **kwargs: SimpleNamespace(siblings=[]))
        def fixture_process(args, **kwargs):
            return run_process([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        def transfer():
            with bind_job(job):
                return list(downloader._snapshot_progress('fixture/repo', str(self.root / 'snapshot')))
        with patch.dict(sys.modules, {'huggingface_hub': SimpleNamespace(HfApi=lambda: metadata)}), \
                patch.object(downloader, 'run_process', side_effect=fixture_process), ThreadPoolExecutor(1) as pool:
            future = pool.submit(transfer)
            try:
                deadline = time.monotonic() + 5
                while not job.processes and time.monotonic() < deadline:
                    threading.Event().wait(.01)
                self.assertTrue(job.processes)
                job.request_stop()
                with self.assertRaises(RenderCancelled):
                    future.result(timeout=10)
                self.assertFalse(job.processes)
            finally:
                job.request_stop()
        job.cleanup()
        self.assertFalse(job.workspace.exists())

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.dict('os.environ', {'REFLOW_OFFLINE': '0'}))

    def response(self, chunks, length=None, content_type='application/octet-stream', encoding=''):
        response = Mock()
        response.headers = {'Content-Type': content_type, 'Content-Encoding': encoding}
        if length is not None:
            response.headers['Content-Length'] = str(length)
        response.iter_content.return_value = iter(chunks)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def download(self, response):
        with patch.object(downloader.requests, 'get', return_value=response):
            return list(downloader.download_with_progress('https://example.test/model.pth', str(self.root / 'model.pth')))

    def test_download_rejects_html_empty_truncated_and_compressed_preserves_old(self):
        destination = self.root / 'model.pth'
        destination.write_bytes(b'prior model')
        responses = (self.response([b'<html>oops'], 10), self.response([b'html'], 4, 'text/html'),
                     self.response([], 10), self.response([b'123'], 100),
                     self.response([b'1234'], 4, encoding='gzip'))
        for response in responses:
            with self.assertRaises(RuntimeError):
                self.download(response)
            self.assertEqual(destination.read_bytes(), b'prior model')
            self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_download_publishes_exact_complete_bytes_before_done(self):
        progress = self.download(self.response([b'abc', b'def'], 6))
        self.assertEqual((self.root / 'model.pth').read_bytes(), b'abcdef')
        self.assertEqual(progress[-1]['phase'], 'done')
        self.assertEqual(progress[-1]['downloaded'], 6)

    def test_download_http_and_publication_errors_preserve_old(self):
        destination = self.root / 'model.pth'
        destination.write_bytes(b'prior')
        response = self.response([b'new'], 3)
        response.raise_for_status.side_effect = RuntimeError('HTTP failure')
        with self.assertRaises(RuntimeError):
            self.download(response)
        response.raise_for_status.side_effect = None
        with patch.object(downloader.os, 'replace', side_effect=OSError('publish failed')):
            with self.assertRaises(OSError):
                self.download(response)
        self.assertEqual(destination.read_bytes(), b'prior')
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_offline_single_file_and_repository_make_no_network_request(self):
        with patch.dict('os.environ', {'REFLOW_OFFLINE': '1'}), patch.object(downloader.requests, 'get') as get:
            for url in ('https://example.test/model.bin', 'https://huggingface.co/org/repo'):
                with self.assertRaisesRegex(RuntimeError, 'Offline'):
                    list(downloader.download_with_progress(url, str(self.root / 'model')))
            get.assert_not_called()

    def test_repository_is_staged_and_old_directory_never_erased(self):
        def producer(repo, destination):
            path = Path(destination)
            path.mkdir()
            (path / 'weights.bin').write_bytes(b'weights')
            self.assertFalse((self.root / 'repo').exists())
            yield {'phase': 'done', 'downloaded': 7}
        with patch.object(downloader, '_snapshot_progress', side_effect=producer):
            progress = list(downloader._download_hf_snapshot('org/repo', str(self.root / 'repo')))
            self.assertEqual(progress[-1]['phase'], 'done')
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                list(downloader._download_hf_snapshot('org/repo', str(self.root / 'repo')))
        self.assertEqual((self.root / 'repo/weights.bin').read_bytes(), b'weights')
        self.assertEqual(list(self.root.glob('.repo-download-*')), [])

    def test_failed_repository_keeps_destination_absent_and_clears_owned_staging(self):
        def producer(repo, destination):
            Path(destination).mkdir()
            (Path(destination) / 'partial.bin').write_bytes(b'partial')
            raise RuntimeError('transfer failed')
            yield
        with patch.object(downloader, '_snapshot_progress', side_effect=producer):
            with self.assertRaisesRegex(RuntimeError, 'transfer failed'):
                list(downloader._download_hf_snapshot('org/repo', str(self.root / 'repo')))
        self.assertFalse((self.root / 'repo').exists())
        self.assertEqual(list(self.root.glob('.repo-download-*')), [])

    def test_archive_traversal_and_existing_targets_rejected_before_extraction(self):
        archive = self.root / 'voice.zip'
        for name in ('../escape.pth', 'C:/escape.pth', '/absolute.pth', '..\\escape.pth'):
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr(name, b'weights')
            with self.assertRaises(RuntimeError):
                downloader.extract_archive(str(archive), str(self.root / 'extract'))
        folder = self.root / 'extract'
        folder.mkdir(exist_ok=True)
        (folder / 'voice.pth').write_bytes(b'prior')
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('voice.pth', b'new')
        with self.assertRaisesRegex(RuntimeError, 'overwrite'):
            downloader.extract_archive(str(archive), str(folder))
        self.assertEqual((folder / 'voice.pth').read_bytes(), b'prior')

    def test_archive_normal_nested_files_extract(self):
        archive = self.root / 'voice.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('voice/model.pth', b'weights')
        files = downloader.extract_archive(str(archive), str(self.root / 'extract'))
        self.assertEqual(Path(files[0]).read_bytes(), b'weights')

    def test_integrity_import_failures_do_not_install_and_are_reported(self):
        doctor = integrity.IntegrityDoctor()
        doctor.critical_libs = {'broken': 'package'}
        with patch.object(integrity.importlib, 'import_module', side_effect=ImportError('DLL missing')), \
             patch.object(doctor, 'install_package') as install:
            failed = doctor.check_libraries()
        install.assert_not_called()
        self.assertEqual(failed[0]['module'], 'broken')
        self.assertIn('DLL missing', failed[0]['error'])

    def test_bridge_integrity_refuses_false_success(self):
        with patch.object(integrity.IntegrityDoctor, 'check_libraries', return_value=[{'module': 'broken'}]):
            result = api.PythonBridge.__new__(api.PythonBridge).run_integrity_check()
        self.assertFalse(result['ok'])
        self.assertIn('broken', result['message'])

    def test_parallel_estimates_do_not_assume_worker_speedup(self):
        for device in ('cpu', 'dedicated', 'integrated'):
            for workers in (1, 2, 4, 8):
                self.assertEqual(api._parallel_speedup_factor(workers, device), 1.0)

    def parse(self, content):
        path = self.root / 'subtitles.srt'
        path.write_text(content, encoding='utf-8')
        return srt_utils.parse_srt(str(path))

    def test_srt_invalid_cue_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError, 'cue 2'):
            self.parse('1\n00:00:00,000 --> 00:00:01,000\nGood\n\n2\ninvalid time\nBad')

    def test_srt_preserves_multiline_and_tags(self):
        cues = self.parse('1\n00:00:00,000 --> 00:00:01,000\n<i>One</i>\nTwo\n')
        self.assertEqual(cues[0]['text'], '<i>One</i>\nTwo')

    def test_srt_invalid_timestamp_interval_or_junk_rejected(self):
        for content in ('junk', '1\n00:60:00,000 --> 01:00:01,000\nText',
                        '1\n00:00:02,000 --> 00:00:01,000\nText',
                        '1\n00:00:00,000 --> 00:00:01,000\nText\n\nextra junk'):
            with self.assertRaises(ValueError):
                self.parse(content)

    def test_negative_label_order_cannot_invert_binary_moderation(self):
        self.assertEqual(positive_index({0: 'non-toxic', 1: 'toxic'}, {'toxic'}, {'non_toxic'}), 1)
        self.assertEqual(positive_index({0: 'nsfw', 1: 'not_nsfw'}, {'nsfw'}, {'not_nsfw'}), 0)
        for labels in ({0: 'not_toxic', 1: 'neutral'}, {0: 'LABEL_0', 1: 'LABEL_1'},
                       {0: 'toxic', 1: 'toxic'}, {0: 'toxic', 1: 'neutral', 2: 'other'}):
            with self.assertRaises(ValueError):
                positive_index(labels, {'toxic'}, {'neutral', 'not_toxic'})

    def test_invalid_moderation_result_fails_and_explicit_removal_is_empty(self):
        provider = SimpleNamespace(filter_text=lambda *args, **kwargs: '', supports_line_removal=False)
        with self.assertRaisesRegex(RuntimeError, 'invalid profanity-filter'):
            pipeline.ReflowPipeline._filter_line('input', provider, '')
        provider.supports_line_removal = True
        self.assertEqual(pipeline.ReflowPipeline._filter_line('input', provider, ''), '')

    def test_keep_source_moderation_runs_without_translation(self):
        subject = pipeline.ReflowPipeline.__new__(pipeline.ReflowPipeline)
        subject.registry = Mock()
        subject.registry.get_active.return_value = {'custom_instructions': 'keep language'}
        provider = Mock()
        provider.filter_text.return_value = 'clean'
        with patch.object(pipeline.providers, 'resolve_profanity_filter', return_value=provider):
            cues = subject._moderate_source([{'text': 'original'}], {})
        self.assertEqual(cues[0]['text'], 'clean')
        provider.filter_text.assert_called_once_with('original', custom_instructions='keep language')

    def test_enabled_visual_stage_rejects_missing_or_original_result(self):
        for result in (None, 'original.mp4'):
            with self.assertRaisesRegex(RuntimeError, 'enabled provider'):
                pipeline._require_visual_output('Lip sync', result, 'expected.mp4')
        with patch.object(pipeline, '_validate_media', side_effect=RuntimeError('invalid media')):
            with self.assertRaisesRegex(RuntimeError, 'invalid media'):
                pipeline._require_visual_output('Lip sync', 'expected.mp4', 'expected.mp4')

    def test_asset_headers_strip_foreign_secrets_and_refuse_downgrade(self):
        secret = {'X-Api-Key': 'fixture-secret'}
        self.assertEqual(cloud.asset_headers('https://service.test', 'https://assets.test/file', secret), {})
        self.assertEqual(cloud.asset_headers('https://service.test', 'https://service.test/file', secret), secret)
        for url in ('http://assets.test/file', 'file:///tmp/model', 'https://user:pass@assets.test/file'):
            with self.assertRaises(cloud.CloudRestError):
                cloud.asset_headers('https://service.test', url, secret)

    def test_visual_stage_rejects_shortened_or_extended_output(self):
        for duration in (2.0, 9.0):
            with patch.object(pipeline, '_validate_media', return_value=duration):
                with self.assertRaisesRegex(RuntimeError, 'output duration changed'):
                    pipeline._require_visual_output('Lip sync', 'expected.mp4', 'expected.mp4', 8.0)
        with patch.object(pipeline, '_validate_media', return_value=8.2):
            self.assertEqual(pipeline._require_visual_output(
                'Lip sync', 'expected.mp4', 'expected.mp4', 8.0), 'expected.mp4')

    def test_foreign_polling_never_sends_credentials(self):
        with patch.object(cloud, 'request') as request:
            with self.assertRaisesRegex(cloud.CloudRestError, 'origin'):
                cloud.poll_until_done('https://foreign.test/status', {'X-Key': 'secret'}, 'status', 'done', 'url', service_url='https://service.test')
            request.assert_not_called()

    def test_get_redirect_strips_custom_auth_header(self):
        first, second = Mock(), Mock()
        first.status_code = 302
        first.headers = {'Location': 'https://assets.test/file'}
        second.status_code = 200
        with patch.object(cloud.requests, 'request', side_effect=[first, second]) as request:
            self.assertIs(cloud.request('GET', 'https://service.test/file', headers={'X-Key': 'secret'}), second)
        self.assertEqual(request.call_args_list[1].kwargs['headers'], {})
        self.assertFalse(request.call_args_list[0].kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
