import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core.stage_checkpoints import environment_identity, file_identity


class EnvironmentIdentityTests(unittest.TestCase):
    def test_large_library_is_inventoried_without_reading_its_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'torch/lib').mkdir(parents=True)
            library = root/'torch/lib/large.dll'
            library.write_bytes(b'library')
            def read(path):
                self.assertNotEqual(Path(path), library)
                return file_identity(path)
            with patch('core.stage_checkpoints.file_identity', side_effect=read):
                before = environment_identity(root)
                library.write_bytes(b'updated-library')
                self.assertNotEqual(before, environment_identity(root))

    def test_metadata_content_changes_invalidate_even_when_size_and_time_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'model.dist-info').mkdir()
            metadata = root/'model.dist-info/METADATA'
            metadata.write_text('Version: 1')
            stamp = metadata.stat()
            before = environment_identity(root)
            metadata.write_text('Version: 2')
            os.utime(metadata, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertNotEqual(before, environment_identity(root))

    def test_bytecode_caches_do_not_invalidate_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'module.py').write_text('source')
            before = environment_identity(root)
            (root/'__pycache__').mkdir()
            (root/'__pycache__/module.pyc').write_bytes(b'cache')
            self.assertEqual(before, environment_identity(root))
