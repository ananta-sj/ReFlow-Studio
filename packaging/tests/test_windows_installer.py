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
