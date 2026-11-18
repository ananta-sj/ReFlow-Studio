"""Review persistence, accepted-take reuse and cancellable publication contracts."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from pydub import AudioSegment
from pydub.generators import Sine
from core import cue_review as review
from core.render_context import RenderContext, bind_job, RenderCancelled
from core.pipeline import ReflowPipeline
from core.providers import resolve as providers
from dev.test_render_queue import api


class CueReviewTests(unittest.TestCase):
    def test_overlong_generation_is_a_review_decision_not_engine_circuit_failure(self):
        from core.speech_generation_budget import SpeechGenerationLimitExceeded
        saved=self.store.load(self.identifier);saved['duration']=4
        saved['cues']=[dict(start=i,end=i+1,available_seconds=1,source_text='Hello',text='नमस्ते',candidate=None,accepted=None) for i in range(4)]
        saved['revision']+=1;self.store.save(saved,expected_revision=1)
        self.pipe._dub_segment.side_effect=SpeechGenerationLimitExceeded('unfinished within budget')
        recognizer=Mock()
        with patch.object(providers,'resolve_stt',return_value=recognizer):self.operate('first_pass',None)
        cues=self.store.load(self.identifier)['cues']
        self.assertTrue(all(c['first_pass']['reason']=='too_long' and not c['accepted'] for c in cues))
        self.assertEqual(self.pipe._dub_segment.call_count,8)
        recognizer.transcribe_takes.assert_not_called()

    def test_one_failed_line_is_saved_for_review_and_does_not_block_next_line(self):
        self.pipe._dub_segment.side_effect=[RuntimeError('temporary inference failure'),RuntimeError('temporary inference failure'),self.clip]
        recognizer=Mock();recognizer.transcribe_takes.return_value=[[{'text':'अलविदा'}]]
        with patch.object(providers,'resolve_stt',return_value=recognizer):self.operate('first_pass',None)
        cues=self.store.load(self.identifier)['cues']
        self.assertEqual(cues[0]['first_pass']['reason'],'generation_failed')
        self.assertIsNone(cues[0]['accepted']);self.assertIsNotNone(cues[1]['accepted'])

    def test_repeated_engine_failure_stops_after_three_saved_lines(self):
        saved=self.store.load(self.identifier);saved['duration']=4
        saved['cues']=[dict(start=i,end=i+1,available_seconds=1,source_text='Hello',text='नमस्ते',candidate=None,accepted=None) for i in range(4)]
        saved['revision']+=1;self.store.save(saved,expected_revision=1)
        self.pipe._dub_segment.side_effect=RuntimeError('engine unavailable')
        with patch.object(providers,'resolve_stt',return_value=Mock()),self.assertRaisesRegex(RuntimeError,'three consecutive'):
            self.operate('first_pass',None)
        saved=self.store.load(self.identifier)
        self.assertTrue(all(c.get('first_pass') for c in saved['cues'][:3]))
        self.assertNotIn('first_pass',saved['cues'][3])
        self.assertEqual(self.pipe._dub_segment.call_count,6)

    def test_cache_preferences_do_not_invalidate_saved_review_takes(self):
        original=review.configuration(self.pipe,self.settings)
        self.settings.all.return_value={'mode':'fixture','auto_cleanup_cache':False}
        self.assertEqual(review.configuration(self.pipe,self.settings),original)
        self.settings.all.return_value={'mode':'fixture','auto_cleanup_cache':True}
        self.assertEqual(review.configuration(self.pipe,self.settings),original)

    def test_recovery_prepares_saved_text_without_recognition_or_translation(self):
        source=self.root/'recovery.wav'
        self.clip.export(source,format='wav').close()
        recovery=dict(run_id='b'*32,source=dict(bytes=source.stat().st_size,sha256=review.digest(source)),
            cues=[dict(start=0,end=.4,text='Original',recovered_translation=None)],preserved_events=[])
        self.pipe._transcribe_source=Mock(side_effect=AssertionError('must reuse recognition'))
        self.pipe._resolve_translation_and_filter=Mock(side_effect=AssertionError('must reuse wording'))
        self.pipe._check_speech_routes=Mock()
        params=dict(target_lang='hi',source_language='en',keep_background=False,cast_list=['CLONED_USER'])
        job=RenderContext(self.root/'temp')
        try:
            with bind_job(job),patch.object(providers,'resolve_stt',side_effect=AssertionError('must not load recognizer')):
                path=review.prepare(self.store,self.pipe,str(source),params,self.settings,self.progress,recovery=recovery)
            saved=self.store.load(Path(path).parent.name)
            self.assertEqual(saved['recovered_from_run'],'b'*32)
            self.assertTrue(saved['cues'][0]['translation_pending'])
            self.assertIsNone(saved['cues'][0]['accepted'])
            self.pipe._transcribe_source.assert_not_called()
        finally:job.cleanup()

    def test_recovered_untranslated_line_cannot_be_spoken_or_accepted(self):
        saved=self.store.load(self.identifier)
        saved['cues'][0]['translation_pending']=True
        saved['revision']+=1
        self.store.save(saved,expected_revision=1)
        with self.assertRaisesRegex(ValueError,'Translate this recovered'):
            self.operate('generate',0)
        with self.assertRaisesRegex(ValueError,'Translate this recovered'):
            self.store.accept(self.identifier,2,0)
        saved=self.store.edit(self.identifier,2,0,'Corrected original',saved['cues'][0]['text'])
        self.assertTrue(saved['cues'][0]['translation_pending'])
        saved=self.store.edit(self.identifier,saved['revision'],0,'Corrected original','नई पंक्ति')
        self.assertNotIn('translation_pending',saved['cues'][0])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.store = review.ReviewStore(self.root / 'outputs')
        self.identifier = 'a' * 32
        self.folder = self.store.folder(self.identifier)
        self.folder.mkdir()
        self.clip = Sine(440).to_audio_segment(duration=400).apply_gain(-12)
        self.clip.export(self.folder / 'reference.wav', format='wav').close()
        self.pipe = ReflowPipeline.__new__(ReflowPipeline)
        self.pipe.registry = Mock()
        self.pipe.registry.list.return_value = []
        self.pipe.registry.get_active.return_value = None
        self.pipe.output_dir = str(self.root / 'outputs')
        self.pipe._dub_segment = Mock(return_value=self.clip)
        self.settings = Mock()
        self.settings.all.return_value = {'mode': 'fixture'}
        self.manifest = dict(version=1, id=self.identifier, revision=1, name='source.wav', created_at=1,
            duration=2, target_lang='hi', speech_language='hi', source_language='en', actor='CLONED_USER',
            device='cpu', configuration=review.configuration(self.pipe, self.settings),
            assets={'reference.wav': review.digest(self.folder / 'reference.wav')},
            cues=[dict(start=0, end=1, available_seconds=1, source_text='Hello', text='नमस्ते', candidate=None, accepted=None),
                  dict(start=1, end=2, available_seconds=1, source_text='Bye', text='अलविदा', candidate=None, accepted=None)])
        self.store.save(self.manifest)
        self.stack.enter_context(patch.object(providers, 'resolve_tts', return_value=Mock()))
        self.progress = Mock()

    def operate(self, action, index=0):
        revision = self.store.load(self.identifier)['revision']
        job = RenderContext(self.root / 'temp')
        try:
            with bind_job(job):
                return review.operate(self.store, self.pipe, self.identifier, revision,
                                      action, index, self.settings, self.progress)
        finally:
            job.cleanup()

    def accept(self, index=0):
        revision = self.store.load(self.identifier)['revision']
        return self.store.accept(self.identifier, revision, index)

    def test_first_pass_accepts_matching_words_retries_uncertain_and_resumes(self):
        def words(text):
            return [{'start': 0, 'end': .3, 'text': text}]

        recognizer = Mock()
        recognizer.transcribe_takes.side_effect = [
            [words('नमस्ते।')], [words('अलग शब्द')], [words('कुछ और')], [words('अलविदा')]]
        self.pipe._dub_segment.side_effect = [self.clip, self.clip, self.clip.apply_gain(-2), self.clip]
        with patch.object(providers, 'resolve_stt', return_value=recognizer):
            self.operate('first_pass', None)
            first, second = self.store.load(self.identifier)['cues']
            self.assertEqual(first['first_pass']['attempts'], 1)
            self.assertEqual(first['accepted'], first['candidate'])
            self.assertEqual(second['first_pass']['reason'], 'words_uncertain')
            self.assertEqual(second['first_pass']['attempts'], 2)
            self.assertIsNone(second['accepted'])
            self.assertTrue(second['candidate']['fits'])
            self.operate('first_pass', None)
        after_first, after_second = self.store.load(self.identifier)['cues']
        self.assertEqual(first['accepted'], after_first['accepted'])
        self.assertEqual(after_second['first_pass']['status'], 'passed')
        self.assertEqual([call.args[0] for call in self.pipe._dub_segment.call_args_list], [0, 1, 1, 1])
        self.assertTrue(all(call.kwargs['preserve_delivery'] for call in self.pipe._dub_segment.call_args_list))
        events = [call.args for call in self.progress.call_args_list]
        first_run = events[:next(index for index, event in enumerate(events) if event[0] == 100)+1]
        percentages = [percent for percent, _ in first_run]
        self.assertEqual(percentages, sorted(percentages))
        second_line = next(percent for percent, status in first_run if 'Generating line 2/2' in status)
        self.assertGreater(second_line, 0)

    def test_first_pass_does_not_approve_audio_that_only_fits_by_using_the_pause(self):
        saved = self.store.load(self.identifier)
        saved['cues'][0]['end'] = .2
        saved['revision'] += 1
        self.store.save(saved, expected_revision=1)
        recognizer = Mock()
        recognizer.transcribe_takes.return_value = [[{'start': 0, 'end': .3, 'text': 'अलविदा'}]]
        with patch.object(providers, 'resolve_stt', return_value=recognizer):
            self.operate('first_pass', None)
        first, second = self.store.load(self.identifier)['cues']
        self.assertEqual(first['first_pass']['reason'], 'too_long')
        self.assertTrue(first['candidate']['fits'])  # The user can still choose to use the pause.
        self.assertIsNone(first['accepted'])
        self.assertIsNotNone(second['accepted'])
        self.assertEqual(recognizer.transcribe_takes.call_count, 1)

    def test_first_pass_aligns_source_onset_and_keeps_verified_words_when_a_retry_is_worse(self):
        saved = self.store.load(self.identifier)
        lead = AudioSegment.silent(200, frame_rate=self.clip.frame_rate)
        first_source = lead + self.clip + lead + lead
        second_source = self.clip + lead + self.clip
        vocals = self.folder / 'vocals.wav'
        (first_source + second_source).export(vocals, format='wav').close()
        saved['assets']['vocals.wav'] = review.digest(vocals)
        saved['revision'] += 1
        self.store.save(saved, expected_revision=1)
        recognizer = Mock()
        recognizer.transcribe_takes.side_effect = [
            [[{'text': 'नमस्ते'}]], [[{'text': 'अलविदा'}]], [[{'text': 'गलत'}]]]
        self.pipe._dub_segment.side_effect = [self.clip, self.clip, self.clip.apply_gain(-8)]
        with patch.object(providers, 'resolve_stt', return_value=recognizer):
            self.operate('first_pass', None)
        first, second = self.store.load(self.identifier)['cues']
        self.assertIsNotNone(first['accepted'])
        with (self.folder / first['accepted']['file']).open('rb') as stream:
            take = AudioSegment.from_wav(stream)
        self.assertEqual(take[:180].max, 0)
        self.assertGreater(take[230:350].max, 0)
        self.assertEqual(second['first_pass']['reason'], 'delivery_uncertain')
        self.assertEqual(second['first_pass']['heard'], 'अलविदा')
        self.assertLess(second['first_pass']['performance']['end_delta_ms'], -500)
        self.assertIsNone(second['accepted'])

    def test_first_pass_keeps_each_completed_line_when_cancelled(self):
        saved = self.store.load(self.identifier)
        saved['duration'] = 13
        saved['cues'] = [dict(start=i, end=i+1, available_seconds=1, source_text='Hello',
                              text='नमस्ते', candidate=None, accepted=None) for i in range(13)]
        saved['revision'] += 1
        self.store.save(saved, expected_revision=1)
        recognizer = Mock()
        recognizer.transcribe_takes.return_value = [[{'start': 0, 'end': .3, 'text': 'नमस्ते'}]]
        self.pipe._dub_segment.side_effect = [self.clip] * 2 + [RenderCancelled('cancelled')]
        with patch.object(providers, 'resolve_stt', return_value=recognizer):
            with self.assertRaises(RenderCancelled):
                self.operate('first_pass', None)
        saved = self.store.load(self.identifier)
        self.assertEqual(saved['revision'], 4)
        self.assertTrue(all(cue['accepted'] for cue in saved['cues'][:2]))
        self.assertIsNone(saved['cues'][2]['accepted'])

    def test_character_review_matches_clear_lines_and_uses_distinct_references(self):
        import numpy as np
        from core.character_review import set_speaker

        manifest = self.store.load(self.identifier)
        manifest.update(duration=6, speaker_matching=True, speaker_dirty=True, speaker_references={})
        manifest['cues'] = [dict(start=i*1.5, end=(i+1)*1.5, available_seconds=1.5,
                                source_text='Hello', text='नमस्ते', candidate=None, accepted=None)
                            for i in range(4)]
        audio = sum((Sine(hz).to_audio_segment(duration=1500).apply_gain(-10)
                     for hz in (440, 550, 450, 495)), self.clip[:0])
        vocals = self.folder/'vocals.wav'
        audio.export(vocals, format='wav').close()
        manifest['assets']['vocals.wav'] = review.digest(vocals)
        manifest['revision'] += 1
        self.store.save(manifest, expected_revision=1)
        set_speaker(self.store, self.identifier, 2, 0, 'Perrine')
        set_speaker(self.store, self.identifier, 3, 1, 'Marie')
        with self.assertRaisesRegex(ValueError, 'Match the characters'):
            self.operate('first_pass', None)
        encode = Mock(side_effect=[np.array(vector) for vector in
                                  ([1., 0.], [0., 1.], [.95, .1], [.7, .7])])
        with patch('core.speaker_matching.load_encoder', return_value=encode):
            self.operate('match_speakers', None)
        saved = self.store.load(self.identifier)
        self.assertEqual([cue.get('speaker') for cue in saved['cues']], ['Perrine', 'Marie', 'Perrine', None])
        self.assertEqual(saved['cues'][3]['speaker_match'], 'ambiguous')
        recognizer = Mock()
        self.pipe._dub_segment.return_value = Sine(440).to_audio_segment(duration=1400).apply_gain(-12)
        recognizer.transcribe_takes.return_value = [[{'start': 0, 'end': .9, 'text': 'नमस्ते'}]]
        with patch.object(providers, 'resolve_stt', return_value=recognizer):
            self.operate('first_pass', None)
        calls = self.pipe._dub_segment.call_args_list
        self.assertEqual([call.args[0] for call in calls], [0, 1, 2])
        self.assertEqual(calls[0].args[6], calls[2].args[6])
        self.assertNotEqual(calls[0].args[6], calls[1].args[6])
        self.operate('generate', 1)
        self.assertEqual(self.pipe._dub_segment.call_args.args[6], calls[1].args[6])
        saved = self.store.load(self.identifier)
        self.assertIsNone(saved['cues'][3]['accepted'])
        initial_reference = saved['speaker_references']['Perrine']
        initial_take = saved['cues'][0]['accepted']
        set_speaker(self.store, self.identifier, saved['revision'], 2, 'Perrine')
        encode = Mock(side_effect=[np.array(vector) for vector in
                                  ([1., 0.], [0., 1.], [.95, .1], [.7, .7])])
        with patch('core.speaker_matching.load_encoder', return_value=encode):
            self.operate('match_speakers', None)
        saved = self.store.load(self.identifier)
        self.assertEqual(saved['speaker_references']['Perrine'], initial_reference)
        self.assertEqual(saved['cues'][0]['accepted'], initial_take)
        set_speaker(self.store, self.identifier, saved['revision'], 2, 'marie')
        corrected = self.store.load(self.identifier)
        self.assertEqual(corrected['cues'][2]['speaker'], 'Marie')
        self.assertIsNone(corrected['cues'][2]['accepted'])
        self.assertIsNotNone(corrected['cues'][0]['accepted'])

    def test_character_match_flags_a_cue_with_a_speaker_change(self):
        import numpy as np
        from core.speaker_matching import match_excerpt

        clip = Sine(440).to_audio_segment(duration=3000).apply_gain(-12)
        refs = {'first': [np.array([1., 0.])], 'second': [np.array([0., 1.])]}
        encode = Mock(side_effect=[np.array(x) for x in ([1., 0.], [1., 0.], [0., 1.])])
        self.assertEqual(match_excerpt(clip, encode, refs), (None, 'mixed_speakers'))

    def test_legacy_identity_migration_does_not_rewrite_saved_record(self):
        path = self.folder / 'review.json'
        legacy = json.loads(path.read_text(encoding='utf-8'))
        for cue in legacy['cues']:
            cue.pop('cue_id', None)
            cue.pop('cue_contract', None)
        path.write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')
        before = path.read_bytes()
        first = self.store.load(self.identifier)
        second = self.store.public(self.identifier)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(first['cues'][0]['cue_id'], second['cues'][0]['cue_id'])
        self.assertFalse(first['cues'][0]['cue_contract']['original_source_known'])
        self.assertIsNone(first['cues'][0]['cue_contract']['translated_text'])

    def test_review_edit_preserves_original_source_identity(self):
        before = self.store.load(self.identifier)['cues'][0]
        self.store.edit(self.identifier, 1, 0, 'Corrected source', 'Corrected target')
        after = self.store.load(self.identifier)['cues'][0]
        self.assertEqual(after['cue_id'], before['cue_id'])
        self.assertEqual(after['cue_contract']['source_text'], 'Hello')
        self.assertEqual(after['cue_contract']['corrected_source_text'], 'Corrected source')
        self.assertEqual(after['cue_contract']['source_start'], 0)

    def test_wording_proposals_preserve_text_and_takes_then_edit_invalidates_them(self):
        from types import SimpleNamespace
        translator = SimpleNamespace(suggest_dialogue=Mock(return_value=['छोटा वाक्य']))
        tts = SimpleNamespace(preserves_native_delivery=True, estimate_duration_seconds=lambda _: .8)
        before = self.store.load(self.identifier)['cues'][0]
        with patch.object(providers, 'uses_exact_reference', return_value=True), patch.object(providers, 'confirmed_reference'), \
                patch.object(providers, 'resolve_tts', return_value=tts), patch.object(providers, 'resolve_translation', return_value=translator):
            self.operate('adapt')
        saved = self.store.load(self.identifier)
        cue = saved['cues'][0]
        self.assertEqual(cue['text'], before['text'])
        self.assertEqual(cue['cue_contract'], before['cue_contract'])
        self.assertEqual(cue['accepted'], before['accepted'])
        self.assertFalse(cue['dialogue_options']['candidates'][0]['approved'])
        self.store.edit(self.identifier, saved['revision'], 0, cue['source_text'], 'मानव की चुनी हुई पंक्ति')
        self.assertNotIn('dialogue_options', self.store.load(self.identifier)['cues'][0])

    def test_wording_proposals_fail_without_mutating_or_starting_speech(self):
        before = (self.folder / 'review.json').read_bytes()
        with patch.object(providers, 'uses_exact_reference', return_value=True), patch.object(providers, 'confirmed_reference'), \
                patch.object(providers, 'resolve_translation', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError): self.operate('adapt')
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)
        self.pipe._dub_segment.assert_not_called()

    def assistance_fixture(self, mock_connections=True):
        from types import SimpleNamespace
        from core.pipeline_contracts import RegistrySnapshot
        from dev.test_dialogue_connections import entry
        self.pipe.registry=RegistrySnapshot({'entries':[entry(),entry('reviewer')],'active':{}})
        self.settings.all.return_value=dict(dialogue_mode='local',dialogue_writer_id='writer',dialogue_reviewer_id='reviewer')
        self.clip.export(self.folder/'source.wav',format='wav').close()
        manifest=self.store.load(self.identifier)
        manifest['assets']['source.wav']=review.digest(self.folder/'source.wav')
        manifest['configuration']=review.configuration(self.pipe,self.settings)
        cue=manifest['cues'][0];cue['text']='यह मूल अनुवाद बहुत लंबा है और इसका अर्थ रखना चाहिए।'
        review.review_contracts.sync(cue)
        previous=manifest['revision'];manifest['revision']+=1
        self.store.save(manifest,expected_revision=previous)
        writer=SimpleNamespace(engine_id='fixture-writer',service_model='fixture-model',
            rewrite_dialogue=Mock(return_value=['यह ठीक है।']))
        reviewer=SimpleNamespace(engine_id='fixture-reviewer',service_model='fixture-model',
            review_dialogue=Mock(return_value=[dict(id='candidate-1',status='preserved',reasons=['Fixture opinion only.'])]))
        tts=SimpleNamespace(preserves_native_delivery=True,estimate_duration_seconds=lambda text:2 if len(text)>20 else .8)
        self.stack.enter_context(patch.object(providers,'uses_exact_reference',return_value=True))
        self.stack.enter_context(patch.object(providers,'confirmed_reference'))
        self.stack.enter_context(patch.object(providers,'resolve_tts',return_value=tts))
        if mock_connections:
            self.stack.enter_context(patch('core.dialogue_connections.resolve',return_value=(writer,reviewer)))
        return writer,reviewer,tts

    def test_assisted_review_preserves_text_and_accepted_take_with_durable_evidence(self):
        writer,reviewer,_=self.assistance_fixture()
        self.operate('generate');self.accept()
        before=self.store.load(self.identifier)['cues'][0]
        self.pipe._dub_segment.reset_mock()
        self.operate('supervise')
        saved=self.store.load(self.identifier);cue=saved['cues'][0]
        self.assertEqual(cue['text'],before['text'])
        self.assertEqual(cue['cue_contract'],before['cue_contract'])
        self.assertEqual(cue['accepted'],before['accepted'])
        self.assertEqual(cue['candidate'],before['candidate'])
        self.assertFalse(cue['dialogue_supervision']['candidates'][0]['approved'])
        self.assertEqual(cue['dialogue_supervision']['review_binding']['cue_id'],cue['cue_id'])
        record=json.loads(next((self.root/'outputs/run_records').glob('*/manifest.json')).read_text(encoding='utf-8'))
        self.assertEqual(record['status'],'needs_review')
        self.assertFalse(record['review_action']['generates_speech'])
        artifact=record['quality_reports'][0]
        self.assertEqual(json.loads(Path(artifact['path']).read_text(encoding='utf-8')),cue['dialogue_supervision'])
        self.assertEqual(record['output']['sha256'],review.digest(self.folder/'review.json'))
        writer.rewrite_dialogue.assert_called_once();reviewer.review_dialogue.assert_called_once()
        self.pipe._dub_segment.assert_not_called()

    def test_assistance_reviewer_failure_keeps_original_review_and_records_failure(self):
        writer,reviewer,_=self.assistance_fixture()
        before=(self.folder/'review.json').read_bytes()
        reviewer.review_dialogue.side_effect=RuntimeError('review service unavailable')
        with self.assertRaisesRegex(RuntimeError,'review service unavailable'):self.operate('supervise')
        self.assertEqual((self.folder/'review.json').read_bytes(),before)
        record=json.loads(next((self.root/'outputs/run_records').glob('*/manifest.json')).read_text(encoding='utf-8'))
        self.assertEqual(record['status'],'failed')
        self.assertEqual([o['status'] for o in record['operations']],['completed','failed'])
        self.pipe._dub_segment.assert_not_called()

    def test_assistance_config_revocation_stops_before_reviewer(self):
        writer,reviewer,_=self.assistance_fixture()
        before=(self.folder/'review.json').read_bytes()
        def rewrite(**kwargs):
            self.settings.all.return_value=dict(self.settings.all.return_value,dialogue_mode='off')
            return ['यह ठीक है।']
        writer.rewrite_dialogue.side_effect=rewrite
        with self.assertRaisesRegex(ValueError,'consent changed'):self.operate('supervise')
        reviewer.review_dialogue.assert_not_called()
        self.assertEqual((self.folder/'review.json').read_bytes(),before)

    def test_assistance_revision_race_preserves_concurrent_edit(self):
        writer,reviewer,_=self.assistance_fixture()
        def rewrite(**kwargs):
            saved=self.store.load(self.identifier)
            self.store.edit(self.identifier,saved['revision'],0,'Human corrected source','मानव की नई पंक्ति')
            return ['यह ठीक है।']
        writer.rewrite_dialogue.side_effect=rewrite
        with self.assertRaises(ValueError):self.operate('supervise')
        reviewer.review_dialogue.assert_not_called()
        saved=self.store.load(self.identifier)
        self.assertEqual(saved['cues'][0]['text'],'मानव की नई पंक्ति')
        self.assertNotIn('dialogue_supervision',saved['cues'][0])

    def test_assistance_modified_audio_stops_before_requests(self):
        writer,reviewer,_=self.assistance_fixture()
        (self.folder/'source.wav').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'audio changed'):self.operate('supervise')
        writer.rewrite_dialogue.assert_not_called();reviewer.review_dialogue.assert_not_called()

    def test_assistance_fitting_original_saves_zero_query_report(self):
        writer,reviewer,tts=self.assistance_fixture()
        tts.estimate_duration_seconds=lambda _: .8
        self.operate('supervise')
        report=self.store.load(self.identifier)['cues'][0]['dialogue_supervision']
        self.assertEqual(report['outcome'],'original_fits_prediction')
        writer.rewrite_dialogue.assert_not_called();reviewer.review_dialogue.assert_not_called()
        self.pipe._dub_segment.assert_not_called()

    def test_actual_http_assistance_publishes_saved_review_without_inference(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from core.pipeline_contracts import RegistrySnapshot
        from dev.test_dialogue_connections import entry
        self.assistance_fixture(mock_connections=False)
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                payload=json.loads(body['messages'][1]['content'])
                result=({'candidates':['यह ठीक है।']} if 'max_candidates' in payload else
                    {'opinions':[dict(id=c['id'],status='preserved',reasons=['Fixture opinion only.'],
                        evidence=[dict(source_quote=payload['source_text'],candidate_quote=c['text'],relation='equivalent')]) for c in payload['candidates']]})
                raw=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            self.pipe.registry=RegistrySnapshot({'entries':[entry(endpoint=url),entry('reviewer',endpoint=url)],'active':{}})
            manifest=self.store.load(self.identifier);revision=manifest['revision']
            manifest.update(configuration=review.configuration(self.pipe,self.settings),revision=revision+1)
            self.store.save(manifest,expected_revision=revision)
            original=manifest['cues'][0]['text']
            self.operate('supervise')
            saved=self.store.load(self.identifier)
            self.assertEqual(len(requests),2)
            self.assertEqual(saved['cues'][0]['text'],original)
            self.assertFalse(saved['cues'][0]['dialogue_supervision']['candidates'][0]['approved'])
            self.assertEqual(saved['cues'][0]['dialogue_supervision']['engines']['writer']['service_endpoint'],url)
            self.pipe._dub_segment.assert_not_called()
        finally:
            server.shutdown();server.server_close();thread.join(2)

    def test_assistance_source_or_window_edit_invalidates_evidence(self):
        self.assistance_fixture();self.operate('supervise')
        saved=self.store.load(self.identifier)
        self.store.edit(self.identifier,saved['revision'],0,'Corrected source',saved['cues'][0]['text'])
        self.assertNotIn('dialogue_supervision',self.store.load(self.identifier)['cues'][0])

    def test_failed_new_assistance_preserves_previous_report(self):
        writer,_,_=self.assistance_fixture();self.operate('supervise')
        before=(self.folder/'review.json').read_bytes()
        writer.rewrite_dialogue.side_effect=RuntimeError('writer unavailable')
        with self.assertRaises(RuntimeError):self.operate('supervise')
        self.assertEqual((self.folder/'review.json').read_bytes(),before)

    def test_saved_assistance_rejects_tampered_bindings_status_budget_and_approval(self):
        from copy import deepcopy
        self.assistance_fixture();self.operate('supervise')
        saved=self.store.load(self.identifier)
        for mutate in (lambda r:r.update(source_text='Changed'),lambda r:r.update(writer_requests=2),
                       lambda r:r['review_binding'].update(cue_id='wrong'),
                       lambda r:r['candidates'][0].update(approved=True),
                       lambda r:r['candidates'][0].update(meaning_status='uncertain'),
                       lambda r:r['candidates'][0].update(predicted_seconds=5)):
            value=deepcopy(saved);mutate(value['cues'][0]['dialogue_supervision'])
            with self.assertRaises(ValueError):review.validate_manifest(value)

    def test_accepted_observations_estimate_without_constructing_a_speech_engine(self):
        saved = self.store.load(self.identifier)
        saved['duration'] = 4
        saved['cues'] = [dict(start=i, end=i+1, available_seconds=1, source_text='Hello',
            text='नमस्ते' if i < 3 else 'नमस्ते नमस्ते', candidate=None, accepted=None) for i in range(4)]
        saved['revision'] += 1
        self.store.save(saved, expected_revision=1)
        def generate(*args, **kwargs):
            kwargs['timing_observation']['seconds'] = .75
            return self.clip
        self.pipe._dub_segment.side_effect = generate
        for index in range(3):
            self.operate('generate', index)
            current = self.store.load(self.identifier)
            self.store.accept(self.identifier, current['revision'], index)
        current = self.store.load(self.identifier)
        before = (self.folder / 'review.json').read_bytes()
        with patch.object(providers, 'uses_exact_reference', return_value=False), \
                patch.object(providers, 'resolve_tts') as resolver:
            result = review.estimate_timing(self.store, self.pipe, self.identifier, current['revision'], 3, self.settings)
            self.assertEqual(result['basis'], 'observed_natural_takes')
            self.assertEqual(result['sample_count'], 3)
            self.assertAlmostEqual(result['estimated_seconds'], 1.5)
            self.assertFalse(result['fits'])
            resolver.assert_not_called()
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)
        # An unaccepted replacement must not discard calibration for the accepted take.
        self.pipe._dub_segment.side_effect = lambda *a, **kw: (
            kw['timing_observation'].update(seconds=.95) or self.clip.apply_gain(-2))
        self.operate('generate', 0)
        current = self.store.load(self.identifier)
        with patch.object(providers, 'uses_exact_reference', return_value=False):
            result = review.estimate_timing(self.store, self.pipe, self.identifier, current['revision'], 3, self.settings)
            self.assertTrue(result['supported'])
            self.assertEqual(result['sample_count'], 3)
            self.assertAlmostEqual(result['estimated_seconds'], 1.5)
        current['cues'][0]['accepted_timing_sample']['reference_sha256'] = 'b'*64
        current['revision'] += 1
        self.store.save(current, expected_revision=current['revision']-1)
        with patch.object(providers, 'uses_exact_reference', return_value=False):
            result = review.estimate_timing(self.store, self.pipe, self.identifier, current['revision'], 3, self.settings)
            self.assertFalse(result['supported'])

    def test_observed_timing_requires_three_valid_natural_samples(self):
        from core.speech_timing import estimate_from_samples
        samples = [{'text': 'hello there', 'seconds': 2.0},
                   {'text': 'hello again', 'seconds': 2.0},
                   {'text': 'world hello', 'seconds': 2.0}]
        self.assertIsNone(estimate_from_samples('hello there', samples[:2]))
        result = estimate_from_samples('hello there', samples)
        self.assertAlmostEqual(result['estimated_seconds'], 2.0)
        self.assertEqual(result['sample_count'], 3)
        self.assertIsNone(estimate_from_samples('hello', [{'text': 'hello', 'seconds': float('nan')}]*3))

    def test_invalid_saved_timing_observation_is_rejected(self):
        saved = self.store.load(self.identifier)
        saved['cues'][0]['timing_sample'] = dict(text='Hello', seconds=float('inf'),
            take_sha256='a'*64, reference_sha256='b'*64)
        with self.assertRaisesRegex(ValueError, 'timing observation'):
            review.validate_manifest(saved)

    def test_generated_take_records_natural_timing_observation(self):
        def generate(*args, **kwargs):
            kwargs['timing_observation']['seconds'] = .75
            return self.clip
        self.pipe._dub_segment.side_effect = generate
        self.operate('generate', 0)
        cue = self.store.load(self.identifier)['cues'][0]
        self.assertEqual(cue['timing_sample']['seconds'], .75)
        self.assertEqual(cue['timing_sample']['text'], cue['text'])

    def test_timing_estimate_is_read_only_and_does_not_generate_speech(self):
        before = (self.folder / 'review.json').read_bytes()
        provider = Mock()
        provider.estimate_duration_seconds.return_value = 1.2
        with patch.object(providers, 'uses_exact_reference', return_value=True), \
                patch.object(providers, 'confirmed_reference') as reference_check, \
                patch.object(providers, 'resolve_tts', return_value=provider):
            result = review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)
            reference_check.assert_called_once_with(self.pipe.registry, str(self.folder / 'reference.wav'))
        self.assertFalse(result['fits'])
        self.assertEqual(result['available_seconds'], 1)
        self.assertEqual(result['estimated_seconds'], 1.2)
        provider.synthesize.assert_not_called()
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)

    def test_timing_estimate_fits_and_rejects_invalid_estimates(self):
        provider = Mock()
        with patch.object(providers, 'uses_exact_reference', return_value=True), \
                patch.object(providers, 'confirmed_reference'), \
                patch.object(providers, 'resolve_tts', return_value=provider):
            provider.estimate_duration_seconds.return_value = .9
            self.assertTrue(review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)['fits'])
            for invalid in (True, 0, -1, float('nan'), float('inf'), '1'):
                provider.estimate_duration_seconds.return_value = invalid
                with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'invalid speech duration'):
                    review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)

    def test_unsupported_timing_estimate_never_constructs_other_engines(self):
        with patch.object(providers, 'uses_exact_reference', return_value=False), \
                patch.object(providers, 'resolve_tts') as resolver:
            result = review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)
            self.assertFalse(result['supported'])
            resolver.assert_not_called()

    def test_timing_estimate_rejects_changed_settings_reference_and_revision(self):
        self.settings.all.return_value = {'mode': 'changed'}
        with self.assertRaisesRegex(ValueError, 'settings changed'):
            review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)
        self.settings.all.return_value = {'mode': 'fixture'}
        self.store.edit(self.identifier, 1, 0, 'Hello', 'नमस्कार')
        with self.assertRaises(ValueError):
            review.estimate_timing(self.store, self.pipe, self.identifier, 1, 0, self.settings)
        (self.folder / 'reference.wav').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'reference audio changed'):
            review.estimate_timing(self.store, self.pipe, self.identifier, 2, 0, self.settings)

    def test_generate_accept_reopen_and_render_reuses_exact_takes(self):
        for index in range(2):
            self.operate('generate', index)
            self.accept(index)
        self.pipe._dub_segment.reset_mock()
        output = self.operate('render')
        self.pipe._dub_segment.assert_not_called()
        from core.audio_utils import load_playable_audio
        audio = load_playable_audio(output)
        self.assertEqual(len(audio), 2000)
        self.assertEqual(audio[:400].set_frame_rate(self.clip.frame_rate).set_channels(1).raw_data, self.clip.raw_data)
        reopened = review.ReviewStore(self.root / 'outputs').public(self.identifier)
        self.assertTrue(all(cue['accepted']['fits'] for cue in reopened['cues']))
        self.assertNotIn('file', reopened['cues'][0]['accepted'])
        self.assertTrue(self.store.audio(self.identifier, 0, True).startswith('data:audio/wav;base64,'))

    def video_review(self):
        from core.pipeline import _run_ffmpeg
        tools = Path(__file__).resolve().parents[1]/'ffmpeg/bin'
        self.stack.enter_context(patch.dict(os.environ, {'PATH':str(tools)+os.pathsep+os.environ.get('PATH','')}))
        source = self.folder/'source-video.mp4'
        _run_ffmpeg(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=64x64:r=10','-t','2',str(source)])
        value = self.store.load(self.identifier)
        old = value['revision']
        value.update(video_asset=source.name,revision=old+1)
        value['assets'][source.name] = review.digest(source)
        self.store.save(value,expected_revision=old)
        for index in range(2):
            self.operate('generate',index); self.accept(index)
        return source

    def test_reviewed_video_has_hindi_subtitles_and_preserves_timeline(self):
        from core.render_context import run_process
        self.video_review()
        self.pipe._dub_segment.reset_mock()
        output = self.operate('render')
        self.pipe._dub_segment.assert_not_called()
        result = run_process(['ffprobe','-v','error','-show_streams','-of','json',output],capture_output=True,check=True)
        streams = json.loads(result.stdout)['streams']
        self.assertEqual({s['codec_type'] for s in streams},{'video','audio','subtitle'})
        self.assertEqual(next(s for s in streams if s['codec_type']=='subtitle')['tags']['language'],'hin')
        self.assertLess(abs(self.pipe.get_duration(output)-2),.15)
        self.assertEqual(self.store.public(self.identifier)['output_kind'],'video')

    def test_changed_video_cannot_publish_output_or_change_accepted_takes(self):
        source = self.video_review()
        before = self.store.load(self.identifier)
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source video changed'):
            self.operate('render')
        self.assertEqual(self.store.load(self.identifier),before)
        self.assertFalse(list(Path(self.pipe.output_dir).glob('REVIEWED_VIDEO_*.mp4')))

    def test_failed_video_merge_keeps_accepted_review_and_publishes_nothing(self):
        self.video_review()
        before = self.store.load(self.identifier)
        with patch.object(self.pipe,'merge_av',side_effect=RuntimeError('mux failed')):
            with self.assertRaisesRegex(RuntimeError,'mux failed'):
                self.operate('render')
        self.assertEqual(self.store.load(self.identifier),before)
        self.assertFalse(list(Path(self.pipe.output_dir).glob('REVIEWED_VIDEO_*.mp4')))

    def test_small_asr_end_rounding_is_bounded_and_recorded_without_changing_text(self):
        from core.transcription import TranscriptionResult
        source = TranscriptionResult([dict(start=0,end=1.03,text='Hello')],'en',.99)
        bounded, changes = review.review_transcription_bounds(source,1)
        self.assertEqual(source[0]['end'],1.03)
        self.assertEqual(bounded[0],dict(start=0,end=1,text='Hello'))
        self.assertEqual(bounded.language,'en')
        self.assertEqual(changes[0]['original_end'],1.03)

    def test_genuine_out_of_bounds_or_overlap_cannot_be_retimed(self):
        from core.transcription import TranscriptionResult
        cases = [[dict(start=0,end=1.2,text='Hello')],
                 [dict(start=0,end=.8,text='Hello'),dict(start=.7,end=1,text='Bye')]]
        for cues in cases:
            with self.subTest(cues=cues), self.assertRaises(ValueError):
                review.review_transcription_bounds(TranscriptionResult(cues),1)

    def test_failed_or_long_regeneration_preserves_accepted_take(self):
        self.operate('generate'); self.accept()
        accepted = self.store.load(self.identifier)['cues'][0]['accepted']
        before = self.store.load(self.identifier)
        self.pipe._dub_segment.side_effect = RuntimeError('inference failed')
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            self.operate('generate')
        self.assertEqual(self.store.load(self.identifier), before)
        self.pipe._dub_segment.side_effect = None
        self.pipe._dub_segment.return_value = Sine(440).to_audio_segment(duration=1500)
        self.operate('generate')
        manifest = self.store.load(self.identifier)
        self.assertEqual(manifest['cues'][0]['accepted'], accepted)
        self.assertFalse(manifest['cues'][0]['candidate']['fits'])
        self.assertIn('allow_overflow', self.pipe._dub_segment.call_args.kwargs)
        with self.assertRaisesRegex(ValueError, 'fits'):
            self.accept()

    def test_edit_invalidates_only_changed_cue_and_stale_revision_rejected(self):
        for index in range(2):
            self.operate('generate', index); self.accept(index)
        before = self.store.load(self.identifier)
        result = self.store.edit(self.identifier, before['revision'], 0, 'Corrected source', 'नया पाठ')
        self.assertIsNone(result['cues'][0]['accepted'])
        self.assertEqual(self.store.load(self.identifier)['cues'][1], before['cues'][1])
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.store.edit(self.identifier, before['revision'], 0, 'Other edit', 'Other text')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.store.accept(self.identifier, True, 0)

    def test_timing_edit_preserves_accepted_pcm_and_render_uses_new_start(self):
        for index in range(2):
            self.operate('generate', index); self.accept(index)
        before = self.store.load(self.identifier)
        take = dict(before['cues'][0]['accepted'])
        revision = before['revision']
        self.store.edit(self.identifier, revision, 0, 'Hello', 'नमस्ते', .2, .9)
        after = self.store.load(self.identifier)
        self.assertEqual(after['cues'][0]['accepted'], take)
        self.assertEqual(after['cues'][0]['available_seconds'], .8)
        self.assertEqual(after['cues'][1], before['cues'][1])
        self.pipe._dub_segment.reset_mock()
        output = self.operate('render')
        self.pipe._dub_segment.assert_not_called()
        from core.audio_utils import load_playable_audio
        audio = load_playable_audio(output)
        self.assertEqual(audio[:200].max, 0)
        self.assertEqual(audio[200:600].set_frame_rate(self.clip.frame_rate).set_channels(1).raw_data, self.clip.raw_data)
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.store.edit(self.identifier, revision, 0, 'Hello', 'नमस्ते', .3, .9)

    def test_timing_that_cuts_previous_accepted_speech_is_atomic(self):
        value = self.store.load(self.identifier)
        value['cues'][0]['end'] = .25
        self.store.save(value, expected_revision=1)
        self.operate('generate', 0); self.accept(0)
        before = (self.folder/'review.json').read_bytes()
        current = self.store.load(self.identifier)
        with self.assertRaisesRegex(ValueError, 'cut accepted speech'):
            self.store.edit(self.identifier, current['revision'], 1, 'Bye', 'अलविदा', .3, 2)
        self.assertEqual((self.folder/'review.json').read_bytes(), before)

    def test_timing_changes_recompute_candidate_fit_without_deleting_audio(self):
        value = self.store.load(self.identifier)
        value['cues'][0]['end'] = .25
        self.store.save(value, expected_revision=1)
        self.operate('generate', 0)
        current = self.store.load(self.identifier)
        candidate = dict(current['cues'][0]['candidate'])
        result = self.store.edit(self.identifier, current['revision'], 1, 'Bye', 'अलविदा', .3, 2)
        self.assertFalse(result['cues'][0]['candidate']['fits'])
        stored = self.store.load(self.identifier)['cues'][0]['candidate']
        self.assertEqual(stored['file'], candidate['file'])
        self.assertEqual(stored['sha256'], candidate['sha256'])
        self.assertTrue((self.folder/stored['file']).is_file())

    def test_invalid_timing_and_noop_preserve_review(self):
        before = (self.folder/'review.json').read_bytes()
        for start,end in [(True,.9),('0',.9),(float('nan'),.9),(0,float('inf')),
            (0,None),(-.1,.9),(0,2.1),(1,.9),(.2,1.1)]:
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                self.store.edit(self.identifier, 1, 0, 'Hello', 'नमस्ते', start, end)
            self.assertEqual((self.folder/'review.json').read_bytes(),before)
        result = self.store.edit(self.identifier,1,0,'Hello','नमस्ते',0,1)
        self.assertEqual(result['revision'],1)
        self.assertEqual((self.folder/'review.json').read_bytes(),before)

    def test_bridge_timing_edit_is_locked_and_surfaces_bounds_failure(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock = threading.Lock()
        with patch.object(bridge,'_deletion_busy',return_value=False), patch.object(bridge,'_cue_store',return_value=self.store):
            result = bridge.edit_review_cue(self.identifier,1,0,'Hello','नमस्ते',.2,.9)
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['review']['cues'][0]['start'],.2)
            self.assertFalse(bridge.edit_review_cue(self.identifier,2,0,'Hello','नमस्ते',0,1.5)['ok'])
        with patch.object(bridge,'_deletion_busy',return_value=True):
            self.assertFalse(bridge.edit_review_cue(self.identifier,2,0,'Hello','नमस्ते',0,.9)['ok'])

    def test_retranslation_clears_take_and_uses_corrected_source(self):
        self.operate('generate'); self.accept()
        provider = Mock()
        self.pipe._resolve_translation_and_filter = Mock(return_value=(provider, '', None, ''))
        self.pipe._translate_line = Mock(return_value='नई अनुवादित पंक्ति')
        self.operate('translate')
        self.assertEqual(self.pipe._translate_line.call_args.args[0], 'Hello')
        self.assertIsNone(self.store.load(self.identifier)['cues'][0]['accepted'])

    def test_configuration_change_rejects_generation(self):
        self.pipe.registry.get_active.return_value = {'id': 'new-engine'}
        with self.assertRaisesRegex(ValueError, 'settings changed'):
            self.operate('generate')
        self.pipe._dub_segment.assert_not_called()

    def test_accepted_audio_renders_after_model_settings_change_without_inference(self):
        for index in range(2):
            self.operate('generate', index); self.accept(index)
        self.pipe.registry.get_active.return_value = {'id': 'different-model'}
        self.pipe._dub_segment.reset_mock()
        output = self.operate('render')
        self.assertTrue(Path(output).is_file())
        self.pipe._dub_segment.assert_not_called()

    def test_invalid_saved_timing_and_fit_metadata_are_rejected(self):
        from copy import deepcopy
        cases = []
        for field, value in [('start', -1), ('end', 3), ('available_seconds', 10), ('start', float('nan'))]:
            manifest = deepcopy(self.manifest)
            manifest['cues'][0][field] = value
            cases.append(manifest)
        overlap = deepcopy(self.manifest)
        overlap['cues'][1]['start'] = .5
        cases.append(overlap)
        overflow = deepcopy(self.manifest)
        overflow['cues'][0]['accepted'] = dict(file='bad.wav', seconds=2, fits=True, sha256='f'*64)
        cases.append(overflow)
        cases.extend([[], {'version': True}])
        for manifest in cases:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                review.validate_manifest(manifest)

    def test_competing_process_saves_do_not_overwrite_newer_cue(self):
        import subprocess
        import sys
        script = """
