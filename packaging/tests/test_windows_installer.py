"""Installer boundaries, without requiring a compiler or Windows desktop."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('windows_installer', ROOT/'packaging/build_windows_installer.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallerTests(unittest.TestCase):
    def test_rejects_unlisted_personal_files_and_modified_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'ReflowStudio.exe').write_bytes(b'fixture')
            entry = dict(path='ReflowStudio.exe', bytes=7, sha256=installer.sha(root/'ReflowStudio.exe'))
            (root/'candidate-manifest.json').write_text(json.dumps(dict(target='windows-x64', files=[entry])))
            installer.validate_payload(root)
            (root/'settings.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'inventory'):
                installer.validate_payload(root)
            (root/'settings.json').unlink()
            (root/'ReflowStudio.exe').write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                installer.validate_payload(root)

    def test_installer_is_per_user_and_never_recursively_deletes_user_data(self):
        script = (ROOT/'packaging/windows/desktop-preview.iss').read_text()
        self.assertIn('PrivilegesRequired=lowest', script)
        self.assertIn('{localappdata}', script)
        self.assertNotIn('[UninstallDelete]', script)
        self.assertIn('CloseApplications=no', script)
        self.assertIn('LockFile(', script)

    def test_ci_installer_acceptance_is_before_upload_and_cannot_be_skipped_on_failure(self):
        workflow = (ROOT/'.github/workflows/build.yml').read_text()
        compile_at = workflow.index('run: python packaging/build_windows_installer.py')
        verify_at = workflow.index('run: python packaging/verify_windows_installer.py')
        upload_at = workflow.index('- name: Upload candidate downloads')
        self.assertLess(compile_at, verify_at)
        self.assertLess(verify_at, upload_at)
        self.assertNotIn('continue-on-error', workflow[compile_at:upload_at])

    def test_installer_sources_are_in_clean_export(self):
        spec = importlib.util.spec_from_file_location('source_export_installer_test', ROOT/'packaging/create_source_archive.py')
        export = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(export)
        for name in ('packaging/windows/desktop-preview.iss', 'packaging/build_windows_installer.py',
                     'packaging/verify_windows_installer.py'):
            self.assertTrue(export.include(name), name)


class UninstallerCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('windows_verify_test',ROOT/'packaging/verify_windows_installer.py')
        cls.verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.verify)

    def test_waits_for_clone_to_release_log(self):
        from unittest.mock import patch
        with patch.object(self.verify,'log_is_released',side_effect=[False,False,True]) as probe, patch.object(self.verify.time,'sleep'):
            self.verify.wait_for_uninstaller(Path('fixture.log'))
        self.assertEqual(probe.call_count,3)

    def test_stuck_uninstaller_fails_instead_of_ignoring_cleanup(self):
        from unittest.mock import patch
        with patch.object(self.verify,'log_is_released',return_value=False),patch.object(self.verify.time,'monotonic',side_effect=[0,61]):
            with self.assertRaisesRegex(TimeoutError,'uninstaller'):
                self.verify.wait_for_uninstaller(Path('fixture.log'),timeout=60)

    def test_windows_real_open_log_is_detected_and_then_released(self):
        import os
        if os.name!='nt':
            self.skipTest('Windows file sharing semantics')
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'uninstall.log'
            with file.open('w') as stream:
                stream.write('fixture');stream.flush()
                self.assertFalse(self.verify.log_is_released(file))
            self.assertTrue(self.verify.log_is_released(file))
