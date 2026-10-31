"""Saved selection, independent engines and portable recipe closure."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import settings
from core.providers.resolve import resolve_tts
from core.pipeline_contracts import SettingsSnapshot

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('xtts_portable_builder',ROOT/'packaging/build_portable.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        patcher=patch.object(settings,'SETTINGS_PATH',str(self.root/'settings.json'))
        patcher.start();self.addCleanup(patcher.stop)

    def test_existing_settings_keep_legacy_without_disk_migration(self):
        path=self.root/'settings.json';path.write_text('{"default_language":"hi"}')
        before=path.read_bytes();store=settings.Settings()
        self.assertEqual(store.get('xtts_runtime'),'legacy')
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_selection_preserves_saved_bytes(self):
        store=settings.Settings();store.update({'xtts_runtime':'isolated'})
        path=self.root/'settings.json';before=path.read_bytes()
        with self.assertRaises(ValueError):store.update({'xtts_runtime':'unknown'})
        self.assertEqual(path.read_bytes(),before)

    def test_running_snapshot_does_not_follow_later_selection(self):
        store=settings.Settings();frozen=SettingsSnapshot(store.all())
        store.update({'xtts_runtime':'isolated'})
        self.assertEqual(frozen.get('xtts_runtime'),'legacy')

    def test_saved_runtime_reaches_xtts_provider(self):
        registry=Mock();registry.get_active.return_value=None
        with patch('core.providers.tts.xtts_local.XTTSLocalProvider') as factory:
            resolve_tts(registry,'cpu',runtime='isolated')
        factory.assert_called_once_with(device='cpu',runtime='isolated')

    def test_isolated_choice_does_not_change_api_engine(self):
        registry=Mock();registry.get_active.return_value=dict(kind='cloud_api',api_base_url='https://fixture.test',request_preset='custom')
        with patch('core.providers.tts.cloud_rest.TTSCloudRestProvider') as api, patch('core.providers.tts.xtts_local.XTTSLocalProvider') as local:
            resolve_tts(registry,'cuda:0',runtime='isolated')
        api.assert_called_once();local.assert_not_called()

    def test_unavailable_runtime_cannot_be_saved_through_bridge(self):
        from bridge.api import PythonBridge
        bridge=PythonBridge.__new__(PythonBridge);bridge.settings=Mock()
        with patch('core.xtts_runtime.validate',side_effect=RuntimeError('missing')):
            with self.assertRaises(RuntimeError):bridge.update_settings({'xtts_runtime':'isolated'})
        bridge.settings.update.assert_not_called()

    def test_legacy_review_recipe_unchanged_and_trial_changes_it(self):
        from core.cue_review import configuration
        pipeline=Mock();pipeline.registry.list.return_value=[];pipeline.registry.get_active.return_value=None
        old=configuration(pipeline,SettingsSnapshot({'default_language':'en'}))
        self.assertEqual(old,configuration(pipeline,SettingsSnapshot({'default_language':'en','xtts_runtime':'legacy'})))
        self.assertNotEqual(old,configuration(pipeline,SettingsSnapshot({'default_language':'en','xtts_runtime':'isolated'})))

    def test_portable_inventory_contains_profile_and_bound_lock(self):
        profile=self.root/'runtime_profiles'/builder.XTTS_PROFILE;profile.mkdir(parents=True)
        (profile/'python.exe').write_bytes(b'fixture');(profile/'profile.json').write_text('{}')
        lock=self.root/builder.XTTS_LOCK;lock.parent.mkdir(parents=True);lock.write_text('{}')
        with patch.object(builder,'ROOT',self.root),patch.object(builder,'ROOT_FILES',()),patch.object(builder,'TREES',()),patch('core.xtts_runtime.validate') as validate:
            paths={relative for _,relative,_ in builder.entries([builder.XTTS_PROFILE])}
        validate.assert_called_once_with(self.root)
        self.assertIn(builder.XTTS_LOCK,paths)
        self.assertIn('runtime_profiles/'+builder.XTTS_PROFILE+'/python.exe',paths)
        self.assertNotIn('settings.json',paths)

    def test_portable_inventory_refuses_unverified_recipe(self):
        with patch('core.xtts_runtime.validate',side_effect=RuntimeError('recipe changed')):
            with self.assertRaises(RuntimeError):list(builder.entries([builder.XTTS_PROFILE]))

    def test_parallel_copy_preserves_binary_payloads_and_nested_paths(self):
        source=self.root/'source';source.mkdir();output=self.root/'output';output.mkdir()
        entries=[]
        for index in range(70):
            path=source/str(index);path.write_bytes(bytes([index])*100)
            entries.append((path,'nested/'+str(index),'fixture'))
        builder.copy_entries(entries,output,workers=4)
        for path,relative,_ in entries:self.assertEqual(path.read_bytes(),(output/relative).read_bytes())

    def test_parallel_copy_error_is_not_hidden(self):
        output=self.root/'output';output.mkdir()
        with self.assertRaises(FileNotFoundError):
            builder.copy_entries([(self.root/'missing','missing','fixture')],output)
        self.assertFalse((output/'portable-manifest.json').exists())

if __name__=='__main__':unittest.main()
