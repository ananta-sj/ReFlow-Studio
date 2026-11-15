import json,unittest
from dev.evaluate_qwen35_dialogue import validate

LOG='common_perf_print: eval time = 100.00 ms / 28 runs'

class Qwen35TrialTests(unittest.TestCase):
    def answer(self,**changes):
        return json.dumps(dict(text='मुझे रास्ता नहीं पता।',uncertain=False,**changes),ensure_ascii=False)

    def test_complete_structured_hindi_answer_is_only_a_candidate(self):
        result=validate(self.answer()+' [end of text]',512,LOG)
        self.assertEqual(result['text'],'मुझे रास्ता नहीं पता।')
        self.assertNotIn('accepted',result)

    def test_explicit_abstention_can_be_saved_but_is_not_approval(self):
        result=validate(json.dumps(dict(text='',uncertain=True)),512,LOG)
        self.assertTrue(result['uncertain'])

    def test_empty_answer_extra_fields_and_false_boolean_types_are_rejected(self):
        for data in (dict(text='',uncertain=False),dict(text='मुझे नहीं पता।',uncertain='false'),
                     dict(text='मुझे नहीं पता।',uncertain=False,accepted=True)):
            with self.assertRaises(ValueError):validate(json.dumps(data),512,LOG)

    def test_partial_generation_and_reasoning_or_explanations_do_not_pass(self):
        for raw,log in ((self.answer(),'common_perf_print: eval time = 1 ms / 511 runs'),
                        ('<think>reasoning</think>'+self.answer(),LOG),
                        (self.answer()+' extra explanation',LOG),
                        (self.answer()+' [end of text] hidden extra answer',LOG)):
            with self.assertRaises(ValueError):validate(raw,512,log)

if __name__=='__main__':unittest.main()
