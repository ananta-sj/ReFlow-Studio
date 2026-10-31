"""Resource planning follows processor choices without loading any engines."""
import math
import unittest
import threading
from unittest.mock import Mock, patch

from core.hardware_monitor import HardwareMonitor, GPUDevice
from core.pipeline_contracts import RegistrySnapshot
from core.parallel_policy import segment_buffer_window
from dev.test_render_queue import api


class ResourceRoutingTests(unittest.TestCase):
    def test_public_estimates_use_render_cast_and_do_not_mutate_caller_flags(self):
        bridge = self.bridge()
        bridge._render_lock = threading.RLock()
        bridge.graph = api.build_default_graph()
        bridge._resource_estimate = Mock(return_value={'fixture': True})
        original = {'voice':'dashboard', 'cast_list':['stale']}
        with patch.object(api, '_probe_duration', return_value=10):
            bridge.estimate_job('fixture.mp4', original, 'cpu')
            self.assertEqual(bridge._resource_estimate.call_args.args[-1]['cast_list'], ['dashboard'])
            from core.node_registry import SPECS
            bridge.graph.nodes['tts_rvc'].values['voice'] = 'first'
            other = bridge.graph.add_node('tts_rvc_2', SPECS['tts_rvc'])
            other.values['voice'] = 'second'
            bridge.estimate_job_all_devices('fixture.mp4', original)
            self.assertEqual(bridge._resource_estimate.call_args.args[-1]['cast_list'], ['first','second'])
        self.assertEqual(original, {'voice':'dashboard', 'cast_list':['stale']})

    def bridge(self, entries=(), active=None):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge.monitor = HardwareMonitor.__new__(HardwareMonitor)
        bridge.monitor.devices = [GPUDevice('cpu', 'CPU', 'cpu', 'cpu'),
            GPUDevice('cuda:0', 'GPU 0', 'dedicated', 'cuda'), GPUDevice('cuda:1', 'GPU 1', 'dedicated', 'cuda')]
        bridge.registry = RegistrySnapshot(dict(entries=list(entries), active=active or {}))
        return bridge

    def entry(self, identifier, stage, preset=None, **meta):
        return dict(id=identifier, display_name=identifier, stage_type=stage, kind='local_file',
                    request_preset=preset, meta=dict(file_size_bytes=1024**3, **meta))

    def test_cpu_indic_speech_with_gpu_rvc_uses_each_processor_without_clone_actor(self):
        bridge = self.bridge([self.entry('hindi', 'tts', 'indicf5', speech_device='cpu'),
                              self.entry('actor', 'voice', 'rvc')], {'tts':'hindi'})
        result = bridge._resource_estimate(100, ['tts_rvc'], 'cuda:1', {'cast_list':['actor']})
        tts, voice = result['speech_components']
        self.assertEqual((tts['device'], voice['device']), ('cpu', 'cuda:1'))
        self.assertEqual(result['stage_devices']['tts_rvc'], 'mixed')
        self.assertEqual(result['peak_vram_by_device_mb'], {'cuda:1':voice['model_memory_mb']})
        self.assertEqual(result['eta_seconds'], max(5, int(100*(tts['cost_ratio'] + voice['cost_ratio']*.2))))
        self.assertTrue(any('Hindi speech' in warning for warning in result['warnings']))

    def test_cpu_f5_and_gpu_base_speech_are_split_and_duplicate_voices_are_counted_once(self):
        bridge = self.bridge([self.entry('tts', 'tts', 'xtts'), self.entry('f5', 'voice', 'f5tts')], {'tts':'tts'})
        with patch('core.optional_runtime.interpreter', return_value='existing-optional-python'):
            result = bridge._resource_estimate(100, ['tts_rvc'], 'cuda:1', {'cast_list':['CLONED_USER', 'f5', 'f5']})
        self.assertEqual(len(result['speech_components']), 2)
        tts, voice = result['speech_components']
        self.assertEqual((tts['device'], voice['device']), ('cuda:1', 'cpu'))
        self.assertEqual(result['peak_vram_by_device_mb'], {'cuda:1':tts['model_memory_mb']})
        self.assertEqual(result['eta_seconds'], max(5, int(100*(tts['cost_ratio']*.2 + voice['cost_ratio']))))

    def test_all_f5_voices_skip_unrelated_active_base_tts(self):
        bridge = self.bridge([self.entry('tts', 'tts', 'indicf5', speech_device='cuda:0'),
                              self.entry('f5', 'voice', 'f5tts')], {'tts':'tts'})
        with patch('core.optional_runtime.interpreter', return_value='existing-optional-python'):
            result = bridge._resource_estimate(100, ['tts_rvc'], 'cuda:1', {'cast_list':['f5']})
        self.assertEqual([component['role'] for component in result['speech_components']], ['voice'])
        self.assertEqual(result['stage_devices']['tts_rvc'], 'cpu')
        self.assertEqual(result['peak_vram_by_device_mb'], {})
        self.assertIsNone(result['peak_vram_mb'])
        self.assertFalse(any('Hindi speech' in warning for warning in result['warnings']))

    def test_fixed_gpu_translation_and_selected_gpu_speech_have_separate_budgets(self):
        bridge = self.bridge([self.entry('translation', 'translation', 'indictrans2'),
                              self.entry('tts', 'tts', 'xtts')], {'translation':'translation', 'tts':'tts'})
        result = bridge._resource_estimate(100, ['translate', 'tts_rvc'], 'cuda:1', {})
        self.assertEqual(set(result['peak_vram_by_device_mb']), {'cuda:0', 'cuda:1'})
        speech_budget = result['speech_components'][0]['model_memory_mb']
        self.assertEqual(result['peak_vram_by_device_mb']['cuda:1'], speech_budget)
        self.assertEqual(result['peak_vram_mb'], max(result['peak_vram_by_device_mb'].values()))

    def test_unknown_gpu_stage_memory_is_not_zero_or_overwritten_by_known_stage(self):
        bridge = self.bridge()
        for stages in (['separate', 'tts_rvc'], ['tts_rvc', 'separate']):
            result = bridge._resource_estimate(100, stages, 'cuda:0', {})
            self.assertEqual(result['peak_vram_by_device_mb'], {'cuda:0':None})
            self.assertIsNone(result['peak_vram_mb'])
            self.assertTrue(any('unknown for separate' in warning for warning in result['warnings']))

    def test_text_only_jobs_do_not_count_audio_buffers_or_unused_speech_routes(self):
        bridge = self.bridge([self.entry('tts', 'tts', 'indicf5', speech_device='cuda:0')], {'tts':'tts'})
        result = bridge._resource_estimate(100, ['translate'], 'cpu', {'parallel_workers':8})
        self.assertEqual(result['audio_buffer_ram_mb'], 0)
        self.assertEqual(result['segment_buffer_window'], 0)
        self.assertEqual(result['speech_components'], [])
        self.assertFalse(any('Hindi speech' in warning for warning in result['warnings']))

    def test_invalid_duration_fails_before_provider_inspection(self):
        bridge = self.bridge()
        bridge._estimate_overrides = Mock()
        for duration in (True, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                bridge._resource_estimate(duration, ['tts_rvc'], 'cpu', {})
        bridge._estimate_overrides.assert_not_called()

    def test_shared_worker_window_matches_estimate_and_has_no_speed_or_gpu_memory_discount(self):
        bridge = self.bridge()
        values = [bridge._resource_estimate(100, ['tts_rvc'], 'cuda:0', {'parallel_workers':workers}) for workers in (1, 2, 8)]
        self.assertEqual([value['segment_buffer_window'] for value in values], [1, 4, 16])
        self.assertEqual(len({value['eta_seconds'] for value in values}), 1)
        self.assertEqual(len({value['peak_vram_mb'] for value in values}), 1)
        self.assertGreater(values[2]['audio_buffer_ram_mb'], values[0]['audio_buffer_ram_mb'])
        for workers in (True, 0, 9, 1.5):
            with self.assertRaises(ValueError):
                segment_buffer_window(workers)

    def test_nonaccelerated_adapter_normalizes_to_cpu_in_speech_and_memory_planning(self):
        result = self.bridge()._resource_estimate(100, ['tts_rvc'], 'other:Display adapter', {})
        self.assertEqual(result['stage_devices']['tts_rvc'], 'cpu')
        self.assertEqual(result['peak_vram_by_device_mb'], {})


if __name__ == '__main__':
    unittest.main()
