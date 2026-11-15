import unittest
from dev.completion_evidence import finished_before_cap


class CompletionEvidenceTests(unittest.TestCase):
    def log(self,count):return f'0.42 I common_perf_print: eval time = 100 ms / {count} runs'
    def test_first_token_accounting_cannot_hide_a_token_cap(self):
        self.assertFalse(finished_before_cap(self.log(767),768))
        self.assertFalse(finished_before_cap(self.log(768),768))
    def test_complete_early_generation_is_recognized(self):
        self.assertTrue(finished_before_cap(self.log(34),768))
    def test_prompt_only_or_missing_counters_are_not_completion_evidence(self):
        self.assertFalse(finished_before_cap(self.log(34).replace('eval time','prompt eval time'),768))
        self.assertFalse(finished_before_cap('[end of text]',768))


if __name__=='__main__':unittest.main()
