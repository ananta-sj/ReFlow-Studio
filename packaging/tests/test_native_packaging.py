"""Build contracts independent of model assets, desktop services and AI packages."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[2]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'packaging'/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher=load('native_launcher')
runtime=load('prepare_ci_runtime')
source_export=load('create_source_archive')
splitter=load('split_release_asset')


class LauncherTests(unittest.TestCase):
    def test_linux_child_does_not_inherit_frozen_library_or_python_paths(self):
        with patch.dict('os.environ',{'LD_LIBRARY_PATH':'/frozen','LD_LIBRARY_PATH_ORIG':'/original',
                                     'PYTHONHOME':'wrong','PYTHONPATH':'wrong'},clear=True), patch.object(sys,'platform','linux'):
            env=launcher.child_environment(Path('/payload'),verify=True)
        self.assertEqual(env['LD_LIBRARY_PATH'],'/original')
        self.assertNotIn('PYTHONHOME',env)
        self.assertNotIn('PYTHONPATH',env)
        self.assertEqual(env['PYWEBVIEW_GUI'],'qt')
        self.assertEqual(env['REFLOW_OFFLINE'],'1')

    def test_originally_absent_library_path_remains_absent(self):
        with patch.dict('os.environ',{'LD_LIBRARY_PATH':'/frozen'},clear=True),patch.object(sys,'platform','linux'):
            env=launcher.child_environment(Path('/payload'))
        self.assertNotIn('LD_LIBRARY_PATH',env)
        self.assertNotIn('REFLOW_OFFLINE',env)

    def test_macos_payload_lives_inside_application_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            executable=root/'ReflowStudio.app/Contents/MacOS/ReflowStudio'
            with patch.object(sys,'platform','darwin'),patch.object(sys,'executable',str(executable)):
                self.assertEqual(launcher.payload_root(),root/'ReflowStudio.app/Contents/Resources/ReflowStudio')

    def test_start_uses_real_included_python_and_preserves_app_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            python=root/'python/python.exe';python.parent.mkdir();python.write_bytes(b'fixture')
            (root/'main.py').write_text('# fixture')
            with patch.object(launcher,'payload_root',return_value=root),patch.object(sys,'argv',['ReflowStudio.exe']), \
                 patch.object(launcher,'child_environment',return_value={}), \
                 patch.object(subprocess,'run',side_effect=[Mock(returncode=0),Mock(returncode=7)]) as run:
                with self.assertRaisesRegex(RuntimeError,'stopped with an error'):
                    launcher.main()
            self.assertEqual(run.call_args_list[1].args[0],[str(python),'-B',str(root/'main.py')])
            self.assertEqual(run.call_args_list[1].kwargs['cwd'],root)

    def test_failed_integrity_never_starts_application(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            python=root/'python/python.exe';python.parent.mkdir();python.write_bytes(b'fixture')
            (root/'main.py').write_text('# fixture')
            with patch.object(launcher,'payload_root',return_value=root),patch.object(sys,'argv',['ReflowStudio.exe']), \
                 patch.object(launcher,'child_environment',return_value={}),patch.object(subprocess,'run',return_value=Mock(returncode=1)) as run:
                with self.assertRaisesRegex(RuntimeError,'Runtime checks failed'):
                    launcher.main()
            self.assertEqual(run.call_count,1)


class RuntimeDownloadTests(unittest.TestCase):
    def fixture(self,root,payload,checksum):
        (root/'packaging').mkdir()
        (root/'packaging/ci_runtime_sources.json').write_text(json.dumps(dict(
            python='3.13.18',release='20261026',targets={'windows-x64':dict(triple='test',sha256=checksum)})))
        return patch.multiple(runtime,ROOT=root)

    def test_foreign_runner_is_rejected_before_network_access(self):
        with patch.object(sys,'argv',['prepare','linux-x64']),patch.object(sys,'platform','win32'), \
             patch.object(runtime.platform,'machine',return_value='AMD64'), \
             patch.object(runtime.urllib.request,'urlopen') as request:
            with self.assertRaisesRegex(RuntimeError,'does not match'):
                runtime.main()
        request.assert_not_called()

    def test_unverified_runtime_is_never_extracted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);payload=b'not a verified archive'
            with self.fixture(root,payload,'0'*64),patch.object(sys,'argv',['prepare','windows-x64']), \
                 patch.object(sys,'platform','win32'),patch.object(runtime.platform,'machine',return_value='AMD64'), \
                 patch.object(runtime.urllib.request,'urlopen',return_value=io.BytesIO(payload)),patch.object(tarfile,'open') as extract:
                with self.assertRaisesRegex(RuntimeError,'checksum differs'):
                    runtime.main()
            extract.assert_not_called()
            self.assertFalse((root/'build/ci-runtime').exists())

    @unittest.skipUnless(hasattr(tarfile,'data_filter'),'Requires CI Python 3.13 data filter')
    def test_archive_traversal_cannot_write_outside_runtime(self):
        contents=io.BytesIO()
        with tarfile.open(fileobj=contents,mode='w:gz') as archive:
            item=tarfile.TarInfo('../escape.txt');item.size=1
            archive.addfile(item,io.BytesIO(b'x'))
        payload=contents.getvalue()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.fixture(root,payload,hashlib.sha256(payload).hexdigest()), \
                 patch.object(sys,'argv',['prepare','windows-x64']),patch.object(sys,'platform','win32'), \
                 patch.object(runtime.platform,'machine',return_value='AMD64'), \
                 patch.object(runtime.urllib.request,'urlopen',return_value=io.BytesIO(payload)):
                with self.assertRaises(tarfile.FilterError):
                    runtime.main()
            self.assertFalse((root/'build/escape.txt').exists())

    def test_pinned_recipe_covers_both_mac_architectures_and_all_three_os(self):
        recipe=json.loads((ROOT/'packaging/ci_runtime_sources.json').read_text())
        self.assertEqual(set(recipe['targets']),{'windows-x64','linux-x64','macos-arm64','macos-x64'})
        for row in recipe['targets'].values():
            self.assertEqual(len(row['sha256']),64)
            self.assertTrue(set(row['sha256'])<=set('0123456789abcdef'))


class SourceExportTests(unittest.TestCase):
    def test_nested_vendor_repository_is_exported_as_source_not_as_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            vendor=root/'dev/vendor/Example';(vendor/'.git').mkdir(parents=True)
            (vendor/'code.py').write_text('# source')
            def listing(command,**kwargs):
                if command[1]=='rev-parse': return 'abc123\n'
                return b'dev/vendor/Example/\0' if kwargs['cwd']==root else b'code.py\0'
            with patch.object(source_export,'ROOT',root),patch.object(source_export.subprocess,'check_output',side_effect=listing):
                names,revisions,missing=source_export.collect_names()
            self.assertEqual(names,['dev/vendor/Example/code.py'])
            self.assertEqual(revisions,{'dev/vendor/Example':'abc123'})
            self.assertEqual(missing,[])

    def test_model_named_source_directory_is_retained(self):
        self.assertTrue(source_export.include('core/Wav2Lip/models/wav2lip.py'))
        self.assertTrue(source_export.include('core/MuseTalk/musetalk/models/unet.py'))

    def test_weights_media_private_state_and_runtime_files_are_excluded(self):
        for name in ('models/xtts/default/config.json','core/Wav2Lip/checkpoints/voice.pth',
                     'core/MuseTalk/models/model/config.json','Sample/private.mp4',
                     'settings.json','frontend/.env','runtime_profiles/f5/profile.json',
                     'docs/validation/private.wav','core/__pycache__/a.pyc',
                     'dev/vendor/Example/tool.exe','core/vendor/Example/runtime.dll'):
            with self.subTest(name=name):
                self.assertFalse(source_export.include(name))

    def test_rebuild_inputs_and_native_build_workflow_are_exported(self):
        for name in ('README.md','frontend/package-lock.json','frontend/vite.config.ts',
                     '.github/workflows/build.yml','packaging/ci_runtime_sources.json',
                     'packaging/requirements-desktop.txt','dev/test_voice_mastering.py'):
            with self.subTest(name=name):
                self.assertTrue(source_export.include(name))


class ReleasePartsTests(unittest.TestCase):
    def test_assembly_metadata_cannot_inject_shell_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaises(ValueError):
                splitter.write_helper(root,'Reflow.zip',[dict(name="bad';exit;.part01",sha256='0'*64)],'0'*64)
            self.assertFalse((root/'Assemble-ReflowStudio.cmd').exists())

    def test_parts_reproduce_input_and_never_replace_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'Reflow.zip';payload=bytes(range(256))*30
            source.write_bytes(payload)
            report=splitter.split(source,root/'parts',part_bytes=1000)
            self.assertTrue(all(row['bytes']<=1000 for row in report['parts']))
            self.assertEqual(b''.join((root/'parts'/row['name']).read_bytes() for row in report['parts']),payload)
            self.assertEqual(source.read_bytes(),payload)
            with self.assertRaisesRegex(RuntimeError,'already exists'):
                splitter.split(source,root/'parts',part_bytes=1000)

    def test_oversized_release_parts_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaises(ValueError):
                splitter.split(root/'Reflow.zip',root/'parts',part_bytes=2*1024**3)
            self.assertFalse((root/'parts').exists())


if __name__=='__main__':
    unittest.main()
