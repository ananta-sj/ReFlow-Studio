"""Exact text grounding, legacy compatibility and saved-review integrity."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from core.dialogue_evidence import PROTOCOL,validate_evidence
from core.dialogue_supervision import supervise,validate_saved
from dev import test_measured_dialogue_supervision as fixtures


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source='Anita did not approve the 42 reports on Monday.'
        self.text="Anita didn't approve 42 reports Monday."
        self.evidence=[dict(source_quote='did not approve',candidate_quote="didn't approve",relation='equivalent')]
        self.writer=SimpleNamespace(rewrite_dialogue=Mock(return_value=[self.text]))
        self.reviewer=SimpleNamespace(review_protocol=PROTOCOL,review_dialogue=Mock(return_value=[dict(
            id='candidate-1',status='preserved',reasons=['The negated approval claim is retained.'],evidence=self.evidence)]))
        self.take=dict(file='take-'+'a'*32+'.wav',seconds=8,fits=False,sha256='b'*64)
        self.binding=dict(cue_id='cue',configuration='config',input_revision=1,run_id='a'*32)

    def run_review(self):
        return supervise(SimpleNamespace(),self.writer,self.reviewer,self.source,self.source,6,
            target_language='en',measured_take=self.take,review_binding=self.binding)

    def test_faithful_paraphrase_has_checked_quotes_but_no_audio_approval(self):
        result=self.run_review();candidate=result['candidates'][0]
        self.assertEqual(result['schema'],'reflow.dialogue-supervision.v4')
        self.assertEqual(candidate['meaning_evidence'],self.evidence)
        self.assertFalse(candidate['approved']);self.assertIsNone(candidate['fits'])
        cue=dict(cue_id='cue',source_text=self.source,text=self.source,available_seconds=6,candidate=self.take,dialogue_supervision=result)
        validate_saved(cue,'config')
        for mutate in (lambda r:r.pop('meaning_review_protocol'),lambda r:r['candidates'][0].pop('meaning_evidence'),
                       lambda r:r['candidates'][0]['meaning_evidence'][0].update(source_quote='rejected'),
                       lambda r:r['candidates'][0].update(meaning_status='changed')):
            changed=deepcopy(cue);mutate(changed['dialogue_supervision'])
            with self.assertRaises(ValueError):validate_saved(changed,'config')

    def test_missing_or_invented_quote_cannot_publish_a_preserved_opinion(self):
        for evidence in (None,[],[dict(source_quote='rejected',candidate_quote="didn't approve",relation='equivalent')],
                         [dict(source_quote='did not approve',candidate_quote='disapproved',relation='equivalent')]):
            self.reviewer.review_dialogue.return_value[0]['evidence']=evidence
            with self.subTest(evidence=evidence),self.assertRaises(ValueError):self.run_review()
        self.assertEqual(self.writer.rewrite_dialogue.call_count,4)

    def test_quotes_from_other_candidate_are_rejected(self):
        self.writer.rewrite_dialogue.return_value=[self.text,'Anita never approved 42 reports Monday.']
        first=self.reviewer.review_dialogue.return_value[0]
        second=deepcopy(first);second['id']='candidate-2'
        self.reviewer.review_dialogue.return_value=[first,second]
        with self.assertRaisesRegex(ValueError,'absent'):self.run_review()

    def test_omission_addition_and_uncertainty_have_distinct_relations(self):
        cases=[('changed',[dict(source_quote='42',candidate_quote='',relation='omitted')]),
               ('changed',[dict(source_quote='',candidate_quote='Monday',relation='added')]),
               ('uncertain',[dict(source_quote='approve',candidate_quote='approve',relation='uncertain')])]
        for status,evidence in cases:validate_evidence(status,evidence,self.source,self.text)
        for status in ('preserved','changed'):
            with self.assertRaises(ValueError):validate_evidence(status,cases[-1][1],self.source,self.text)

    def test_duplicate_blank_overlong_and_mismatched_pairs_rejected(self):
        for evidence in ([self.evidence[0]]*2,[dict(source_quote='',candidate_quote='',relation='equivalent')],
                         [dict(source_quote=' '*2,candidate_quote='approve',relation='changed')],
                         [dict(source_quote='x'*241,candidate_quote='approve',relation='changed')],
                         [dict(source_quote='42',candidate_quote='42',relation='omitted')]):
            with self.subTest(evidence=evidence),self.assertRaises(ValueError):validate_evidence('preserved',evidence,self.source,self.text)

    def test_grounding_does_not_certify_semantic_equivalence(self):
        # Both exact quotes can exist while the relation is a bad model opinion.
        evidence=[dict(source_quote='did not approve',candidate_quote='rejected',relation='equivalent')]
        validate_evidence('preserved',evidence,self.source,'Anita rejected 42 reports Monday.')
        # Human review/never auto-accept is therefore still mandatory.
        self.assertTrue(self.run_review()['human_review_required'])

    def test_partial_words_and_numbers_are_not_fabricated_source_words(self):
        for source,quote in [('recognizable to anyone','any'),('There were 420 reports','42'),('सीता गई।','ता')]:
            with self.subTest(source=source),self.assertRaisesRegex(ValueError,'absent'):
                validate_evidence('preserved',[dict(source_quote=quote,candidate_quote='report',relation='equivalent')],source,'report')
        validate_evidence('preserved',[dict(source_quote='any',candidate_quote='any',relation='equivalent')],'anyone or any person','any person')

    def test_prompt_distinguishes_claims_from_wording_and_keeps_source_separate(self):
        from core.providers.dialogue_chat import DialogueChatProvider
        provider=DialogueChatProvider(dict(model='fixture',endpoint='http://127.0.0.1:1',local=True))
        with patch.object(provider,'_query',return_value={'opinions':[]}) as query:
            provider.review_dialogue(source_text=self.source,candidates=[],target_language='en')
        instruction=query.call_args.args[0]
        self.assertIn('faithful synonyms',instruction);self.assertIn('Copy source_quote exactly',instruction)
        self.assertEqual(provider.review_protocol,PROTOCOL)


class EvidenceIntegration(unittest.TestCase):
    setUp=fixtures.MeasuredReviewIntegration.setUp
    assistance_fixture=fixtures.MeasuredReviewIntegration.assistance_fixture
    operate=fixtures.MeasuredReviewIntegration.operate
    english_fixture=fixtures.MeasuredReviewIntegration.english_fixture

    def test_grounded_review_survives_save_and_regeneration_clears_it(self):
        writer,reviewer,_=self.english_fixture();reviewer.review_protocol=PROTOCOL
        reviewer.review_dialogue.return_value[0]['evidence']=[dict(
            source_quote='report',candidate_quote='report',relation='equivalent')]
        self.operate('supervise')
        saved=self.store.load(self.identifier)['cues'][0]['dialogue_supervision']
        self.assertEqual(saved['schema'],'reflow.dialogue-supervision.v4')
        self.assertEqual(saved['candidates'][0]['meaning_evidence'][0]['source_quote'],'report')
        self.operate('generate')
        self.assertNotIn('dialogue_supervision',self.store.load(self.identifier)['cues'][0])

    def test_bad_evidence_preserves_previous_review_byte_for_byte(self):
        _,reviewer,_=self.english_fixture();reviewer.review_protocol=PROTOCOL
        reviewer.review_dialogue.return_value[0]['evidence']=[dict(source_quote='invented',candidate_quote='report',relation='equivalent')]
        before=(self.folder/'review.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'absent'):self.operate('supervise')
        self.assertEqual((self.folder/'review.json').read_bytes(),before)


if __name__=='__main__':unittest.main()
