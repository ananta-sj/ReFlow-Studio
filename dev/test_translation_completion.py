"""Oversize and unfinished translations must never reach speech generation."""
from types import SimpleNamespace
import unittest
from core.translation_completion import require_input_window, require_finished


def completed_model(model, tokenizer):
    model.config.max_position_embeddings = 1024
    model.generate.return_value = [[2, 1, 5, 2]]
    tokenizer.eos_token_id, tokenizer.pad_token_id = 2, 1


class TranslationCompletionTests(unittest.TestCase):
    def test_input_limit_boundary_and_no_silent_truncation(self):
        model = SimpleNamespace(config=SimpleNamespace(max_position_embeddings=4))
        require_input_window({'input_ids': [[1]*4]}, model, 'NLLB')
        with self.assertRaisesRegex(ValueError, 'Split the source'):
            require_input_window({'input_ids': [[1]*5]}, model, 'NLLB')

    def test_unknown_checkpoint_limit_is_explicit(self):
        with self.assertRaisesRegex(RuntimeError, 'valid input token limit'):
            require_input_window({'input_ids': [[1]]}, SimpleNamespace(config=None), 'NLLB')

    def test_completed_translation_can_have_padding(self):
        tokenizer = SimpleNamespace(eos_token_id=2, pad_token_id=1)
        require_finished([[2, 5, 2, 1, 1]], tokenizer, 'NLLB')

    def test_decoder_start_eos_does_not_hide_unfinished_output(self):
        with self.assertRaisesRegex(RuntimeError, 'unfinished'):
            require_finished([[2, 5, 6]], SimpleNamespace(eos_token_id=2, pad_token_id=1), 'NLLB')

    def test_forced_eos_at_token_cap_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'output token limit'):
            require_finished([[2, 5, 5, 2]], SimpleNamespace(eos_token_id=2, pad_token_id=1), 'NLLB', max_new_tokens=3)

    def test_malformed_tokens_cannot_decode_to_false_success(self):
        for tokens in ([], [[2, 'text', 2]], [[2, -1, 2]], [[True, 2]], [[2]], [[2, 2], [2, 2]]):
            with self.subTest(tokens=tokens), self.assertRaises(RuntimeError):
                require_finished(tokens, SimpleNamespace(eos_token_id=2, pad_token_id=1), 'NLLB')
