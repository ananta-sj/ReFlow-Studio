"""Runtime probe ownership, failure boundaries and offline process contract."""
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from core import runtime_probe
from core import runtime_probe_worker
from core.render_context import current_job


class RuntimeProbeTests(unittest.TestCase):
    def reply(self, **values):
        return dict(schema='reflow.runtime-probe.v1', adapter='indictrans2', device='cuda:0',
                    status='passed', versions={'torch': 'fixture'}, problems=[], model_loaded=False, **values)

    def run_reply(self, result, assertions=None):
        folders = []
        def run(args, **kwargs):
            folders.append(current_job().workspace)
            if assertions:
                assertions(args, kwargs)
            Path(args[-1]).write_text(json.dumps(result), encoding='utf-8')
        with patch.object(runtime_probe, 'run_process', side_effect=run):
            report = runtime_probe.probe('indictrans2', sys.executable, 'cuda:0')
        self.assertFalse(folders[0].exists())
        return report

    def test_explicit_offline_timeout_and_owned_workspace(self):
        def verify(args, kwargs):
            self.assertEqual(kwargs['timeout'], 45)
            self.assertEqual(args[1], '-B')
            for flag in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE', 'PYTHONDONTWRITEBYTECODE'):
                self.assertEqual(kwargs['env'][flag], '1')
            self.assertEqual(Path(kwargs['env']['TEMP']), current_job().workspace)
            self.assertEqual(Path(args[-1]).parent, current_job().workspace)
        self.assertEqual(self.run_reply(self.reply(), verify)['status'], 'passed')

    def test_invalid_bound_reports_fail_closed(self):
        for update in ({'adapter': 'indicf5'}, {'device': 'cpu'}, {'model_loaded': True},
                       {'status': 'passed', 'problems': ['failure']}, {'versions': {'torch': 1}}):
            result = {**self.reply(), **update}
            self.assertEqual(self.run_reply(result)['status'], 'failed')

    def test_missing_report_and_timeout_release_ownership(self):
        for effect, expected in ((None, 'failed'), (subprocess.TimeoutExpired(['fixture'], 45), 'unverified')):
            with patch.object(runtime_probe, 'run_process', side_effect=effect):
                self.assertEqual(runtime_probe.probe('indictrans2', sys.executable, 'cuda:0')['status'], expected)
        self.assertEqual(self.run_reply(self.reply())['status'], 'passed')

    def test_parallel_probe_is_rejected_without_process(self):
        runtime_probe._gate.acquire()
        try:
            with patch.object(runtime_probe, 'run_process') as run:
                result = runtime_probe.probe('indictrans2', sys.executable, 'cuda:0')
            self.assertEqual(result['status'], 'unverified')
            run.assert_not_called()
        finally:
            runtime_probe._gate.release()

    def test_unknown_route_is_rejected_before_process(self):
        with patch.object(runtime_probe, 'run_process') as run:
            for adapter, device in (('custom', 'cuda:0'), ('whisper_turbo', 'cpu'), ('indictrans2', 'cpu')):
                with self.assertRaises(ValueError):
                    runtime_probe.probe(adapter, sys.executable, device)
        run.assert_not_called()

    def test_optional_route_budgets_and_device_limits_are_shared(self):
        from core.runtime_probe_contract import ROUTES, require_route
        self.assertEqual(set(ROUTES), runtime_probe_worker.ADAPTERS)
        for adapter in ('f5tts', 'musetalk', 'rvc', 'gfpgan'):
            self.assertEqual(require_route(adapter, 'cpu'), 90)
        self.assertEqual(require_route('nudenet', 'cpu'), 45)
        with self.assertRaises(ValueError):
            require_route('nudenet', 'cuda:0')
        with self.assertRaises(ValueError):
            require_route('wav2lip', 'mps')

    def test_inprocess_runtime_ignores_worker_override_and_refuses_frozen_equivalence(self):
        from core.python_runtime import inprocess_python
        with patch.dict('os.environ', {'REFLOW_WORKER_PYTHON': 'a-different-interpreter'}):
            self.assertEqual(inprocess_python(), sys.executable)
        with patch.object(sys, 'frozen', True, create=True):
            self.assertIsNone(inprocess_python())

    def test_hindi_probe_has_bounded_import_budget_and_private_font_cache(self):
        def run(args, **kwargs):
            self.assertEqual(kwargs['timeout'], 90)
            self.assertEqual(Path(kwargs['env']['MPLCONFIGDIR']).parent, current_job().workspace)
            Path(args[-1]).write_text(json.dumps({**self.reply(), 'adapter': 'indicf5'}), encoding='utf-8')
        with patch.object(runtime_probe, 'run_process', side_effect=run):
            self.assertEqual(runtime_probe.probe('indicf5', sys.executable, 'cuda:0')['status'], 'passed')

    def test_worker_requires_the_worker_pinned_version_before_device_work(self):
        torch = Mock(__version__='wrong')
        with patch.object(runtime_probe_worker.importlib, 'import_module', return_value=torch):
            result = runtime_probe_worker.inspect('indictrans2', 'cuda:0')
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['model_loaded'])
        torch.ones.assert_not_called()

    def test_actual_worker_rejects_unknown_route_without_importing_engines(self):
        with patch.object(runtime_probe_worker.importlib, 'import_module') as module:
            with self.assertRaises(ValueError):
                runtime_probe_worker.inspect('custom', 'cuda:0')
        module.assert_not_called()

    def optional_modules(self):
        torch = Mock(__version__='2.7.1+cpu', __file__=str(Path(sys.executable).parent / 'Lib/site-packages/torch/__init__.py'))
        torch.ones.return_value = MagicMock()
        torch.all.return_value.item.return_value = True
        engine = Mock(infer=Mock())
        workflow = SimpleNamespace(__file__=str(runtime_probe_worker.ROOT / 'core/MuseTalk/scripts/inference.py'), main=Mock())
        modules = {'torch': torch, 'f5_tts.api': SimpleNamespace(F5TTS=engine),
                   'transformers': SimpleNamespace(__version__='fixture', WhisperModel=Mock()),
                   'diffusers': SimpleNamespace(AutoencoderKL=Mock()), 'scripts.inference': workflow}
        return modules, engine, workflow

    def test_f5_probe_requires_actual_synthesis_entry_points_without_constructing_engine(self):
        modules, engine, _ = self.optional_modules()
        for api, expected in ((modules['f5_tts.api'], 'passed'), (SimpleNamespace(F5TTS=object), 'failed')):
            with patch('core.f5_imports.load_f5_api',return_value=api.F5TTS), patch.object(runtime_probe_worker.importlib, 'import_module', side_effect=lambda name: modules.get(name, SimpleNamespace())), patch.object(sys, 'path', list(sys.path)):
                result = runtime_probe_worker.inspect('f5tts', 'cpu')
            self.assertEqual(result['status'], expected)
            self.assertFalse(result['model_loaded'])
        engine.assert_not_called()
        engine.infer.assert_not_called()

    def test_demucs_probe_checks_separation_imports_without_loading_weights(self):
        modules, _, _ = self.optional_modules()
        with patch.object(runtime_probe_worker.importlib, 'import_module', side_effect=lambda name: modules.get(name, SimpleNamespace())) as module:
            result = runtime_probe_worker.inspect('demucs', 'cpu')
        self.assertEqual(result['status'], 'passed')
        self.assertFalse(result['model_loaded'])
        for name in ('demucs.separate', 'demucs.htdemucs', 'torchaudio', 'soundfile'):
            self.assertIn(unittest.mock.call(name), module.call_args_list)

    def test_musetalk_probe_imports_bundled_workflow_without_running_it(self):
        modules, _, workflow = self.optional_modules()
        with patch.object(runtime_probe_worker.importlib, 'import_module', side_effect=lambda name: modules.get(name, SimpleNamespace())) as module, patch.object(sys, 'path', list(sys.path)):
            result = runtime_probe_worker.inspect('musetalk', 'cpu')
        self.assertEqual(result['status'], 'passed')
        self.assertIn(unittest.mock.call('scripts.inference'), module.call_args_list)
        workflow.main.assert_not_called()

    def test_musetalk_missing_or_shadowed_workflow_fails_before_device_calculation(self):
        for shadowed in (False, True):
            modules, _, workflow = self.optional_modules()
            if shadowed:
                workflow.__file__ = str(Path(sys.executable).parent / 'scripts/inference.py')
            def load(name):
                if name == 'scripts.inference' and not shadowed:
                    raise ModuleNotFoundError('Missing workflow dependency fixture')
                return modules.get(name, SimpleNamespace())
            with patch.object(runtime_probe_worker.importlib, 'import_module', side_effect=load), patch.object(sys, 'path', list(sys.path)):
                result = runtime_probe_worker.inspect('musetalk', 'cpu')
            self.assertEqual(result['status'], 'failed')
            modules['torch'].ones.assert_not_called()
            workflow.main.assert_not_called()

    def bridge(self):
        from bridge.api import PythonBridge
        bridge = PythonBridge.__new__(PythonBridge)
        bridge.settings = Mock()
        bridge.settings.get.return_value = 'legacy'
        bridge._render_lock = threading.Lock()
        bridge._render_thread = None
        bridge.registry = Mock()
        bridge.get_cast_list = Mock(return_value=[])
        return bridge

    def test_bridge_rejects_new_jobs_and_deletion_while_checking(self):
        bridge = self.bridge()
        def inspect(*args, **kwargs):
            self.assertTrue(kwargs['verify_runtime'])
            self.assertTrue(bridge._deletion_busy())
            self.assertIn('runtime check', bridge._start_rejection())
            return {'status': 'inspection_complete'}
        with patch('core.engine_readiness.inspect', side_effect=inspect):
            bridge.get_engine_readiness({}, verify_runtime=True)
        self.assertFalse(bridge._deletion_busy())
        self.assertIsNone(bridge._start_rejection())

    def test_bridge_failure_releases_runtime_check_flag(self):
        bridge = self.bridge()
        with patch('core.engine_readiness.inspect', side_effect=ValueError('fixture')):
            with self.assertRaises(ValueError):
                bridge.get_engine_readiness({}, verify_runtime=True)
        self.assertFalse(bridge._runtime_check_busy)

    def test_bridge_rejects_runtime_probe_during_active_job(self):
        bridge = self.bridge()
        bridge._active_job = object()
        with patch('core.engine_readiness.inspect') as inspect:
            with self.assertRaises(RuntimeError):
                bridge.get_engine_readiness({}, verify_runtime=True)
        inspect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
