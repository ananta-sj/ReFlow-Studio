"""GPU routing stays gated on real tests and preserves CPU selection."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import cuda_runtime
from core.cuda_providers import CudaXTTSProvider, CudaNLLBProvider, CudaWhisperProvider
from core.providers import resolve
from core.runtime_integrity import sha


class CudaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.folder = self.root/'runtime_profiles/cuda'
        self.folder.mkdir(parents=True)
        for name in ('python.exe', 'python313.dll', 'python313.zip'):
            (self.folder/name).write_bytes(name.encode())
        (self.folder/'.owner').write_text('reflow.cuda.v1')
        (self.folder/'python313._pth').write_text(cuda_runtime.PTH)
        for name in cuda_runtime.SOURCES:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        for package, version in [('torch', '2.14.1+cu130'), ('torchaudio', '2.11.0+cu130')]:
            metadata = self.folder/'Lib/site-packages'/f'{package}-{version}.dist-info/METADATA'
            metadata.parent.mkdir(parents=True)
            metadata.write_text(f'Name: {package}\nVersion: {version}\n')
        self.data = dict(schema='reflow.cuda-runtime.v1', packages={'torch': {'version': '2.14.1+cu130'}},
            bootstrap={name:sha(self.folder/name) for name in ('python.exe', 'python313.dll', 'python313.zip')})
        self.save()
        self.stack.enter_context(patch('core.xtts_runtime.validate', return_value={'identity':'speech'}))
        self.stack.enter_context(patch('core.separation_runtime.validate', return_value={'identity':'separation'}))
        self.stack.enter_context(patch('core.cuda_runtime.recognition_dependencies', return_value='recognition'))

    def save(self):
        (self.folder/'profile.json').write_text(json.dumps(self.data))

    def enable(self):
        identity = cuda_runtime.validate(candidate=True, root=self.root)['identity']
        self.data['gpu_validation'] = dict(identity=identity, stages={stage:dict(ok=True, device='cuda:0')
            for stage in cuda_runtime.STAGES})
        self.save()

    def test_packages_alone_do_not_enable_gpu_routes(self):
        cuda_runtime.validate(candidate=True, root=self.root)
        with self.assertRaisesRegex(RuntimeError, 'model tests'):
            cuda_runtime.validate('speech', root=self.root)

    def test_each_stage_requires_a_successful_cuda_receipt(self):
        self.enable()
        for stage in cuda_runtime.STAGES:
            self.assertEqual(cuda_runtime.validate(stage, root=self.root)['device'], 'cuda:0')
        self.data['gpu_validation']['stages']['recognition']['ok'] = False
        self.save()
        with self.assertRaisesRegex(RuntimeError, 'model tests'):
            cuda_runtime.validate('recognition', root=self.root)

    def test_changed_worker_or_bootstrap_invalidates_receipts(self):
        self.enable()
        (self.root/'core/cuda_worker.py').write_text('changed code')
        with self.assertRaisesRegex(RuntimeError, 'model tests'):
            cuda_runtime.validate('speech', root=self.root)
        (self.folder/'python313.dll').write_bytes(b'changed bootstrap')
        with self.assertRaisesRegex(RuntimeError, 'bootstrap'):
            cuda_runtime.validate(candidate=True, root=self.root)

    def test_import_path_changes_are_rejected(self):
        (self.folder/'python313._pth').write_text('unapproved/location')
        with self.assertRaisesRegex(RuntimeError, 'import paths'):
            cuda_runtime.validate(candidate=True, root=self.root)


class CudaRoutingTests(unittest.TestCase):
    def test_gpu_selection_routes_all_four_stages_and_cpu_keeps_its_settings(self):
        values = dict(xtts_runtime='isolated', nllb_runtime='legacy')
        with patch('core.cuda_runtime.readiness', return_value={'status':'ready'}):
            selected = cuda_runtime.settings_for_device(values, 'cuda:0')
            self.assertTrue(all(selected[key] == 'cuda' for key in
                ('xtts_runtime', 'nllb_runtime', 'recognition_runtime', 'separation_runtime')))
            self.assertEqual(cuda_runtime.settings_for_device(values, 'cpu'), values)
        self.assertEqual(values, dict(xtts_runtime='isolated', nllb_runtime='legacy'))

    def test_unverified_gpu_profile_cannot_change_the_selected_runtime(self):
        values = {'xtts_runtime':'isolated'}
        with patch('core.cuda_runtime.readiness', return_value={'status':'prepared-awaiting-tests'}):
            self.assertEqual(cuda_runtime.settings_for_device(values, 'cuda:0'), values)

    def test_normal_factories_choose_gpu_providers(self):
        registry = Mock()
        registry.get_active.return_value = dict(kind='local_file', local_path='local-model')
        with patch('core.providers.resolve._local', return_value={'adapter':'nllb'}):
            self.assertIsInstance(resolve.resolve_translation(registry, 'localhost', runtime='cuda'), CudaNLLBProvider)
        with patch('core.providers.resolve._local', return_value={'adapter':'xtts'}):
            self.assertIsInstance(resolve.resolve_tts(registry, 'cuda:0', runtime='cuda'), CudaXTTSProvider)
        with patch('core.providers.resolve._local', return_value={'adapter':'faster_whisper'}):
            self.assertIsInstance(resolve.resolve_stt(registry, 'medium', runtime='cuda'), CudaWhisperProvider)

    def test_recognition_worker_is_released_after_failure(self):
        provider = CudaWhisperProvider('local-model')
        provider.calls = Mock()
        provider.calls.call.side_effect = RuntimeError('GPU inference failed')
        with self.assertRaisesRegex(RuntimeError, 'GPU inference failed'):
            provider.transcribe('source.wav', 'ja')
        provider.calls.release.assert_called_once()

    def test_video_preflight_accepts_verified_cuda_stages(self):
        from core.runtime_checks import preflight
        registry = Mock()
        registry.get_active.side_effect = lambda stage: (
            dict(kind='local_file', stage_type=stage, local_path='model')
            if stage in ('stt', 'translation', 'tts') else None)
        params = dict(lang='hi', voice='CLONED_USER', keep_bg=True,
                      compute_device='cuda:0', recognition_runtime='cuda',
                      nllb_runtime='cuda', xtts_runtime='cuda', separation_runtime='cuda')
        with patch('core.runtime_checks.local_contract', side_effect=lambda stage,*args: dict(adapter={'translation':'nllb','tts':'xtts','stt':'faster_whisper'}[stage])), patch('core.cuda_runtime.validate') as validate, patch('core.runtime_checks._engine') as engine:
            preflight(registry, params, 'video_dub')
        self.assertEqual({call.args[0] for call in validate.call_args_list},
                         {'speech', 'translation', 'recognition', 'separate'})
        engine.assert_not_called()

    def test_cloud_translation_remains_on_its_selected_provider(self):
        registry = Mock()
        registry.get_active.return_value = dict(kind='cloud_api', api_base_url='https://example.test')
        with patch('core.providers.resolve._local', return_value=None):
            provider = resolve.resolve_translation(registry, 'localhost', runtime='cuda')
        self.assertNotIsInstance(provider, CudaNLLBProvider)