import json,sys,time
from pathlib import Path
sys.path[:0]=[sys.argv[1], str(Path(sys.argv[1])/'core')]
from core.cue_review import ReviewStore
store=ReviewStore(sys.argv[2]); manifest=store.load(sys.argv[3],1)
marker=Path(sys.argv[4])/('ready-'+sys.argv[5]); marker.touch()
deadline=time.monotonic()+30
while len(list(marker.parent.glob('ready-*')))<2:
    if time.monotonic()>deadline: raise RuntimeError('Process rendezvous timed out')
    time.sleep(.01)
manifest['cues'][0]['text']=sys.argv[5]; manifest['revision']=2
try:
    store.save(manifest,expected_revision=1); print(json.dumps({'ok':True}))
except ValueError as exc:
    print(json.dumps({'ok':False,'reason':str(exc)}))
"""
        processes = [subprocess.Popen([sys.executable, '-B', '-c', script,
            str(Path(__file__).resolve().parents[1]), str(self.root/'outputs'), self.identifier,
            str(self.root), name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for name in ('first-process', 'second-process')]
        try:
            results = []
            for process in processes:
                output, error = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 0, error)
                results.append(json.loads(output))
            self.assertEqual(sum(result['ok'] for result in results), 1)
            self.assertIn('changed', next(result['reason'] for result in results if not result['ok']))
            self.assertEqual(self.store.load(self.identifier)['revision'], 2)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill(); process.wait()

    def test_standalone_save_retries_transient_windows_sharing_denial(self):
        from core import json_store
        from types import SimpleNamespace
        manifest = self.store.load(self.identifier, 1)
        manifest['cues'][0]['text'] = 'Saved after sharing lock'
        manifest['revision'] = 2
        original = json_store.os.replace
        calls = []
        denied = PermissionError('fixture sharing denial')
        denied.winerror = 5
        def replace(source, target):
            calls.append(1)
            if len(calls) == 1:
                self.assertEqual(json.loads((self.folder / 'review.json').read_text(encoding='utf-8'))['revision'], 1)
                raise denied
            return original(source, target)
        filesystem = SimpleNamespace(name='nt', path=json_store.os.path, replace=replace,
                                     fdopen=json_store.os.fdopen, fsync=json_store.os.fsync, unlink=json_store.os.unlink)
        with patch.object(json_store, 'os', filesystem), patch.object(json_store.time, 'sleep') as wait:
            self.store.save(manifest, expected_revision=1)
        self.assertEqual(len(calls), 2)
        wait.assert_called_once_with(.05)
        self.assertEqual(self.store.load(self.identifier)['revision'], 2)
        self.assertFalse(list(self.folder.glob('pending-*')))

    def test_reader_waits_for_review_transaction_before_checking_replaced_path(self):
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.store._transaction(self.identifier):
                future = pool.submit(self.store.load, self.identifier, 1)
                with self.assertRaises(TimeoutError):
                    future.result(timeout=.1)
            self.assertEqual(future.result(timeout=5)['revision'], 1)

    def test_missing_acceptance_or_tampered_take_cannot_publish(self):
        with self.assertRaisesRegex(ValueError, 'Every cue'):
            self.operate('render')
        for index in range(2):
            self.operate('generate', index); self.accept(index)
        manifest = self.store.load(self.identifier)
        path = self.store.asset(manifest, manifest['cues'][0]['accepted']['file'])
        path.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.operate('render')
        self.assertEqual(list((self.root / 'outputs').glob('REVIEWED_AUDIO_*')), [])

    def test_paths_indexes_and_empty_text_are_rejected(self):
        for value in ('../outside', 'A'*32, '', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.folder(value)
        for value in ('../outside.wav', 'C:\\outside.wav', 'dir/file.wav'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.asset(self.manifest, value)
        for index in (-1, True, 2):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.store.cue(self.manifest, index)
        with self.assertRaises(ValueError):
            self.store.edit(self.identifier, 1, 0, '', 'Text')

    def test_cancelled_save_preserves_previous_manifest(self):
        before = (self.folder / 'review.json').read_bytes()
        job = RenderContext(self.root / 'temp')
        job.request_stop()
        try:
            with bind_job(job), self.assertRaises(RenderCancelled):
                self.store.save({**self.manifest, 'revision': 2})
        finally:
            job.cleanup()
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)
        self.assertFalse(list(self.folder.glob('pending-*')))

    def test_bridge_busy_and_revision_guards_cover_mutations(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock = threading.Lock()
        with patch.object(bridge, '_cue_store', return_value=self.store), \
                patch.object(bridge, '_deletion_busy', return_value=True):
            self.assertFalse(bridge.edit_review_cue(self.identifier, 1, 0, 'Edit', 'Text')['ok'])
            self.assertFalse(bridge.accept_review_cue(self.identifier, 1, 0)['ok'])
            self.assertFalse(bridge.estimate_review_timing(self.identifier, 1, 0)['ok'])
        with patch.object(bridge, '_cue_store', return_value=self.store), \
                patch.object(bridge, '_start_rejection', return_value=None), \
                patch.object(bridge, '_start_worker') as worker:
            self.assertFalse(bridge.start_review_action(self.identifier, 0, 'generate', 0)['ok'])
            self.assertFalse(bridge.start_review_action(self.identifier, 1, 'unknown', 0)['ok'])
            worker.assert_not_called()

    def test_bridge_timing_estimate_uses_saved_configuration_and_reports_stale_review(self):
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock = threading.Lock()
        bridge.registry, bridge.settings = self.pipe.registry, self.settings
        with patch.object(bridge, '_cue_store', return_value=self.store), \
                patch.object(bridge, '_deletion_busy', return_value=False), \
                patch.object(providers, 'uses_exact_reference', return_value=False):
            self.assertTrue(bridge.estimate_review_timing(self.identifier, 1, 0)['ok'])
            self.assertFalse(bridge.estimate_review_timing(self.identifier, 0, 0)['ok'])

    def test_prepare_publishes_owned_audio_snapshot_and_failed_prepare_publishes_nothing(self):
        from core.transcription import TranscriptionResult
        source = self.root / 'input.wav'
        Sine(440).to_audio_segment(duration=2000).export(source, format='wav').close()
        self.pipe._transcribe_source = Mock(return_value=TranscriptionResult([
            dict(start=0, end=1, text='Hello'), dict(start=1, end=2, text='Bye')], 'en', .99))
        self.pipe._check_speech_routes = Mock()
        translator = Mock(engine_id='indictrans2')
        self.pipe._resolve_translation_and_filter = Mock(return_value=(translator, '', None, ''))
        self.pipe._translate_line = Mock(side_effect=['नमस्ते', 'अलविदा'])
        self.pipe.clear_vram = Mock()
        params = dict(target_lang='hi', source_language='en', keep_background=False, cast_list=['CLONED_USER'])
        job = RenderContext(self.root / 'temp')
        try:
            with bind_job(job), patch.object(providers, 'resolve_stt', return_value=Mock()):
                path = review.prepare(self.store, self.pipe, str(source), params, self.settings, self.progress)
            prepared = self.store.load(Path(path).parent.name)
            self.assertEqual(prepared['cues'][0]['source_text'], 'Hello')
            self.assertEqual(prepared['cues'][0]['text'], 'नमस्ते')
            self.assertEqual(prepared['duration'], 2)
            self.assertNotIn('background.wav', prepared['assets'])
            import base64
            import io
            from pydub import AudioSegment
            encoded = self.store.source_audio(prepared['id'], 0)
            self.assertTrue(encoded.startswith('data:audio/wav;base64,'))
            decoded = AudioSegment.from_file(io.BytesIO(base64.b64decode(encoded.split(',', 1)[1])), format='wav')
            self.assertEqual(len(decoded), 1000)
        finally:
            job.cleanup()
        before = self.store.list()
        self.pipe._translate_line.side_effect = RuntimeError('translation failed')
        job = RenderContext(self.root / 'temp')
        try:
            with bind_job(job), patch.object(providers, 'resolve_stt', return_value=Mock()), self.assertRaises(RuntimeError):
                review.prepare(self.store, self.pipe, str(source), params, self.settings, self.progress)
        finally:
            job.cleanup()
        self.assertEqual(self.store.list(), before)
        self.assertEqual(translator.release.call_count, 2)

    def test_indic_reference_preparation_preserves_confirmed_samples(self):
        from core.transcription import TranscriptionResult
        from core.audio_utils import AudioEngineer
        reference = self.folder / 'reference.wav'
        expected_hash = review.digest(reference)
        source = self.root / 'indic-source.wav'
        Sine(440).to_audio_segment(duration=2000).export(source, format='wav').close()
        self.pipe._transcribe_source = Mock(return_value=TranscriptionResult([
            dict(start=0, end=2, text='Hello')], 'en', .99))
        self.pipe._check_speech_routes = Mock()
        self.pipe._resolve_translation_and_filter = Mock(return_value=(Mock(), '', None, ''))
        self.pipe._translate_line = Mock(return_value='नमस्ते')
        self.pipe.clear_vram = Mock()
        self.pipe.registry.get_active.return_value = {'meta': {'reference_profile': 'fixture'}}
        params = dict(target_lang='hi', source_language='en', keep_background=False,
                      cast_list=['CLONED_USER'])
        job = RenderContext(self.root / 'temp')
        try:
            with bind_job(job), patch.object(providers, 'resolve_stt', return_value=Mock()), \
                    patch.object(providers, 'uses_exact_reference', return_value=True), \
                    patch('core.providers.tts.indicf5_local.load_reference_profile', return_value={
                        'reference_audio': str(reference), 'reference_sha256': expected_hash}), \
                    patch.object(AudioEngineer, 'clean_reference_audio') as cleaner:
                path = review.prepare(self.store, self.pipe, str(source), params, self.settings, self.progress)
            manifest = self.store.load(Path(path).parent.name)
            self.assertEqual(manifest['assets']['reference.wav'], expected_hash)
            cleaner.assert_not_called()
        finally:
            job.cleanup()

    def test_combine_keeps_timeline_and_other_accepted_lines(self):
        manifest = self.store.load(self.identifier)
        manifest['duration'] = 4
        manifest['cues'][0]['available_seconds'] = 1.2
        manifest['cues'][1].update(start=1.2, end=2, available_seconds=1.8)
        manifest['cues'].append(dict(start=3, end=4, available_seconds=1,
            source_text='Unchanged', text='अगला', candidate=None, accepted=None))
        take = dict(file='reference.wav', seconds=.4, fits=True,
                    sha256=review.digest(self.folder / 'reference.wav'))
        manifest['cues'][0]['accepted'] = dict(take)
        manifest['cues'][1]['candidate'] = dict(take)
        manifest['cues'][2]['accepted'] = dict(take)
        self.store.save(manifest, expected_revision=1)
        third = dict(manifest['cues'][2])
        result = self.store.combine(self.identifier, 1, 0)
        self.assertEqual(result['revision'], 2)
        self.assertEqual(len(result['cues']), 2)
        self.assertEqual(result['cues'][0]['source_text'], 'Hello Bye')
        self.assertEqual(result['cues'][0]['start'], 0)
        self.assertEqual(result['cues'][0]['end'], 2)
        self.assertEqual(result['cues'][0]['available_seconds'], 3)
        self.assertEqual(self.store.load(self.identifier)['cues'][1], third)
        self.assertIsNone(result['cues'][0]['accepted'])
        self.assertIsNone(result['cues'][0]['candidate'])
        before = (self.folder / 'review.json').read_bytes()
        with self.assertRaises(ValueError):
            self.store.combine(self.identifier, 1, 0)
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)

    def test_combine_refuses_last_line_oversize_and_busy_bridge(self):
        before = (self.folder / 'review.json').read_bytes()
        with self.assertRaises(ValueError):
            self.store.combine(self.identifier, 1, 1)
        self.assertEqual((self.folder / 'review.json').read_bytes(), before)
        manifest = self.store.load(self.identifier)
        manifest['cues'][0]['source_text'] = 'x'*4000
        self.store.save(manifest, expected_revision=1)
        with self.assertRaisesRegex(ValueError, '4000-character'):
            self.store.combine(self.identifier, 1, 0)
        bridge = api.PythonBridge.__new__(api.PythonBridge)
        bridge._render_lock = threading.Lock()
        with patch.object(bridge, '_deletion_busy', return_value=True):
            self.assertFalse(bridge.combine_review_cues(self.identifier, 1, 0)['ok'])


if __name__ == '__main__':
    unittest.main()
