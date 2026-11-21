"""POSIX installer contracts; synthetic files only."""
import contextlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('install_posix',ROOT/'packaging/install_posix.py')
install=importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)

class PosixInstallerTests(unittest.TestCase):
    def fixture(self, root):
        source=root/'source';source.mkdir()
        (source/'ReflowStudio').write_text('program')
        row=dict(path='ReflowStudio',sha256=install.sha(source/'ReflowStudio'))
        (source/'candidate-manifest.json').write_text(json.dumps(dict(target='linux-x64',files=[row])))
        return source

    def test_install_upgrade_and_uninstall_preserve_user_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.fixture(root);home=root/'home';home.mkdir()
            with patch.object(install,'home_directory',return_value=home), patch.object(install,'application_idle',contextlib.nullcontext):
                install.install(source,'linux-x64')
                payload=home/'.local/share/ReflowStudio'
                state=payload/'outputs/personal.keep';state.parent.mkdir();state.write_text('keep')
                install.install(source,'linux-x64')
                self.assertEqual(state.read_text(),'keep')
                install.uninstall('linux-x64')
                self.assertFalse((payload/'ReflowStudio').exists())
                self.assertEqual(state.read_text(),'keep')

    def test_tampering_and_traversal_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.fixture(root)
            (source/'ReflowStudio').write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'checksum'):
                install.inventory(source,'linux-x64')
            (source/'candidate-manifest.json').write_text(json.dumps(dict(target='linux-x64',files=[dict(path='../escape',sha256='x')])))
            with self.assertRaisesRegex(RuntimeError,'path'):
                install.inventory(source,'linux-x64')

    def test_unowned_install_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.fixture(root);home=root/'home'
            existing=home/'.local/share/ReflowStudio';existing.mkdir(parents=True)
            (existing/'ReflowStudio').write_text('unrelated')
            with patch.object(install,'home_directory',return_value=home), patch.object(install,'application_idle',contextlib.nullcontext):
                with self.assertRaisesRegex(RuntimeError,'unowned'):
                    install.install(source,'linux-x64')
            self.assertEqual((existing/'ReflowStudio').read_text(),'unrelated')

    def test_mac_install_has_writable_payload_outside_application(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.mkdir();home=root/'home';home.mkdir()
            entries=[]
            for name in ('ReflowStudio.app/Contents/MacOS/ReflowStudio',
                         'ReflowStudio.app/Contents/Resources/ReflowStudio/main.py'):
                file=source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('fixture')
                entries.append(dict(path=name,sha256=install.sha(file)))
            (source/'candidate-manifest.json').write_text(json.dumps(dict(target='macos-arm64',files=entries)))
            with patch.object(install,'home_directory',return_value=home),patch.object(install,'application_idle',contextlib.nullcontext):
                install.install(source,'macos-arm64')
                application=home/'Applications/ReflowStudio.app'
                payload=home/'Library/Application Support/ReflowStudio/runtime'
                self.assertEqual((payload/'main.py').read_text(),'fixture')
                self.assertEqual((application/'Contents/Resources/ReflowStudio/main.py').read_text(),'fixture')
                spec=importlib.util.spec_from_file_location('posix_launcher_test',ROOT/'packaging/native_launcher.py')
                launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
                with patch.object(launcher.sys,'platform','darwin'),patch.object(launcher.sys,'executable',str(application/'Contents/MacOS/ReflowStudio')),patch.object(Path,'home',return_value=home):
                    self.assertEqual(launcher.payload_root(),payload)
                state=payload/'settings.json';state.write_text('keep')
                install.uninstall('macos-arm64')
                self.assertFalse(application.exists())
                self.assertEqual(state.read_text(),'keep')

    def test_uninstall_rejects_receipt_pointing_at_unrelated_file(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            payload=home/'.local/share/ReflowStudio';payload.mkdir(parents=True)
            personal=home/'personal';personal.write_text('keep')
            (payload/'.installation.json').write_text(json.dumps(dict(target='linux-x64',files=[dict(path='personal',sha256=install.sha(personal))])))
            with patch.object(install,'home_directory',return_value=home),patch.object(install,'application_idle',contextlib.nullcontext):
                with self.assertRaisesRegex(RuntimeError,'leaves installed'):
                    install.uninstall('linux-x64')
            self.assertEqual(personal.read_text(),'keep')

    def test_self_extractor_offset_starts_exactly_at_archive_bytes(self):
        spec=importlib.util.spec_from_file_location('posix_builder_test',ROOT/'packaging/build_posix_installer.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        header=builder.linux_header('fixture','a'*64)
        lines=header.splitlines(keepends=True)
        import re
        start=int(re.search(rb'tail -n \+(\d+)',header).group(1))
        self.assertEqual(start,len(lines)+1)
        self.assertEqual((header+b'ARCHIVE').splitlines(keepends=True)[start-1],b'ARCHIVE')

    def test_real_program_update_preserves_generated_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.fixture(root);home=root/'home';home.mkdir()
            with patch.object(install,'home_directory',return_value=home),patch.object(install,'application_idle',contextlib.nullcontext):
                install.install(source,'linux-x64')
                payload=home/'.local/share/ReflowStudio'
                (payload/'settings.json').write_text('keep')
                (source/'ReflowStudio').write_text('updated program')
                (source/'candidate-manifest.json').write_text(json.dumps(dict(target='linux-x64',files=[dict(path='ReflowStudio',sha256=install.sha(source/'ReflowStudio'))])))
                install.install(source,'linux-x64')
                self.assertEqual((payload/'ReflowStudio').read_text(),'updated program')
                self.assertEqual((payload/'settings.json').read_text(),'keep')

    def test_existing_unrelated_desktop_entry_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=self.fixture(root);home=root/'home';home.mkdir()
            desktop=home/'.local/share/applications/ReflowStudio.desktop'
            desktop.parent.mkdir(parents=True);desktop.write_text('unrelated')
            with patch.object(install,'home_directory',return_value=home),patch.object(install,'application_idle',contextlib.nullcontext):
                with self.assertRaisesRegex(RuntimeError,'unowned'):
                    install.install(source,'linux-x64')
            self.assertEqual(desktop.read_text(),'unrelated')
            self.assertFalse((home/'.local/share/ReflowStudio/ReflowStudio').exists())
