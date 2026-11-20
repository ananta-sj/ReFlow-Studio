import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dev import verify_optional_runtime as verifier


class OptionalVerificationMetadataTests(unittest.TestCase):
    def test_readiness_preserves_bootstrap_and_records_actual_python(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root/'runtime_profiles/vision'
            folder.mkdir(parents=True)
            (folder/'profile.json').write_text(json.dumps(dict(profile='vision', status='prepared', bootstrap_sha256='preserve-me')))
            detector = Mock()
            with patch.object(verifier, 'ROOT', root), patch.object(sys, 'argv', ['verify', 'vision']), patch.object(sys, 'executable', str(folder/'python.exe')), patch.object(verifier.metadata, 'distributions', return_value=[]), patch.object(verifier.importlib, 'import_module'), patch.dict(sys.modules, {'nudenet': SimpleNamespace(NudeDetector=Mock(return_value=detector))}):
                with self.assertRaises(SystemExit) as exit_code:
                    verifier.main()
            self.assertEqual(exit_code.exception.code, 0)
            result = json.loads((folder/'profile.json').read_text())
            self.assertEqual(result['bootstrap_sha256'], 'preserve-me')
            self.assertEqual(result['python'], '.'.join(map(str, sys.version_info[:3])))
            self.assertTrue((folder/'verification.json').is_file())
