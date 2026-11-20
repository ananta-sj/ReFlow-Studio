import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from core.integrity import IntegrityDoctor


class IntegrityInstallBoundaryTests(unittest.TestCase):
    def test_optional_engine_cannot_be_installed_in_desktop_environment(self):
        with patch('core.integrity.subprocess.check_call') as install:
            with self.assertRaisesRegex(ValueError, 'isolated'):
                IntegrityDoctor().install_package('basicsr')
            install.assert_not_called()

    def test_desktop_repair_uses_reviewed_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root/'packaging/requirements-desktop.txt'
            manifest.parent.mkdir()
            manifest.write_text('# fixture')
            doctor = IntegrityDoctor()
            doctor.root_dir = str(root)
            with patch('core.integrity.subprocess.check_call') as install:
                doctor.install_package('pillow')
            command = install.call_args.args[0]
            self.assertIn('-I', command)
            self.assertEqual(command[-2:], ['-r', str(manifest)])
