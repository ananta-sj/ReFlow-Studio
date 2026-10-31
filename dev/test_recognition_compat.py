"""Decoder adaptation is exact-version, local to faster-whisper and idempotent."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import recognition_compat as compat


class RecognitionCompatTests(unittest.TestCase):
    def test_decoder_preserves_native_options_without_global_patch(self):
        module = SimpleNamespace(open=Mock(return_value='container'), marker=object())
        decoder = compat._AudioAV(module)
        self.assertEqual(decoder.open('a.wav', mode='r', metadata_errors='ignore', timeout=4), 'container')
        module.open.assert_called_once_with('a.wav', mode='r', timeout=4)
        self.assertIs(decoder.marker, module.marker)

    def test_unknown_metadata_policy_is_not_silently_changed(self):
        module = SimpleNamespace(open=Mock())
        with self.assertRaises(ValueError):
            compat._AudioAV(module).open('a.wav', metadata_errors='strict')
        module.open.assert_not_called()

    def test_other_versions_are_unchanged(self):
        with patch.object(compat, 'version', return_value='1.1.0'):
            self.assertFalse(compat.apply())

    def test_apply_is_local_and_idempotent(self):
        module = SimpleNamespace(__version__='19.0.1', open=Mock())
        audio = SimpleNamespace(av=module)
        package = SimpleNamespace(audio=audio)
        with patch.object(compat, 'version', side_effect=lambda name: '1.2.1' if name == 'faster-whisper' else '19.0.1'), \
                patch.dict(sys.modules, {'av': module, 'faster_whisper': package}):
            self.assertTrue(compat.apply())
            wrapper = audio.av
            self.assertTrue(compat.apply())
            self.assertIs(audio.av, wrapper)
            self.assertIs(audio.av._module, module)
            self.assertIs(module.open, wrapper._module.open)

    def test_mismatched_import_is_rejected(self):
        with patch.object(compat, 'version', side_effect=lambda name: '1.2.1' if name == 'faster-whisper' else '19.0.1'), \
                patch.dict(sys.modules, {'av': SimpleNamespace(__version__='18.0.0'),
                                        'faster_whisper': SimpleNamespace(audio=SimpleNamespace())}):
            with self.assertRaisesRegex(RuntimeError, 'disagree'):
                compat.apply()


if __name__ == '__main__':
    unittest.main()
