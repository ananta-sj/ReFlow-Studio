"""Security and compatibility adapters reject drift before upstream execution."""
import hashlib,sys,types,unittest
from unittest.mock import patch
from core import visual_imports as guard

class VisualImportTests(unittest.TestCase):
    def transform(self,name,source):
        with patch.dict(guard.HASHES,{name:hashlib.sha256(source).hexdigest()}):return guard.guarded_source(name,source)
    def test_training_entrypoints_cannot_execute_original_bodies(self):
        source=b'\n'.join(('def '+name+'(*a,**kw):\n    raise AssertionError("unsafe")\n').encode() for name in guard.LAUNCHERS)+b'\ndef inference_helper(): return 7\n'
        namespace={};exec(self.transform('basicsr.utils.dist_util',source),namespace)
        for name in guard.LAUNCHERS:
            with self.assertRaisesRegex(RuntimeError,'training is disabled'):namespace[name]()
        self.assertEqual(namespace['inference_helper'](),7);self.assertTrue(namespace['__reflow_visual_guard__'])
    def test_vision_import_is_redirected_to_current_function(self):
        source=b'from torchvision.transforms.functional_tensor import rgb_to_grayscale\n'
        result=self.transform('basicsr.data.degradations',source)
        self.assertIn('from torchvision.transforms.functional import rgb_to_grayscale',result);self.assertNotIn('functional_tensor',result)
    def test_unexpected_source_is_rejected(self):
        for name in guard.HASHES:
            with self.assertRaisesRegex(RuntimeError,'source changed'):guard.guarded_source(name,b'changed')
    def test_missing_launcher_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'layout changed'):self.transform('basicsr.utils.dist_util',b'def init_dist(): pass\n')
    def test_preloaded_package_is_rejected_before_hook(self):
        before=list(sys.meta_path)
        with patch.object(guard.metadata,'version',return_value='1.4.2'),patch.dict(sys.modules,{'basicsr':types.ModuleType('basicsr')}):
            with self.assertRaisesRegex(RuntimeError,'loaded before'):
                with guard.guarded_imports():pass
        self.assertEqual(before,sys.meta_path)
    def test_wrong_version_is_rejected(self):
        with patch.object(guard.metadata,'version',return_value='other'):
            with self.assertRaisesRegex(RuntimeError,'reviewed version'):
                with guard.guarded_imports():pass
    def test_hook_removed_on_import_failure(self):
        before=list(sys.meta_path)
        with patch.object(guard.metadata,'version',return_value='1.4.2'),patch.dict(sys.modules,clear=False):
            for name in list(sys.modules):
                if name=='basicsr' or name.startswith('basicsr.'):sys.modules.pop(name)
            with self.assertRaisesRegex(RuntimeError,'failure'):
                with guard.guarded_imports():raise RuntimeError('failure')
        self.assertEqual(before,sys.meta_path)
    def test_unrelated_imports_ignored(self):
        with patch.object(guard.importlib.machinery.PathFinder,'find_spec') as find:self.assertIsNone(guard._Finder().find_spec('unrelated'))
        find.assert_not_called()
