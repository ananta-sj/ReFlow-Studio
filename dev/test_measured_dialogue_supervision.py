"""Measured proposals never turn a model opinion into audio fit or acceptance."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
from core.dialogue_supervision import supervise, validate_saved
from core import cue_review as review
from dev import test_cue_review as fixtures


class MeasuredTests(unittest.TestCase):
    def setUp(self):
        self.take = dict(file='take-'+'a'*32+'.wav', seconds=8, fits=False, sha256='b'*64)
        self.writer = SimpleNamespace(rewrite_dialogue=Mock(return_value=['A shorter report.']))
        self.reviewer = SimpleNamespace(review_dialogue=Mock(return_value=[dict(id='candidate-1',status='preserved',reasons=['Fixture only.'])]))
        self.binding = dict(cue_id='cue',configuration='config',input_revision=1,run_id='a'*32)

    def run_review(self, **kwargs):
        return supervise(SimpleNamespace(),self.writer,self.reviewer,'A complete original report.',
            'A complete original report.',6,target_language='en',measured_take=self.take,review_binding=self.binding,**kwargs)

    def test_measured_route_has_no_fake_prediction_or_acceptance(self):
        report=self.run_review();candidate=report['candidates'][0]
        self.assertIsNone(report['original_predicted_seconds'])
        self.assertIsNone(candidate['predicted_seconds']);self.assertIsNone(candidate['fits'])
        self.assertFalse(candidate['approved']);self.assertFalse(report['auto_rewrite'])
        self.assertEqual(report['writer_requests']+report['reviewer_requests'],2)
        cue=dict(cue_id='cue',text=report['input_text'],source_text=report['source_text'],available_seconds=6,candidate=self.take,dialogue_supervision=report)
        validate_saved(cue,'config')
        for mutate in (lambda c:c['candidate'].update(sha256='c'*64),lambda c:c.update(text='Changed'),
                       lambda c:c['dialogue_supervision']['candidates'][0].update(fits=True),
                       lambda c:c['dialogue_supervision']['candidates'][0].update(predicted_seconds=2)):
            changed=deepcopy(cue);mutate(changed)
            with self.assertRaises(ValueError):validate_saved(changed,'config')

    def test_numeric_and_script_mismatch_are_blocked(self):
        for text in ('There were 43 reports.','यह रिपोर्ट है।'):
            self.writer.rewrite_dialogue.return_value=[text]
            report=supervise(SimpleNamespace(),self.writer,self.reviewer,'There were 42 reports.',
                'There were 42 reports.',6,target_language='en',measured_take=self.take)
            self.assertTrue(report['candidates'][0]['warnings'])
        self.reviewer.review_dialogue.assert_not_called()

    def test_invalid_measured_evidence_stops_before_requests(self):
        for update in (dict(seconds=float('nan')),dict(seconds=5),dict(fits=True),dict(file='../take.wav'),dict(sha256='bad')):
            self.take.update(update)
            with self.assertRaises(ValueError):self.run_review()
            self.setUp()

    def test_language_prompts_are_explicit_and_reject_unknown_pair(self):
        from core.providers.dialogue_chat import DialogueChatProvider
        provider=DialogueChatProvider(dict(model='fixture',endpoint='http://127.0.0.1:1/v1',local=True))
        with patch.object(provider,'_query',return_value={'candidates':[]}) as query:
            provider.rewrite_dialogue(source_language='en',target_language='en')
            self.assertIn('spoken English',query.call_args.args[0])
            with self.assertRaises(ValueError):provider.rewrite_dialogue(target_language='ta')
            self.assertEqual(query.call_count,1)


class MeasuredReviewIntegration(unittest.TestCase):
    setUp = fixtures.CueReviewTests.setUp
    assistance_fixture = fixtures.CueReviewTests.assistance_fixture
    operate = fixtures.CueReviewTests.operate
    def english_fixture(self):
        writer,reviewer,_=self.assistance_fixture()
        writer.rewrite_dialogue.return_value=['A shorter report.']
        saved=self.store.load(self.identifier)
        saved.update(target_lang='source',speech_language='en')
        saved['cues'][0]['text']='A complete original report.'
        saved['cues'][0]['source_text']='A complete original report.'
        # Real audio must overflow the one-second slot, not merely claim to.
        long=self.clip*4;path=self.folder/('take-'+'b'*32+'.wav');long.export(path,format='wav').close()
        saved['cues'][0]['candidate']=dict(file=path.name,seconds=1.6,fits=False,sha256=review.digest(path))
        review.review_contracts.sync(saved['cues'][0])
        revision=saved['revision'];saved['revision']+=1;self.store.save(saved,expected_revision=revision)
        return writer,reviewer,path

    def test_english_assistance_persists_unmeasured_variants_and_invalidates_on_regeneration(self):
        self.english_fixture()
        self.operate('supervise')
        report=self.store.load(self.identifier)['cues'][0]['dialogue_supervision']
        self.assertEqual(report['schema'],'reflow.dialogue-supervision.v2')
        self.assertIsNone(report['candidates'][0]['fits'])
        self.operate('generate')
        self.assertNotIn('dialogue_supervision',self.store.load(self.identifier)['cues'][0])

    def test_false_duration_stops_before_model_request(self):
        writer,reviewer,_=self.english_fixture()
        saved=self.store.load(self.identifier);saved['cues'][0]['candidate']['seconds']=2
        revision=saved['revision'];saved['revision']+=1;self.store.save(saved,expected_revision=revision)
        with self.assertRaisesRegex(ValueError,'duration differs'):self.operate('supervise')
        writer.rewrite_dialogue.assert_not_called();reviewer.review_dialogue.assert_not_called()

    def test_take_changed_during_writer_stops_before_critic_and_publication(self):
        writer,reviewer,path=self.english_fixture()
        before=(self.folder/'review.json').read_bytes()
        def change(**kwargs):
            path.write_bytes(b'changed')
            return ['A shorter report.']
        writer.rewrite_dialogue.side_effect=change
        with self.assertRaisesRegex(ValueError,'Saved audio changed'):self.operate('supervise')
        reviewer.review_dialogue.assert_not_called()
        self.assertEqual((self.folder/'review.json').read_bytes(),before)

    def test_real_bridge_dispatches_explicit_measured_action_in_disposable_session(self):
        import threading
        from bridge.api import PythonBridge
        self.english_fixture()
        bridge=PythonBridge.__new__(PythonBridge);bridge._render_lock=threading.Lock()
        bridge._start_rejection=Mock(return_value=None);bridge._cue_store=Mock(return_value=self.store)
        def dispatch(name,params,template,queue_id):
            self.assertEqual(params['_review_action'],'supervise')
            self.operate('supervise',params['_review_index'])
            return dict(ok=True)
        bridge._start_worker=Mock(side_effect=dispatch)
        saved=self.store.load(self.identifier)
        self.assertTrue(bridge.start_review_action(self.identifier,saved['revision'],'supervise',0)['ok'])
        self.assertIsNone(self.store.load(self.identifier)['cues'][0]['dialogue_supervision']['candidates'][0]['fits'])


if __name__=='__main__':unittest.main()
