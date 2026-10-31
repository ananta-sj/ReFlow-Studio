"""Saved-state failures and concurrency against disposable files only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import builtins
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import json_store, model_registry, settings, hardware_profile, render_state

ROOT = Path(__file__).resolve().parents[1]


class PersistenceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for module, name, filename in (
            (model_registry, 'REGISTRY_PATH', 'models.json'),
            (settings, 'SETTINGS_PATH', 'settings.json'),
            (hardware_profile, 'PROFILE_PATH', 'hardware.json'),
            (render_state, 'STATE_PATH', 'render.json'),
        ):
            self.stack.enter_context(patch.object(module, name, str(self.root / filename)))

    @unittest.skipUnless(os.name == 'nt', 'Windows rename retry contract')
    def test_atomic_publish_retries_transient_windows_denial(self):
        path = self.root / 'atomic.json'
        path.write_bytes(b'old')
        replace = os.replace
        attempts = []
        actual_denials = []
        def sharing_denial(source, target):
            attempts.append((source, target))
            if len(attempts) < 3:
                error = PermissionError('transient sharing denial')
                error.winerror = 32
                raise error
            try:
                replace(source, target)
            except PermissionError as error:
                actual_denials.append(getattr(error, 'winerror', None))
                raise
        with patch.object(json_store.os, 'replace', side_effect=sharing_denial), patch.object(json_store.time, 'sleep'):
            json_store.atomic_bytes(str(path), b'new')
        # A real Windows sharing denial can follow the two injected ones.
        # Keep the exact retry accounting and production's four-attempt bound.
        self.assertEqual(len(attempts), 3 + len(actual_denials))
        self.assertLessEqual(len(attempts), 4)
        self.assertTrue(all(code in (5, 32) for code in actual_denials))
        self.assertEqual(path.read_bytes(), b'new')
        self.assertEqual(list(self.root.glob('.atomic.json.*.tmp')), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows rename retry contract')
    def test_atomic_publish_permanent_denial_preserves_previous_bytes(self):
        path = self.root / 'atomic.json'
        path.write_bytes(b'old')
        error = PermissionError('persistent denial')
        error.winerror = 5
        with patch.object(json_store.os, 'replace', side_effect=error) as replace, patch.object(json_store.time, 'sleep'):
            with self.assertRaises(PermissionError):
                json_store.atomic_bytes(str(path), b'new')
        self.assertEqual(replace.call_count, 4)
        self.assertEqual(path.read_bytes(), b'old')
        self.assertEqual(list(self.root.glob('.atomic.json.*.tmp')), [])

    def registry(self):
        return model_registry.ModelRegistry()

    def add(self, registry, name='Voice'):
        checkpoint = self.root / 'checkpoint.bin'
        checkpoint.write_bytes(b'fixture')
        return registry.add('tts', 'local_file', name, status='installed', local_path=str(checkpoint), meta={'nested': {'value': 1}})

    def monitor(self, name='CPU'):
        return SimpleNamespace(cpu_name=name, devices=[], default_device_id=lambda: 'cpu',
                               sample=lambda device: {'ram_total_gb': 16})

    def child(self, body, *args):
        script = 'import sys; sys.path[:0] = ' + repr([str(ROOT), str(ROOT / 'core')]) + '\n' + body
        return subprocess.Popen([sys.executable, '-B', '-c', script, *map(str, args)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def finish(self, child, expected=0):
        try:
            output, error = child.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            self.fail('Disposable subprocess timed out')
        self.assertEqual(child.returncode, expected, (output, error))

    def test_first_run_defaults_and_no_live_json_created_by_reads(self):
        self.assertEqual(self.registry().list(), [])
        self.assertEqual(settings.Settings().all(), settings.DEFAULTS)
        self.assertIsNone(hardware_profile.HardwareProfileStore().get())
        self.assertIsNone(render_state.get_interrupted())
        self.assertEqual(list(self.root.glob('*.json')), [])

    def test_unicode_optional_metadata_and_unknown_settings_preserved(self):
        registry = self.registry()
        entry = self.add(registry, 'आवाज़ 中文')
        self.assertEqual(self.registry().get(entry['id'])['display_name'], 'आवाज़ 中文')
        path = self.root / 'settings.json'
        path.write_text(json.dumps({'future_option': {'keep': True}, 'default_language': 'fr'}), encoding='utf-8')
        settings.Settings().update({'keep_bg_default': False})
        self.assertEqual(json.loads(path.read_text())['future_option'], {'keep': True})
        self.assertEqual(settings.Settings().get('default_language'), 'fr')

    def test_registry_returns_defensive_copies(self):
        registry = self.registry()
        entry = self.add(registry)
        for result in (entry, registry.get(entry['id']), registry.list()[0],
                       registry.get_active('tts'), registry.get_active_map()['tts'],
                       registry.update(entry['id'], status='installed')):
            result['meta']['nested']['value'] = 999
            result['display_name'] = 'changed'
        self.assertEqual(registry.get(entry['id'])['meta']['nested']['value'], 1)
        self.assertEqual(registry._entries[0]['display_name'], 'Voice')

    def test_registry_replace_failure_preserves_memory_and_bytes(self):
        registry = self.registry()
        entry = self.add(registry)
        before = (self.root / 'models.json').read_bytes()
        memory = deepcopy((registry._entries, registry._active))
        with patch.object(json_store.os, 'replace', side_effect=PermissionError('locked destination')):
            with self.assertRaises(PermissionError):
                registry.update(entry['id'], display_name='new')
        self.assertEqual((self.root / 'models.json').read_bytes(), before)
        self.assertEqual((registry._entries, registry._active), memory)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_registry_remove_and_activation_failures_preserve_memory(self):
        registry = self.registry()
        entry = self.add(registry)
        for action in (lambda: registry.remove(entry['id']), lambda: registry.set_active('tts', None),
                       lambda: self.add(registry, 'Another')):
            before = deepcopy((registry._entries, registry._active))
            with patch.object(json_store.os, 'fsync', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    action()
            self.assertEqual((registry._entries, registry._active), before)
            self.assertEqual(len(self.registry().list()), 1)

    def test_temporary_creation_and_write_failure_preserve_prior_file(self):
        store = settings.Settings()
        store.update({'default_language': 'fr'})
        path = self.root / 'settings.json'
        before = path.read_bytes()
        original = os.fdopen
        @contextmanager
        def failed_writer(fd, mode):
            with original(fd, mode) as stream:
                yield SimpleNamespace(write=Mock(side_effect=OSError('write failed')),
                                      flush=stream.flush, fileno=stream.fileno)
        for target, replacement in ((json_store.tempfile, 'mkstemp'), (json_store.os, 'fdopen')):
            options = {'side_effect': OSError('create failed')} if replacement == 'mkstemp' else {'side_effect': failed_writer}
            with patch.object(target, replacement, **options):
                with self.assertRaises(OSError):
                    store.update({'default_language': 'de'})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store._values['default_language'], 'fr')
            self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_serialization_failure_preserves_prior_registry(self):
        registry = self.registry()
        entry = self.add(registry)
        before = (self.root / 'models.json').read_bytes()
        for metadata in ({'bad': object()}, {'bad': float('nan')}):
            with self.assertRaises((TypeError, ValueError)):
                registry.update(entry['id'], meta=metadata)
            self.assertEqual((self.root / 'models.json').read_bytes(), before)
            self.assertEqual(registry._entries[0]['meta'], {'nested': {'value': 1}})

    def test_settings_update_and_reset_failure_preserve_memory(self):
        store = settings.Settings()
        store.update({'default_language': 'fr'})
        before = (self.root / 'settings.json').read_bytes()
        memory = deepcopy(store._values)
        for action in (lambda: store.update({'default_language': 'de'}), store.reset):
            with patch.object(json_store.os, 'replace', side_effect=OSError('save failed')):
                with self.assertRaises(OSError):
                    action()
            self.assertEqual(store._values, memory)
            self.assertEqual((self.root / 'settings.json').read_bytes(), before)

    def test_invalid_settings_rejected_before_publication(self):
        store = settings.Settings()
        store.update({})
        before = (self.root / 'settings.json').read_bytes()
        for update in ({'keep_bg_default': 'false'}, {'default_task_priority': True},
                       {'default_task_priority': 101}, {'default_texture_quality': 3},
                       {'whisper_model_size': 'unknown'}, {'search_provider': 'bad'},
                       {'default_language': ''}, []):
            with self.assertRaises(ValueError):
                store.update(update)
            self.assertEqual((self.root / 'settings.json').read_bytes(), before)

    def test_invalid_registry_shapes_and_updates_rejected(self):
        registry = self.registry()
        entry = self.add(registry)
        before = (self.root / 'models.json').read_bytes()
        for fields in ({'meta': []}, {'local_path': 42}, {'stage_type': 'missing'}, {'display_name': None}):
            with self.assertRaises(ValueError):
                registry.update(entry['id'], **fields)
            self.assertEqual((self.root / 'models.json').read_bytes(), before)
        with self.assertRaises(ValueError):
            registry.set_active('bad', entry['id'])

    def test_threaded_distinct_registry_instances_keep_all_updates(self):
        registries = [self.registry() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda index: self.add(registries[index % 4], str(index)), range(40)))
        self.assertEqual(len(self.registry().list()), 40)
        self.assertEqual(len({entry['id'] for entry in results}), 40)

    def test_distinct_settings_instances_merge_latest_disk_state(self):
        first, second = settings.Settings(), settings.Settings()
        first.update({'default_language': 'fr'})
        second.update({'keep_bg_default': False})
        self.assertEqual(first.get('keep_bg_default'), False)
        self.assertEqual(second.get('default_language'), 'fr')

    def test_cooperating_subprocesses_keep_all_registry_updates(self):
        body = '''from core import model_registry
model_registry.REGISTRY_PATH = sys.argv[1]
registry = model_registry.ModelRegistry()
for index in range(12):
    registry.add('tts', 'local_file', sys.argv[2] + str(index))
'''
        children = [self.child(body, self.root / 'models.json', str(index)) for index in range(3)]
        for child in children:
            self.finish(child)
        self.assertEqual(len(self.registry().list()), 36)

    def test_crash_before_and_after_replace_keeps_complete_record(self):
        body = '''import os
from core import settings, json_store
settings.SETTINGS_PATH = sys.argv[1]
store = settings.Settings()
original = json_store.os.replace
def crash(source, destination):
    if sys.argv[2] == 'after':
        original(source, destination)
    os._exit(23)
json_store.os.replace = crash
store.update({'default_language': 'de'})
'''
        for moment, expected in (('before', 'fr'), ('after', 'de')):
            settings.Settings().update({'default_language': 'fr'})
            self.finish(self.child(body, self.root / 'settings.json', moment), 23)
            self.assertEqual(settings.Settings().get('default_language'), expected)
        # Crash-left temporary files are isolated here and never read as state.
        self.assertEqual(len(list(self.root.glob('*.tmp'))), 1)

    def test_corrupt_registry_preserved_exactly_and_warned_once(self):
        path = self.root / 'models.json'
        raw = b'{"entries": [broken\xff'
        path.write_bytes(raw)
        warning = Mock()
        registry = model_registry.ModelRegistry(warning=warning)
        self.assertEqual(registry.list(), [])
        self.assertEqual(path.read_bytes(), raw)
        backups = list(self.root.glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), raw)
        warning.assert_called_once()
        self.add(registry)
        self.assertEqual(backups[0].read_bytes(), raw)
        self.assertEqual(len(self.registry().list()), 1)

    def test_wrong_root_and_nested_shapes_preserved(self):
        factories = ((self.root / 'models.json', self.registry, []),
                     (self.root / 'settings.json', settings.Settings, {'keep_bg_default': 'false'}),
                     (self.root / 'hardware.json', hardware_profile.HardwareProfileStore, {'best_device': []}))
        for path, factory, data in factories:
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertLogs('core.json_store', 'WARNING'):
                factory()
            self.assertEqual(json.loads(path.read_text()), data)
            self.assertEqual(len(list(self.root.glob(path.name + '.corrupt-*.bak'))), 1)

    def test_backup_failure_blocks_overwrite(self):
        registry = self.registry()
        path = self.root / 'models.json'
        path.write_bytes(b'broken')
        with patch.object(json_store, 'atomic_bytes', side_effect=PermissionError('backup denied')):
            with self.assertRaises(PermissionError):
                self.add(registry)
        self.assertEqual(path.read_bytes(), b'broken')
        self.assertEqual(registry._entries, [])

    def test_read_permission_error_is_not_default_or_corruption(self):
        store = settings.Settings()
        store.update({'default_language': 'fr'})
        original = builtins.open
        def denied(path, *args, **kwargs):
            if str(path) == str(self.root / 'settings.json'):
                raise PermissionError('read denied')
            return original(path, *args, **kwargs)
        with patch('builtins.open', side_effect=denied):
            with self.assertRaises(PermissionError):
                store.update({'default_language': 'de'})
        self.assertEqual(store._values['default_language'], 'fr')
        self.assertEqual(list(self.root.glob('*.bak')), [])

    def test_hardware_refresh_failure_and_defensive_profile(self):
        store = hardware_profile.HardwareProfileStore()
        profile = store.capture(self.monitor())
        profile['best_device']['name'] = 'changed'
        self.assertEqual(store.get()['best_device']['name'], 'CPU')
        before = deepcopy(store._profile)
        with patch.object(json_store.os, 'replace', side_effect=OSError('save failed')):
            with self.assertRaises(OSError):
                store.capture(self.monitor('New CPU'), force=True)
        self.assertEqual(store._profile, before)
        self.assertEqual(store.get(), before)

    def test_hardware_invalid_capacity_rejected(self):
        store = hardware_profile.HardwareProfileStore()
        monitor = self.monitor()
        monitor.sample = lambda device: {'ram_total_gb': -1}
        with self.assertRaises(ValueError):
            store.capture(monitor)
        self.assertIsNone(store._profile)
        self.assertFalse((self.root / 'hardware.json').exists())

    def test_render_marker_atomic_failure_preserves_old_record(self):
        render_state.mark_started('one.mp4', {'source_language': 'fr'}, 'video_dub')
        before = (self.root / 'render.json').read_bytes()
        with patch.object(json_store.os, 'replace', side_effect=OSError('save failed')):
            with self.assertRaises(OSError):
                render_state.mark_started('two.mp4', {}, 'audio_dub')
        self.assertEqual((self.root / 'render.json').read_bytes(), before)
        self.assertEqual(render_state.get_interrupted()['params']['source_language'], 'fr')
        offered = render_state.get_interrupted()
        self.assertIsNotNone(offered)  # Reading does not consume recovery.
        self.assertTrue(render_state.discard(offered['recovery_token']))
        self.assertIsNone(render_state.get_interrupted())

    def test_invalid_render_marker_rejected(self):
        for path, params, template in (('', {}, 'video_dub'), ('one', [], 'video_dub'), ('one', {}, 'bad')):
            with self.assertRaises(ValueError):
                render_state.mark_started(path, params, template)
        self.assertFalse((self.root / 'render.json').exists())

    def test_corrupt_render_marker_preserved_before_consumption(self):
        path = self.root / 'render.json'
        path.write_bytes(b'[]')
        with self.assertLogs('core.json_store', 'WARNING'):
            self.assertIsNone(render_state.get_interrupted())
        self.assertEqual(next(self.root.glob('*.bak')).read_bytes(), b'[]')

    def test_clear_missing_idempotent_other_errors_surface(self):
        render_state.clear()
        render_state.mark_started('one', {}, 'video_dub')
        with patch.object(json_store.os, 'unlink', side_effect=PermissionError('remove denied')):
            with self.assertRaises(PermissionError):
                render_state.clear()
        self.assertTrue((self.root / 'render.json').exists())

    def test_nonfinite_existing_json_is_preserved(self):
        path = self.root / 'settings.json'
        path.write_bytes(b'{"default_task_priority": NaN}')
        with self.assertLogs('core.json_store', 'WARNING'):
            self.assertEqual(settings.Settings().get('default_task_priority'), 75)
        self.assertEqual(next(self.root.glob('*.bak')).read_bytes(), path.read_bytes())


class PersistenceBridgeTests(unittest.TestCase):
    def setUp(self):
        from dev import test_render_queue
        test_render_queue.RenderQueueTests.setUp(self)

    def test_failed_marker_write_does_not_clear_prior_record_or_run_pipeline(self):
        self.state.mark_started.side_effect = OSError('cannot save marker')
        self.bridge._run_render('one.mp4', {}, 'video_dub')
        self.state.clear.assert_not_called()
        self.pipeline.run.assert_not_called()
        self.assertEqual(self.bridge.get_session_state()['render']['status'], 'error')

    def test_pending_warning_delivery_retries_after_notification_failure(self):
        import threading
        from bridge import api
        self.bridge._persistence_warning_lock = threading.Lock()
        self.bridge._persistence_warnings = []
        self.bridge._queue_persistence_warning('recoverable settings warning')
        with patch.object(api.webview, 'windows', [object()]):
            self.events.side_effect = RuntimeError('page reconnecting')
            self.bridge._flush_persistence_warnings()
            self.assertEqual(len(self.bridge._persistence_warnings), 1)
            self.events.side_effect = None
            self.bridge._flush_persistence_warnings()
        self.assertEqual(self.bridge._persistence_warnings, [])
        self.events.assert_called_with('log', {'level': 'warning', 'message': 'recoverable settings warning'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
