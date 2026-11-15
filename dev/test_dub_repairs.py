import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import numpy as np

from core.speech_generation_budget import generation_budget, bounded_generate, SpeechGenerationLimitExceeded
from core.voice_conditioning import cached_conditioning
from core.dub_quality import assess, DubReviewRequired
from core.caption_voice_identity import profiles,match,unit
from unittest.mock import patch


class RepairTests(unittest.TestCase):
    def test_corroboration_requires_two_initial_examples_and_does_not_chain(self):
        from core.caption_voice_identity import choose_cues
        templates={'a':dict(label='Alice',center=[1.,0.,0.]),'b':dict(label='Bob',center=[0.,1.,0.])}
        cues=[dict(start=i*4,end=i*4+2,text='Line') for i in range(3)]
        weak=unit([.58,.1,.808]); strong=unit([.8,0,.6])
        chosen,evidence=choose_cues(cues,{0:weak,1:strong,2:strong},templates,{})
        self.assertEqual(chosen[0],'a')
        self.assertEqual(evidence[0]['method'],'two_source_examples')
        chosen,_=choose_cues(cues,{0:weak,1:weak,2:strong},templates,{})
        self.assertIsNone(chosen[0]); self.assertIsNone(chosen[1])

    def test_utterance_evidence_cannot_cross_a_competing_voice(self):
        from core.caption_voice_identity import choose_cues
        templates={'a':dict(label='Alice',center=[1.,0.,0.,0.]),'b':dict(label='Bob',center=[0.,1.,0.,0.])}
        first=unit([.59,.1,math.sqrt(.6419),0]); last=unit([.59,.1,.26,math.sqrt(.6419-.26**2)])
        cues=[dict(start=i*2.1,end=i*2.1+2,text='Line') for i in range(3)]
        joined,evidence=choose_cues(cues[:2],{0:first,1:last},templates,{})
        self.assertEqual(joined,{0:'a',1:'a'})
        self.assertEqual(evidence[0]['method'],'consistent_utterance')
        split,_=choose_cues(cues,{0:first,1:[0.,1.,0.,0.],2:last},templates,{})
        self.assertIsNone(split[0]); self.assertIsNone(split[2])

    def test_voice_embedding_is_independent_of_longer_neighbouring_clips(self):
        from core.diarization_worker import unpadded_embeddings
        short=np.arange(120,dtype=float).reshape(1,120)
        long=np.ones((1,900))
        calls=[]
        def embedding(values):
            calls.append(values.shape)
            return values.mean(axis=-1)
        alone=list(unpadded_embeddings(embedding,[('short',short)]))[0][1]
        together=list(unpadded_embeddings(embedding,[('long',long),('short',short)]))[1][1]
        np.testing.assert_array_equal(alone,together)
        self.assertEqual(calls,[(1,1,120),(1,1,900),(1,1,120)])

    def test_missing_readback_results_cannot_pass_and_music_is_excluded(self):
        from core.dub_quality import assess_readback
        cues=[dict(start=i,end=i+1,text='Speech') for i in range(3)]
        with self.assertRaises(DubReviewRequired) as error:
            assess_readback(cues,{'cues':[{'index':1,'status':'passed_readback'}]}, {0:'marked_singing'})
        self.assertEqual(error.exception.report['total'],2)
        self.assertEqual(error.exception.report['unresolved'],1)
        self.assertEqual(error.exception.report['cues'][0]['index'],2)

    def test_unfinished_generation_is_rejected_before_audio_publication(self):
        function=Mock(return_value=np.array([[2,3,4]]))
        generate=bounded_generate(function)
        with generation_budget(2,.05), self.assertRaises(SpeechGenerationLimitExceeded):
            generate(np.ones((1,10)),eos_token_id=0,max_length=615)
        self.assertEqual(function.call_args.kwargs['max_new_tokens'],40)
        function.return_value=np.array([[2,3,0]])
        with generation_budget(2,.05):
            self.assertEqual(generate(np.ones((1,10)),eos_token_id=0,max_length=615)[0,-1],0)

    def test_generation_budget_does_not_leak_to_other_calls(self):
        function=Mock(return_value=np.array([[0]])); generate=bounded_generate(function)
        with generation_budget(1,.05): generate(np.ones((1,3)),eos_token_id=0)
        generate(np.ones((1,3)),eos_token_id=0)
        self.assertNotIn('max_new_tokens',function.call_args.kwargs)

    def test_reference_conditioning_is_reused_and_invalidated_on_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ref.wav'; path.write_bytes(b'original')
            calls=[]
            def encode(audio_path,max_ref_length=30):
                calls.append((audio_path,max_ref_length)); return object()
            cached=cached_conditioning(encode)
            first=cached(path)
            self.assertIs(first,cached(path))
            self.assertEqual(len(calls),1)
            self.assertIsNot(first,cached(path,max_ref_length=20))
            path.write_bytes(b'different reference')
            self.assertIsNot(first,cached(path))
            self.assertEqual(len(calls),3)

    def test_incomplete_episode_cannot_be_reported_as_completed(self):
        cues=[dict(start=i,end=i+1,text='Speech',cue_id=str(i)) for i in range(363)]
        with self.assertRaises(DubReviewRequired) as error:
            assess(cues,{i:'timing_overflow' for i in range(355)},'speech')
        self.assertEqual(error.exception.report['ready'],8)
        self.assertEqual(error.exception.report['total'],363)

    def test_intentionally_preserved_music_does_not_count_as_missing_dialogue(self):
        report=assess([dict(start=0,end=2,text='Song'),dict(start=3,end=4,text='Hi')],
                      {0:'marked_singing'},'speech')
        self.assertEqual(report['total'],1)
        self.assertEqual(report['status'],'ready')

    def test_three_characters_can_be_resolved_inside_one_global_scene_cluster(self):
        cues=[dict(speaker_hint=name) for name in ['A','B','C']]
        vectors={0:[1.,0,0],1:[0,1.,0],2:[0,0,1.]}
        templates,_=profiles(cues,vectors)
        self.assertEqual([templates[match(vector,templates)[0]]['label'] for vector in vectors.values()],['A','B','C'])
        self.assertIsNone(match(unit([1.,1.,1.]),templates)[0])

    def test_generic_label_does_not_pool_distinct_voices_into_one_reference(self):
        templates,named=profiles([dict(speaker_hint='Child'),dict(speaker_hint='Child')],{0:[1.,0],1:[0,1.]})
        self.assertNotEqual(named[0],named[1])

    def test_a_mixed_caption_cannot_contaminate_named_voice_templates(self):
        templates,named=profiles([dict(speaker_hint='Father',multiple_caption_speakers=True),
            dict(speaker_hint='Daughter')],{0:[1.,0],1:[0,1.]})
        self.assertNotIn(0,named)
        self.assertEqual([row['label'] for row in templates.values()],['Daughter'])

    def test_named_voice_styles_pool_but_short_interjections_are_not_anchors(self):
        cues=[dict(speaker_hint='Alice',start=0,end=3),dict(speaker_hint='Alice',start=3,end=6),
              dict(speaker_hint='Bob',start=6,end=6.8)]
        templates,named=profiles(cues,{0:[1.,0],1:[0,1.],2:[1.,0]})
        self.assertEqual(len(templates),1)
        self.assertEqual(named[0],named[1])
        self.assertNotIn(2,named)

    def test_short_labelled_reply_uses_its_named_voice_without_polluting_profiles(self):
        from core.caption_voice_identity import match_cue
        templates,_=profiles([dict(speaker_hint='Alice')],{0:[1.,0]})
        key,_,_=match_cue(dict(speaker_hint='Alice',start=0,end=.8),[0.,1.],templates)
        self.assertEqual(templates[key]['label'],'Alice')
        self.assertIsNone(match_cue(dict(start=0,end=.8),unit([.65,.76]),templates)[0])

    def test_voice_routing_ignores_merged_global_group_and_joins_only_same_voice(self):
        from core.caption_voice_identity import assign
        from core.transcription import TranscriptionResult
        from pydub import AudioSegment
        cues=TranscriptionResult([
            dict(start=0,end=2,text='First',cue_id='a',speaker_hint='A'),
            dict(start=2.2,end=4.2,text='Second',cue_id='b'),
            dict(start=4.5,end=6.5,text='Third',cue_id='c',speaker_hint='B')],'en')
        result=dict(device='cuda:0',audio_seconds=7,turns=[dict(start=0,end=7,speaker='merged')],
            cue_embeddings=[dict(cue_id=key,vector=value) for key,value in [('a',[1.,0]),('b',[1.,0]),('c',[0,1.])]])
        with tempfile.TemporaryDirectory() as folder, patch('core.diarization.references',return_value={'A / 1':'a.wav','B / 1':'b.wav'}),patch('core.speech_performance.measure',return_value=None):
            joined,rows=assign(AudioSegment.silent(duration=7000),cues,result,Path(folder),'test')
        self.assertEqual(len(joined),2)
        self.assertEqual(joined[0]['text'],'First Second')
        self.assertEqual(len(joined[0]['parent_ids']),2)
        self.assertEqual([rows[c['cue_id']]['reference'] for c in joined],['a.wav','b.wav'])

    def test_failed_job_review_is_visible_without_an_export(self):
        import json
        from bridge.api import PythonBridge
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'outputs'; records=output/'run_records'/'job'; records.mkdir(parents=True)
            cues=records/'cues.json'; report=records/'coverage.json'; manifest=records/'manifest.json'
            cues.write_text(json.dumps({'segments':[dict(cue_id='a',start=1,end=2,text='Hello',source_text='Source')]}))
            report.write_text(json.dumps(dict(status='needs_review',ready=0,total=1,unresolved=1,
                cues=[dict(index=0,cue_id='a',start=1,end=2,reason='timing_overflow')])))
            manifest.write_text(json.dumps(dict(cue_artifacts=[dict(phase='source-character-turns',path=str(cues))],
                quality_reports=[dict(kind='dub-coverage',path=str(report))])))
            bridge=PythonBridge.__new__(PythonBridge); bridge._last_run_manifest_path=str(manifest)
            with patch('bridge.api.config.OUTPUT_PATH',str(output)):
                value=bridge.get_failed_render_review()
            self.assertTrue(value['ok'])
            self.assertEqual(value['review']['coverage']['ready'],0)
            self.assertEqual(value['review']['cues'][0]['text'],'Hello')


if __name__=='__main__': unittest.main()
