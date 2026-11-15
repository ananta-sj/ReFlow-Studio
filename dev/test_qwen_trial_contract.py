import copy
import unittest
from dev.evaluate_qwen_scene import validate_response


class QwenTrialContractTests(unittest.TestCase):
    def response(self,rows=None,finish='stop'):
        import json
        rows=rows or [dict(id='a',text='हाँ, उन्होंने कहा था।',uncertain=False,reason='')]
        return {'choices':[{'finish_reason':finish,'message':{'content':json.dumps({'cues':rows})}}]}

    def test_completed_exact_coverage_is_only_a_proposal(self):
        rows=validate_response(self.response(),['a'])
        self.assertEqual(rows[0]['text'],'हाँ, उन्होंने कहा था।')
        self.assertNotIn('approved',rows[0])

    def test_missing_or_duplicated_cues_are_rejected(self):
        with self.assertRaises(ValueError):validate_response(self.response(),['a','b'])
        import json
        response=self.response();row=json.loads(response['choices'][0]['message']['content'])['cues'][0]
        with self.assertRaises(ValueError):validate_response(self.response([row,row]),['a','b'])

    def test_unfinished_generation_is_rejected_even_if_json_is_complete(self):
        with self.assertRaises(ValueError):validate_response(self.response(finish='length'),['a'])

    def test_model_control_text_and_extra_fields_are_rejected(self):
        row=dict(id='a',text='<think>हाँ</think>',uncertain=False,reason='')
        with self.assertRaises(ValueError):validate_response(self.response([row]),['a'])
        row=dict(id='a',text='हाँ।',uncertain=False,reason='',approved=True)
        with self.assertRaises(ValueError):validate_response(self.response([row]),['a'])

    def test_uncertainty_is_preserved_for_review(self):
        row=dict(id='a',text='हाँ।',uncertain=True,reason='Meaning is unclear')
        self.assertTrue(validate_response(self.response([row]),['a'])[0]['uncertain'])


if __name__=='__main__':unittest.main()
