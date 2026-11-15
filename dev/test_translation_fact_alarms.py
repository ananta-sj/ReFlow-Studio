import unittest
from core.dialogue_integrity import require_explicit_facts,DialogueIntegrityReviewRequired

class FactAlarms(unittest.TestCase):
    def test_real_missing_direction_and_changed_family_reference_are_flagged(self):
        with self.assertRaises(DialogueIntegrityReviewRequired):
            require_explicit_facts('He lives far to the north of Paris.','वे पेरिस से बहुत दूर रहते हैं।','en','Hindi')
        with self.assertRaises(DialogueIntegrityReviewRequired):
            require_explicit_facts('He wanted us to go to his father.','उसने चाहा कि हम अपने पिता के पास जाएं।','en','Hindi')

    def test_correct_direction_hinglish_and_singular_reflexive_are_not_blocked(self):
        for text in ('वे पेरिस के उत्तर में रहते हैं।','वे Paris के north में रहते हैं।'):
            self.assertEqual(require_explicit_facts('He lives north of Paris.',text,'en','Hindi'),text)
        require_explicit_facts('He went to his father.','वह अपने पिता के पास गया।','en','Hindi')
        require_explicit_facts('He wanted us to go to his father.','वह चाहते थे कि हम उनके पिता के पास जाएं।','en','Hindi')
        require_explicit_facts('He wanted us to go to his father.','उन्होंने हमें अपने पिता के पास जाने को कहा।','en','Hindi')

    def test_unsupported_language_pairs_are_not_guessed(self):
        self.assertEqual(require_explicit_facts('north of Paris','Unknown','ja','Hindi'),'Unknown')

if __name__=='__main__':unittest.main()
