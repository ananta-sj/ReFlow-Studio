import email.parser
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from dev.build_cached_path_compat import build_wheel


class CacheCompatibilityWheelTests(unittest.TestCase):
    def source(self, root):
        path = root/'source.whl'
        with zipfile.ZipFile(path, 'w') as bundle:
            bundle.writestr('cached_path/__init__.py', b'VALUE = 1\n')
            bundle.writestr('cached_path-1.8.10.dist-info/METADATA', 'Name: cached-path\nVersion: 1.8.10\nRequires-Dist: filelock<4.0,>=3.4\nRequires-Dist: huggingface-hub<2.0,>=0.8.1\nRequires-Dist: rich<14.0,>=12.1\n')
            bundle.writestr('cached_path-1.8.10.dist-info/LICENSE', b'fixture licence retained')
            bundle.writestr('cached_path-1.8.10.dist-info/RECORD', '')
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_changes_only_reviewed_metadata_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, digest = self.source(root)
            first = root/'first.whl'
            second = root/'second.whl'
            build_wheel(source, first, digest)
            build_wheel(source, second, digest)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as result:
                self.assertEqual(result.read('cached_path/__init__.py'), b'VALUE = 1\n')
                self.assertEqual(result.read('cached_path-1.8.10+reflow.1.dist-info/LICENSE'), b'fixture licence retained')
                meta = email.parser.Parser().parsestr(result.read('cached_path-1.8.10+reflow.1.dist-info/METADATA').decode())
                self.assertEqual(meta['Version'], '1.8.10+reflow.1')
                self.assertIn('filelock>=4.2.12,<5', meta.get_all('Requires-Dist'))
                self.assertIn('rich<14.0,>=12.1', meta.get_all('Requires-Dist'))

    def test_wrong_source_identity_never_produces_a_wheel(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _ = self.source(root)
            target = root/'result.whl'
            with self.assertRaisesRegex(RuntimeError, 'identity'):
                build_wheel(source, target, '0'*64)
            self.assertFalse(target.exists())
