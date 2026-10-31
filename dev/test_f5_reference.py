from pathlib import Path
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from core.feature_worker import prepare_f5_reference


class F5ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.reference = Path(self.folder.name) / 'reference.wav'
        self.reference.write_bytes(b'fixture audio')
        self.params = dict(reference_audio=str(self.reference), device='cpu')
        self.utils = SimpleNamespace(asr_pipe=object(), preprocess_ref_audio_text=Mock(
            return_value=(str(self.reference), 'Reference speech.')))
        module = ModuleType('f5_tts.infer')
        module.utils_infer = self.utils
        modules = patch.dict('sys.modules', {'f5_tts.infer': module})
        modules.start()
        self.addCleanup(modules.stop)
        initializer = patch('core.feature_worker.prepare_f5_asr')
        self.prepare = initializer.start()
        self.addCleanup(initializer.stop)

    def test_transcription_is_cached_and_model_released_before_synthesis(self):
        cache = {}
        first = prepare_f5_reference(self.params, cache)
        self.assertIsNone(self.utils.asr_pipe)
        self.assertEqual(first, prepare_f5_reference(self.params, cache))
        self.prepare.assert_called_once()
        self.utils.preprocess_ref_audio_text.assert_called_once()
        self.reference.write_bytes(b'changed fixture audio')
        prepare_f5_reference(self.params, cache)
        self.assertEqual(self.prepare.call_count, 2)

    def test_transcription_failure_still_releases_model(self):
        self.utils.preprocess_ref_audio_text.side_effect = RuntimeError('ASR failed')
        with self.assertRaisesRegex(RuntimeError, 'ASR failed'):
            prepare_f5_reference(self.params, {})
        self.assertIsNone(self.utils.asr_pipe)

    def test_explicit_text_bypasses_asr(self):
        self.assertEqual(prepare_f5_reference({**self.params, 'reference_text': 'Known speech.'}),
                         (str(self.reference), 'Known speech.'))
        self.prepare.assert_not_called()

    def test_empty_recognition_does_not_condition_speech(self):
        self.utils.preprocess_ref_audio_text.return_value = (str(self.reference), '. ')
        with self.assertRaisesRegex(RuntimeError, 'no usable speech'):
            prepare_f5_reference(self.params)
        self.assertIsNone(self.utils.asr_pipe)
