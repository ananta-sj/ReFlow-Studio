"""Visual runtime drift, selection, preflight and portable inventory."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import visual_runtime as runtime,settings
from core.runtime_integrity import sha
ROOT=Path(__file__).resolve().parents[1]

class VisualRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'temp');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.folder=self.root/'runtime_profiles/visual-candidate';self.folder.mkdir(parents=True)
        (self.folder/'python.exe').write_bytes(b'python')
        from core import visual_imports
        fixtures={}
        for name in visual_imports.HASHES:
            path=self.folder/'Lib/site-packages'/Path(*name.split('.')).with_suffix('.py');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            fixtures[name]=sha(path)
        guard=patch.object(visual_imports,'HASHES',fixtures);guard.start();self.addCleanup(guard.stop)
        rows=[]
        for index in range(55):
            name='fixture-'+str(index);rows.append(dict(name=name,version='1.0'))
            path=self.folder/f'Lib/site-packages/{name}-1.0.dist-info/METADATA';path.parent.mkdir(parents=True);path.write_text(f'Name: {name}\nVersion: 1.0\n')
        lock=self.root/runtime.LOCK;lock.parent.mkdir(parents=True);lock.write_text(json.dumps(dict(packages=rows,bootstrap=[dict(name='python.exe')])))
        for name in runtime.SOURCES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(name)
        (self.folder/'profile.json').write_text(json.dumps(dict(python='3.13.16',device='cpu',lock_sha256=sha(lock),bootstrap_sha256={'python.exe':sha(self.folder/'python.exe')})))
        (self.folder/'routing-recipe.json').write_text(json.dumps(dict(schema='reflow.visual-runtime.v1',source_sha256={name:sha(self.root/name) for name in runtime.SOURCES})))
    def test_valid_recipe_and_stable_identity(self):
        self.assertEqual(runtime.validate(self.root),runtime.validate(self.root));self.assertFalse(runtime.readiness(self.root)['release_ready'])
    def test_worker_source_drift_is_rejected(self):
        (self.root/runtime.SOURCES[-1]).write_text('changed')
        with self.assertRaisesRegex(RuntimeError,'recipe changed'):runtime.validate(self.root)
    def test_bootstrap_drift_is_rejected(self):
        (self.folder/'python.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'bootstrap changed'):runtime.validate(self.root)
    def test_lock_drift_is_rejected(self):
        (self.root/runtime.LOCK).write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'lock changed'):runtime.validate(self.root)
    def test_package_drift_and_duplicates_are_rejected(self):
        path=self.folder/'Lib/site-packages/extra.dist-info/METADATA';path.parent.mkdir();path.write_text('Name: fixture-0\nVersion: 1.0\n')
        with self.assertRaisesRegex(RuntimeError,'Duplicate'):runtime.validate(self.root)
        path.write_text('Name: unexpected\nVersion: 1.0\n')
        with self.assertRaisesRegex(RuntimeError,'approved closure'):runtime.validate(self.root)
    def test_bad_runtime_and_gpu_are_rejected_before_files(self):
        from core.providers.enhancer.gfpgan_local import GFPGANLocalProvider
        with patch('core.visual_runtime.validate') as create:
            for kwargs in [dict(runtime='bad'),dict(runtime='isolated',device='cuda:0')]:
                with self.assertRaises(ValueError):GFPGANLocalProvider(**kwargs)
        create.assert_not_called()
    def test_preflight_uses_selected_worker_contract_without_parent_demucs(self):
        from core.runtime_checks import preflight
        with patch('core.runtime_checks._engine') as engine,patch.object(runtime,'validate') as validate,patch.object(runtime,'model_contract') as model:
            preflight(None,dict(lang='source',keep_bg=False,enhance=True,enhancement_runtime='isolated',compute_device='cpu'),'video_dub')
        validate.assert_called_once();model.assert_called_once()
        self.assertNotIn(unittest.mock.call('gfpgan'),engine.call_args_list)
    def test_background_disabled_does_not_require_candidate(self):
        from core.runtime_checks import preflight
        with patch('core.runtime_checks._engine'),patch.object(runtime,'validate') as validate:
            preflight(None,dict(lang='source',keep_bg=False,enhance=False,enhancement_runtime='isolated'),'video_dub')
        validate.assert_not_called()
    def test_preflight_rejects_bad_selection_and_gpu(self):
        from core.runtime_checks import preflight
        with patch('core.runtime_checks._engine'):
            for runtime_name,device in [('bad','cpu'),('isolated','cuda:0')]:
                with self.assertRaises(ValueError):preflight(None,dict(lang='source',keep_bg=False,enhance=True,enhancement_runtime=runtime_name,compute_device=device),'video_dub')
    def test_settings_default_does_not_migrate_user_file(self):
        path=self.root/'settings.json';path.write_text('{}')
        with patch.object(settings,'SETTINGS_PATH',str(path)):
            store=settings.Settings();self.assertEqual(store.get('enhancement_runtime'),'legacy')
            with self.assertRaises(ValueError):store.update(dict(enhancement_runtime='bad'))
        self.assertEqual(path.read_text(),'{}')
    def test_unavailable_candidate_cannot_be_saved(self):
        from bridge.api import PythonBridge
        bridge=PythonBridge.__new__(PythonBridge);bridge.settings=Mock()
        with patch.object(runtime,'validate',side_effect=RuntimeError('missing')):
            with self.assertRaises(RuntimeError):bridge.update_settings(dict(enhancement_runtime='isolated'))
        bridge.settings.update.assert_not_called()
    def test_portable_includes_lock_and_recipe(self):
        spec=importlib.util.spec_from_file_location('separation_portable',ROOT/'packaging/build_portable.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        with patch.object(builder,'ROOT',self.root),patch.object(builder,'ROOT_FILES',()),patch.object(builder,'TREES',()):
            paths={relative for _,relative,_ in builder.entries([builder.VISUAL_PROFILE])}
        self.assertIn(runtime.LOCK,paths);self.assertIn('runtime_profiles/visual-candidate/routing-recipe.json',paths)
        self.assertNotIn('settings.json',paths)
if __name__=='__main__':unittest.main()
