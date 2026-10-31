"""Route checks and real desktop imports with unavailable legacy AI libraries."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core import runtime_checks, integrity


BOOT_PROBE = r'''
import importlib.abc, json, sys, types
from pathlib import Path
root, scratch, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
sys.path[:0] = [str(root), str(root / 'core')]
blocked = {'torch', 'TTS', 'transformers', 'faster_whisper', 'demucs',
           'basicsr', 'gfpgan', 'librosa', 'scipy', 'numpy', 'tokenizers',
           'rvc_python', 'f5_tts'}
attempts = []
class BlockAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            attempts.append(fullname)
            if mode == 'broken' and fullname == 'torch':
                raise OSError('Simulated unavailable Torch native DLL')
            raise ModuleNotFoundError('Simulated absent optional engine: ' + fullname)
sys.meta_path.insert(0, BlockAI())
# Execute the real config source with a disposable location before any app
# imports. Every config-derived settings/model/output path stays in scratch.
config = types.ModuleType('config')
config.__file__ = str(scratch / 'config.py')
sys.modules['config'] = config
exec(compile((root / 'config.py').read_text(encoding='utf-8'), config.__file__, 'exec'), config.__dict__)
import main
from bridge.api import PythonBridge
from core import hardware_monitor
from core.pipeline_contracts import SettingsSnapshot
from pipeline import ReflowPipeline
bridge = PythonBridge.__new__(PythonBridge)
result = bridge.run_integrity_check()
assert result['ok'], result
templates = bridge.list_pipeline_templates()
assert len(templates) >= 4, templates
assert config.DEVICE == 'cpu' and config.TORCH_IMPORT_ERROR
assert hardware_monitor.torch is None
pipeline = ReflowPipeline()
pipeline._run_settings = SettingsSnapshot({})
source = scratch / 'source.srt'
source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello world.\n\n', encoding='utf-8')
events = list(pipeline.process_subtitle_translate_gen(str(source), 'source', 'en'))
assert events[-1][0] == 100, events
output = Path(events[-1][2])
assert 'Hello world.' in output.read_text(encoding='utf-8')
pipeline.clear_vram()
assert set(attempts) == {'torch'}, attempts
assert not any(name.split('.')[0] in blocked for name in sys.modules)
print('BOUNDARY_RECEIPT=' + json.dumps({'mode': mode, 'desktop_imports': True,
    'desktop_integrity': result['ok'], 'template_count': len(templates),
    'subtitle_source_export': True, 'attempted_optional_imports': attempts,
    'native_window_tested': False, 'packages_installed': False}))
'''


class DesktopRuntimeBoundaryTests(unittest.TestCase):
    def params(self, **changes):
        values = dict(lang='source', keep_bg=False, cast_list=['CLONED_USER'],
                      xtts_runtime='isolated', compute_device='cpu')
        values.update(changes)
        return values

    def test_isolated_preflight_does_not_import_legacy_tts(self):
        with patch.object(runtime_checks, '_engine') as engine, \
                patch('core.xtts_runtime.validate') as validate:
            runtime_checks.preflight(None, self.params(), 'audio_dub')
        validate.assert_called_once_with()
        self.assertEqual([call.args[0] for call in engine.call_args_list], ['faster_whisper'])

    def test_invalid_isolated_runtime_cannot_pass(self):
        with patch.object(runtime_checks, '_engine'), \
                patch('core.xtts_runtime.validate', side_effect=RuntimeError('profile invalid')):
            with self.assertRaisesRegex(RuntimeError, 'profile invalid'):
                runtime_checks.preflight(None, self.params(), 'video_dub')

    def test_isolated_gpu_rejected_and_other_adapter_uses_cpu(self):
        with patch.object(runtime_checks, '_engine'), patch('core.xtts_runtime.validate') as validate:
            with self.assertRaisesRegex(ValueError, 'CPU only'):
                runtime_checks.preflight(None, self.params(compute_device='cuda:0'), 'audio_dub')
            validate.assert_not_called()
            runtime_checks.preflight(None, self.params(compute_device='other:adapter'), 'audio_dub')
            validate.assert_called_once_with()

    def test_legacy_runtime_still_checks_legacy_imports(self):
        with patch.object(runtime_checks, '_engine') as engine, patch('core.xtts_runtime.validate') as validate:
            runtime_checks.preflight(None, self.params(xtts_runtime='legacy'), 'audio_dub')
        validate.assert_not_called()
        self.assertEqual([call.args[0] for call in engine.call_args_list],
                         ['faster_whisper', 'TTS.tts.configs.xtts_config', 'TTS.tts.models.xtts'])

    def test_cloud_tts_does_not_validate_isolated_runtime(self):
        registry = Mock()
        registry.get_active.side_effect = lambda stage: (
            dict(kind='local_api', api_base_url='http://localhost:11434') if stage == 'tts' else None)
        with patch.object(runtime_checks, '_engine'), patch.object(runtime_checks, '_selection'), \
                patch('core.xtts_runtime.validate') as validate:
            runtime_checks.preflight(registry, self.params(), 'audio_dub')
        validate.assert_not_called()

    def test_subtitles_do_not_check_speech_runtime(self):
        with patch.object(runtime_checks, '_engine') as engine, patch('core.xtts_runtime.validate') as validate:
            runtime_checks.preflight(None, self.params(), 'subtitle_translate')
        validate.assert_not_called()
        engine.assert_not_called()

    def test_media_generators_pass_frozen_runtime_and_job_device(self):
        from pipeline import ReflowPipeline
        from core.pipeline_contracts import SettingsSnapshot
        subject = ReflowPipeline.__new__(ReflowPipeline)
        subject.registry = None
        subject._run_settings = SettingsSnapshot({'xtts_runtime': 'isolated'})
        subject._early_speech_check = Mock()
        for method in (subject.process_video_gen, subject.process_audio_dub_gen):
            with self.subTest(template=method.__name__), \
                    patch.object(runtime_checks, 'preflight', side_effect=RuntimeError('stop before processing')) as check:
                with self.assertRaisesRegex(RuntimeError, 'stop before processing'):
                    next(method('unused-media', ['CLONED_USER'], compute_device='cpu'))
                self.assertEqual(check.call_args.args[1]['xtts_runtime'], 'isolated')
                self.assertEqual(check.call_args.args[1]['compute_device'], 'cpu')

    def test_desktop_integrity_skips_ai_but_explicit_audit_checks_it(self):
        doctor = integrity.IntegrityDoctor()
        with patch.object(integrity.importlib, 'import_module') as imports:
            self.assertEqual(doctor.check_libraries(), [])
            self.assertTrue(set(doctor.engine_libs).isdisjoint(call.args[0] for call in imports.call_args_list))
            imports.reset_mock()
            doctor.check_libraries(include_engines=True)
            self.assertTrue(set(doctor.engine_libs).issubset(call.args[0] for call in imports.call_args_list))

    def probe(self, mode):
        with tempfile.TemporaryDirectory(prefix='desktop-boundary-', dir=ROOT / 'temp') as scratch:
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', BOOT_PROBE,
                                     str(ROOT), scratch, mode], capture_output=True, text=True,
                                    encoding='utf-8', timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(next(line.split('=', 1)[1] for line in result.stdout.splitlines()
                                  if line.startswith('BOUNDARY_RECEIPT=')))
        print('BOUNDARY_RECEIPT=' + json.dumps(receipt))
        self.assertTrue(receipt['desktop_integrity'])
        self.assertTrue(receipt['subtitle_source_export'])

    def test_desktop_and_source_subtitles_without_ai_libraries(self):
        self.probe('missing')

    def test_desktop_and_source_subtitles_with_broken_torch_dll(self):
        self.probe('broken')


if __name__ == '__main__':
    unittest.main()
