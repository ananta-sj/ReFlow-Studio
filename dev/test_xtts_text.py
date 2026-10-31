"""Checkpoint-aware short-cue boundaries without loading or downloading models."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from core.xtts_text import should_split_sentences


class XTTSTextTests(unittest.TestCase):
    def model(self, count=10, limit=402, char_limit=253, language='de'):
        return SimpleNamespace(args=SimpleNamespace(gpt_max_text_tokens=limit),
                               tokenizer=SimpleNamespace(char_limits={language: char_limit},
                                                         encode=Mock(return_value=list(range(count)))))

    def test_short_cue_keeps_sentences_together_without_rewriting_text(self):
        model = self.model()
        text = '  Guten Morgen. Willkommen in unserem Studio.  '
        self.assertFalse(should_split_sentences(text, 'de', model))
        model.tokenizer.encode.assert_called_once_with('guten morgen. willkommen in unserem studio.', lang='de')

    def test_checkpoint_character_limit_is_checked_before_tokenization(self):
        model = self.model(char_limit=4)
        self.assertTrue(should_split_sentences('Long speech', 'de', model))
        model.tokenizer.encode.assert_not_called()

    def test_token_expansion_and_checkpoint_boundary_keep_splitting(self):
        for count, limit, expected in ((127, 402, False), (128, 402, True), (31, 32, False), (32, 32, True)):
            with self.subTest(count=count, limit=limit):
                self.assertEqual(should_split_sentences('2040.', 'de', self.model(count, limit)), expected)

    def test_unproven_and_unaffected_languages_retain_established_delivery(self):
        for language in ('en', 'es', 'it', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'ja'):
            model = self.model(language=language.split('-')[0])
            with self.subTest(language=language):
                self.assertTrue(should_split_sentences('A short cue.', language, model))
                model.tokenizer.encode.assert_not_called()

    def test_evidence_backed_languages_still_obey_checkpoint_token_budget(self):
        for language in ('de', 'fr', 'hu', 'ko', 'pl', 'pt', 'tr'):
            with self.subTest(language=language):
                self.assertFalse(should_split_sentences('A short cue.', language, self.model(language=language)))
                self.assertTrue(should_split_sentences('A short cue.', language, self.model(count=128, language=language)))

    def test_hindi_recipe_does_not_change(self):
        model = self.model(language='hi')
        self.assertTrue(should_split_sentences('नमस्ते। स्वागत है।', 'hi', model))
        model.tokenizer.encode.assert_not_called()

    def test_missing_or_invalid_checkpoint_metadata_keeps_established_route(self):
        for model in (SimpleNamespace(), self.model(limit=True), self.model(char_limit=0)):
            with self.subTest(model=model):
                self.assertTrue(should_split_sentences('Hello.', 'de', model))

    def test_malformed_tokens_fail_instead_of_bypassing_the_window(self):
        for tokens in (None, [], [True], [-1], ['token']):
            model = self.model()
            model.tokenizer.encode.return_value = tokens
            with self.subTest(tokens=tokens), self.assertRaisesRegex(ValueError, 'invalid speech tokens'):
                should_split_sentences('Hello.', 'de', model)

    def test_tokenization_failure_is_not_hidden(self):
        model = self.model()
        model.tokenizer.encode.side_effect = RuntimeError('tokenizer failed')
        with self.assertRaisesRegex(RuntimeError, 'tokenizer failed'):
            should_split_sentences('Hello.', 'de', model)
