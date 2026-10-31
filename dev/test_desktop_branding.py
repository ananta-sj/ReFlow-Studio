import ctypes
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,MagicMock,patch

import main as application


class BrandingTests(unittest.TestCase):
    def test_windows_identity_is_explicit(self):
        function=Mock(return_value=0)
        library=Mock();library.shell32.SetCurrentProcessExplicitAppUserModelID=function
        with patch.object(sys,'platform','win32'),patch.object(ctypes,'windll',library,create=True):
            self.assertTrue(application._set_windows_app_id())
        function.assert_called_once_with('ReflowStudio.Desktop')

    def test_other_platforms_do_not_call_windows(self):
        with patch.object(sys,'platform','linux'):
            self.assertFalse(application._set_windows_app_id())

    def test_platform_icon_uses_packaged_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'assets').mkdir()
            for name in ('icon.ico','icon.png'): (root/'assets'/name).write_bytes(b'fixture')
            with patch.object(application,'RESOURCE_DIR',str(root)),patch.object(sys,'platform','win32'):
                self.assertEqual(application._application_icon_path(),str(root/'assets/icon.ico'))
            with patch.object(application,'RESOURCE_DIR',str(root)),patch.object(sys,'platform','linux'):
                self.assertEqual(application._application_icon_path(),str(root/'assets/icon.png'))

    def test_real_startup_sets_identity_before_window_and_passes_icon(self):
        sequence=[]
        with patch.object(application,'_set_windows_app_id',side_effect=lambda:sequence.append('identity')), \
             patch.object(application,'PythonBridge',side_effect=lambda:sequence.append('bridge') or Mock()), \
             patch.object(application.webview,'create_window',return_value=MagicMock()), \
             patch.object(application,'TrayController'),patch.object(application.webview,'start') as start:
            application.main()
        self.assertEqual(sequence,['identity','bridge'])
        self.assertEqual(start.call_args.kwargs['icon'],application._application_icon_path())

    def test_tray_uses_the_logo_pixels(self):
        from core.tray import _build_icon_image
        from PIL import Image
        with Image.open(Path(application.BASE_DIR)/'assets/icon.png') as original:
            expected=original.convert('RGBA')
        actual=_build_icon_image()
        try:
            self.assertEqual(actual.size,expected.size)
            self.assertEqual(actual.tobytes(),expected.tobytes())
        finally: actual.close();expected.close()


if __name__=='__main__':unittest.main()
