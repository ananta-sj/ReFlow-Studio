"""Target token and stage cleanup must not depend on a live service/model."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.llm_translator import LLMTranslator
from core.providers.translation.ollama_m2m100_local import OllamaM2M100LocalProvider
from core.pipeline import _translation_stage


class M2M100LifecycleTests(unittest.TestCase):
    def translator(self, target=20):
        subject = LLMTranslator.__new__(LLMTranslator)
        subject.mode = 'm2m100';subject.device = 'cpu'
        subject.tokenizer = Mock()
        subject.tokenizer.unk_token_id = 0
        subject.tokenizer.get_lang_id.side_effect = lambda code: 10 if code=='en' else target
        subject.model = Mock()
        subject.model.config.max_position_embeddings = 1024
        subject.model.generate.return_value = [[2, 20, 30, 2]]
        subject.tokenizer.eos_token_id = 2;subject.tokenizer.pad_token_id = 1
        subject.tokenizer.return_value.to.return_value = {'input_ids': [[1,2,3]]}
        subject.tokenizer.batch_decode.return_value = ['नमस्ते।']
        return subject

    def test_invalid_target_token_never_encodes_or_generates(self):
        for value in (None, True, -1, 0, 'hi', 1.5):
            subject = self.translator(value)
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'real target token'):
                subject.translate('Hello', 'Hindi', source_language='en')
            subject.tokenizer.assert_not_called()
            subject.model.generate.assert_not_called()

    def test_valid_target_is_passed_to_generation(self):
        subject = self.translator()
        self.assertEqual(subject.translate('Hello', 'Hindi', source_language='en'), 'नमस्ते।')
        self.assertEqual(subject.model.generate.call_args.kwargs['forced_bos_token_id'], 20)

    def test_release_drops_local_weights_and_is_idempotent(self):
        subject = self.translator();subject.release();subject.release()
        self.assertIsNone(subject.model);self.assertIsNone(subject.tokenizer)
        self.assertEqual(subject.mode, 'released')

    def test_stage_success_releases_only_owned_translator(self):
        provider = OllamaM2M100LocalProvider()
        translator = Mock();provider._translator = translator
        with _translation_stage(provider):pass
        translator.release.assert_called_once()
        self.assertIsNone(provider._translator)
        provider.release()
        translator.release.assert_called_once()

    def test_stage_error_and_generator_close_release(self):
        for error in (RuntimeError('original failure'), GeneratorExit()):
            provider = OllamaM2M100LocalProvider();translator = Mock();provider._translator = translator
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                with _translation_stage(provider):raise error
            translator.release.assert_called_once()
            self.assertIsNone(provider._translator)

    def test_release_does_not_initialize_lazy_provider(self):
        with patch('core.providers.translation.ollama_m2m100_local.LLMTranslator') as factory:
            OllamaM2M100LocalProvider().release()
        factory.assert_not_called()

    def test_failed_initialization_drops_partial_tokenizer(self):
        subject = LLMTranslator.__new__(LLMTranslator)
        tokenizer, model = Mock(), Mock()
        model.from_pretrained.side_effect = RuntimeError('fixture model failure')
        with patch.dict('sys.modules', transformers=SimpleNamespace(M2M100Tokenizer=tokenizer,M2M100ForConditionalGeneration=model)), patch('core.model_assets.ensure_assets'):
            with self.assertRaisesRegex(RuntimeError, 'fixture model failure'):
                subject.init_m2m100()
        self.assertEqual(subject.mode, 'broken')
        self.assertIsNone(subject.tokenizer);self.assertIsNone(subject.model)


if __name__ == '__main__':
    unittest.main()
