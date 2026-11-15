import hashlib,json,tempfile,unittest
import threading
from unittest.mock import Mock,patch
from pathlib import Path
from core.batch_review_recovery import payload,verify_source


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.run=self.root/'run_records'/('a'*32);self.run.mkdir(parents=True)
        self.source=self.root/'source.wav';self.source.write_bytes(b'original')
        self.artifact=self.run/'cues.json'
        self.artifact.write_text(json.dumps({'segments':[dict(start=0,end=1,text='Hindi',source_text='Original',cue_id='one')]}),encoding='utf-8')
        self.record=dict(run_id=self.run.name,source=dict(path=str(self.source),bytes=8,sha256=hashlib.sha256(b'original').hexdigest()),
            plan={'parameters':{'target_lang':'hi'}},cue_artifacts=[dict(phase='speech-input',path=str(self.artifact),sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())])
        self.path=self.run/'manifest.json';self.save()

    def tearDown(self):self.temp.cleanup()
    def save(self):self.path.write_text(json.dumps(self.record),encoding='utf-8')

    def test_saved_translation_keeps_original_wording_and_never_imports_acceptance(self):
        result=payload(self.path)
        self.assertEqual(result['cues'][0]['text'],'Original')
        self.assertEqual(result['cues'][0]['recovered_translation'],'Hindi')
        self.assertNotIn('accepted',result['cues'][0])
        verify_source(result,self.source)
        self.source.write_bytes(b'changed!')
        with self.assertRaisesRegex(ValueError,'media changed'):verify_source(result,self.source)

    def test_pretranslation_draft_stays_explicitly_untranslated(self):
        self.record['cue_artifacts'][0]['phase']='source-captions';self.save()
        result=payload(self.path)
        self.assertEqual(result['cues'][0]['text'],'Hindi')
        self.assertIsNone(result['cues'][0]['recovered_translation'])

    def test_rejected_translation_is_not_mistaken_for_ready_target_wording(self):
        content=json.loads(self.artifact.read_text(encoding='utf-8'))
        content['segments'][0]['translation_review']='Meaning changed'
        self.artifact.write_text(json.dumps(content),encoding='utf-8')
        self.record['cue_artifacts'][0]['sha256']=hashlib.sha256(self.artifact.read_bytes()).hexdigest();self.save()
        self.assertIsNone(payload(self.path)['cues'][0]['recovered_translation'])

    def test_changed_artifact_and_path_outside_run_are_rejected(self):
        self.artifact.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'dialogue changed'):payload(self.path)
        self.record['cue_artifacts'][0]['path']=str(self.source);self.save()
        with self.assertRaisesRegex(ValueError,'belong to this run'):payload(self.path)

    def test_marked_song_is_kept_but_cannot_replace_a_dialogue_turn(self):
        evidence=self.run/'captions.json'
        def save_event(start,end):
            evidence.write_text(json.dumps(dict(language='ja',preserved_events=[dict(start=start,end=end,reason='caption_music_without_dialogue')])),encoding='utf-8')
            self.record['quality_reports']=[dict(kind='source-captions',path=str(evidence),sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())]
            self.save()
        save_event(2,3)
        self.assertEqual(payload(self.path)['preserved_events'][0]['start'],2)
        save_event(.2,.8)
        with self.assertRaisesRegex(ValueError,'overlaps saved dialogue'):payload(self.path)

    def test_bridge_recovers_in_memory_run_when_marker_was_unavailable(self):
        from bridge import api
        bridge=api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock=threading.Lock()
        bridge._start_rejection=Mock(return_value=None)
        bridge._start_worker=Mock(return_value={'ok':True})
        bridge._last_run_manifest_path=str(self.path)
        with patch.object(api.config,'OUTPUT_PATH',str(self.root)),patch('core.failed_review_state.recall',return_value=None):
            self.assertTrue(bridge.recover_failed_review()['ok'])
        parameters=bridge._start_worker.call_args.args[1]
        self.assertEqual(parameters['_review_action'],'recover_batch')
        self.assertFalse(parameters['review_video'])
        self.assertTrue(parameters['review_speaker_matching'])

if __name__=='__main__':unittest.main()
