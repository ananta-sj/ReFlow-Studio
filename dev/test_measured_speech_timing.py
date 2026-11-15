"""Real durable overflow takes and native-window budget consistency."""
import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from pydub import AudioSegment
from pydub.generators import Sine
from core.speech_timing import measured_conflict,SpeechTimingReviewRequired,speed_for_window,bounded_cues
from core.run_manifest import RunManifest,file_identity
from core.pipeline_contracts import PipelineSpec,RegistrySnapshot,SettingsSnapshot
from core.dialogue_adaptation import assess
ROOT=Path(__file__).resolve().parents[1]

class MeasuredSpeechTimingTests(unittest.TestCase):
    def test_video_recovers_an_oversized_take_and_keeps_other_lines(self):
        from core.pipeline import ReflowPipeline

        class RetryingVoice:
            def synthesize_retry(self):
                pass

        pipe = ReflowPipeline.__new__(ReflowPipeline)
        clip = Sine(220).to_audio_segment(duration=500)
        oversized = SpeechTimingReviewRequired(dict(index=2, actor='CLONED_USER',
            measured_seconds=2, available_seconds=1))
        pipe._dub_segment = Mock(side_effect=[oversized, oversized, clip])
        cues = [dict(start=i, end=i+1, text='Words') for i in range(3)]
        preserved = {0: 'marked_singing'}
        render = pipe._dub_all_segments(cues, ['CLONED_USER'], 'hi', RetryingVoice(), {},
            None, None, 'cpu', None, 3, 45, 30, preserved=preserved)
        while True:
            try:
                next(render)
            except StopIteration as result:
                track = result.value
                break
        self.assertEqual(preserved, {0: 'marked_singing', 1: 'timing_overflow'})
        self.assertEqual([call.args[0] for call in pipe._dub_segment.call_args_list], [1, 1, 2])
        self.assertTrue(pipe._dub_segment.call_args_list[1].kwargs['alternate_take'])
        self.assertEqual(track[:2000].max, 0)
        self.assertGreater(track[2000:2500].max, 0)

    def test_preserved_audio_keeps_the_original_mix_without_changing_timeline(self):
        from core.dub_recovery import restore_source_ranges

        source = Sine(220).to_audio_segment(duration=3000).apply_gain(-12)
        dub = Sine(440).to_audio_segment(duration=3000).apply_gain(-12)
        result = restore_source_ranges(dub, source, [(0, 1), (1, 2)])
        self.assertEqual(len(result), len(dub))
        self.assertEqual(result[:1950], source[:1950])
        self.assertEqual(result[2050:], dub[2050:])

    def test_background_beat_alone_does_not_skip_dialogue(self):
        from unittest.mock import patch
        from core.dub_recovery import music_cues

        background = Sine(220).to_audio_segment(duration=65_000).apply_gain(-15)
        dialogue = [dict(start=i, end=i+10, text='とてもはやくおはなしします'*4) for i in range(0, 50, 10)]
        with patch('core.dub_recovery._beat', return_value=(46, .2, .2)):
            self.assertEqual(music_cues(dialogue, background, 'ja'), {})
        marked = [dict(start=150, end=155, text='♪ 明日へ')]
        self.assertEqual(music_cues(marked, None, 'ja'), {0: 'marked_singing'})

    def test_media_end_rounding_is_bounded_without_mutating_source(self):
        cues=[dict(start=1,end=2.03,text='Words')]
        self.assertEqual(bounded_cues(cues,2)[0]['end'],2);self.assertEqual(cues[0]['end'],2.03)
        with self.assertRaisesRegex(ValueError,'outside'):bounded_cues(cues,1.5)
    def test_real_overflow_take_survives_and_requires_review(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'temp') as folder:
            manifest=RunManifest(folder,PipelineSpec('audio_dub',{}),'fixture.wav',RegistrySnapshot(dict(entries=[],active={})),SettingsSnapshot({}))
            clip=Sine(220).to_audio_segment(duration=1600)
            report=measured_conflict(manifest,clip,index=0,segment=dict(start=0,end=1,text='Complete words',cue_id='one'),actor='CLONED_USER',generated_seconds=2.08,available_seconds=1,speed=1.3,native_delivery=False)
            self.assertEqual(report['candidate']['sha256'],file_identity(report['candidate']['path'])['sha256'])
            self.assertEqual(len(AudioSegment.from_wav(report['candidate']['path'])),1600)
            saved=json.loads(manifest.path.read_text());self.assertTrue(saved['review_required'])
            self.assertEqual(saved['quality_reports'][0]['status'],'needs_review')
            self.assertFalse(report['words_cut']);self.assertFalse(report['auto_rewrite'])
            self.assertIn('1.600s',str(SpeechTimingReviewRequired(report)))
    def test_native_preflight_uses_same_final_media_tail(self):
        provider=Mock(preserves_native_delivery=True);provider.estimate_duration_seconds.return_value=1.5
        cues=[dict(start=0,end=1,text='Speech')]
        self.assertEqual(assess(provider,cues,['CLONED_USER'])['status'],'needs_review')
        self.assertEqual(assess(provider,cues,['CLONED_USER'],total_duration=2)['status'],'needs_review')
        provider.estimate_duration_seconds.return_value=1.3
        self.assertEqual(assess(provider,cues,['CLONED_USER'],total_duration=2)['status'],'fits_prediction')
        self.assertEqual(cues[0]['end'],1)
    def test_speed_caps_and_native_hindi_recipe_remain_unchanged(self):
        self.assertEqual(speed_for_window(3000,1000,'en'),1.3)
        self.assertEqual(speed_for_window(300,1000,'en'),1.0)
        self.assertEqual(speed_for_window(2000,1000,'hi'),1.15)
        self.assertEqual(speed_for_window(1050,1000,'hi'),1.05)
        self.assertEqual(speed_for_window(900,1000,'hi'),1.0)
        self.assertEqual(speed_for_window(2000,1000,'hi',True),1.0)
