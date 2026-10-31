"""Window assessment, bounded proposals and explicit review safeguards."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from core.dialogue_adaptation import assess, propose, validate_options, DialogueReviewRequired
from core.render_context import RenderCancelled


class DialogueTests(unittest.TestCase):
    def provider(self):
        return SimpleNamespace(preserves_native_delivery=True, estimate_duration_seconds=lambda text:len(text)/10)

    def cues(self):
        return [dict(cue_id='one',start=0,end=1,text='x'*20,source_text='Source one'),
                dict(cue_id='two',start=2,end=3,text='x'*40,source_text='Source two'),
                dict(cue_id='three',start=4,end=6,text='short',source_text='Source three')]

    def test_all_conflicts_are_assessed_without_rewriting(self):
        cues=self.cues();before=deepcopy(cues)
        report=assess(self.provider(),cues,['CLONED_USER'])
        self.assertEqual(cues,before)
        self.assertEqual([c['status'] for c in report['cues']],['fits_prediction','needs_review','fits_prediction'])
        self.assertEqual(report['status'],'needs_review')
        self.assertFalse(report['meaning_assessed'])
        self.assertIn('1 of 3',str(DialogueReviewRequired(report)))

    def test_intercue_silence_is_available_without_extending_final_end(self):
        report=assess(self.provider(),self.cues(),['CLONED_USER'])
        self.assertEqual([c['available_seconds'] for c in report['cues']],[2,2,2])

    def test_unsupported_or_mixed_cast_never_guesses(self):
        provider=self.provider();provider.estimate_duration_seconds=Mock(side_effect=AssertionError)
        self.assertEqual(assess(provider,self.cues(),['Actor'])['status'],'not_assessed')
        provider.preserves_native_delivery=False
        self.assertEqual(assess(provider,self.cues(),['CLONED_USER'])['status'],'not_assessed')
        provider.estimate_duration_seconds.assert_not_called()

    def test_invalid_estimates_and_cancellation_propagate(self):
        for value in (0,-1,True,float('nan'),float('inf')):
            with self.subTest(value=value),self.assertRaises(ValueError):
                assess(SimpleNamespace(preserves_native_delivery=True,estimate_duration_seconds=lambda _:value),self.cues(),['CLONED_USER'])
        provider=self.provider();provider.estimate_duration_seconds=Mock(side_effect=RenderCancelled())
        with self.assertRaises(RenderCancelled):assess(provider,self.cues(),['CLONED_USER'])

    def options(self,candidates=None):
        translator=SimpleNamespace(suggest_dialogue=Mock(return_value=candidates or ['short','still much too long for this window','short']))
        result=propose(self.provider(),translator,'Original source','Original translation','Hindi','en',1)
        translator.suggest_dialogue.assert_called_once_with('Original source','Hindi',source_language='en',max_candidates=3)
        return result

    def test_one_request_deduplicates_and_keeps_unapproved_results(self):
        result=self.options()
        self.assertEqual(len(result['candidates']),2)
        self.assertTrue(result['candidates'][0]['fits'])
        self.assertFalse(result['candidates'][1]['fits'])
        self.assertTrue(result['human_review_required'])
        self.assertFalse(result['meaning_assessed'])
        self.assertTrue(all(c['approved'] is False for c in result['candidates']))

    def test_excess_candidates_are_rejected(self):
        with self.assertRaises(ValueError):self.options(['a','b','c','d'])

    def test_number_difference_is_a_warning_not_approval(self):
        result=self.options(['There are 2 choices'])
        self.assertTrue(result['candidates'][0]['warnings'])
        self.assertFalse(result['candidates'][0]['approved'])

    def test_duplicate_raw_translation_does_not_fake_an_alternative(self):
        result=self.options(['Original translation'])
        self.assertEqual(result['status'],'no_distinct_alternative')
        self.assertEqual(result['candidates'],[])

    def test_stale_or_tampered_options_are_rejected(self):
        options=self.options();cue=dict(text='Original translation',source_text='Original source',available_seconds=1,dialogue_options=options)
        validate_options(cue)
        for field,value in [('text','changed'),('available_seconds',2),('source_text','changed')]:
            with self.assertRaises(ValueError):validate_options(dict(cue,**{field:value}))
        bad=deepcopy(cue);bad['dialogue_options']['candidates'][0]['approved']=True
        with self.assertRaises(ValueError):validate_options(bad)


if __name__=='__main__':unittest.main()
