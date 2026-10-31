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
        self.assertEqual(assess(provider,cues,['CLONED_USER'],total_duration=2)['status'],'fits_prediction')
        self.assertEqual(cues[0]['end'],1)
    def test_speed_caps_and_native_hindi_recipe_remain_unchanged(self):
        self.assertEqual(speed_for_window(3000,1000,'en'),1.3)
        self.assertEqual(speed_for_window(300,1000,'en'),1.0)
        self.assertEqual(speed_for_window(2000,1000,'hi'),1.342)
        self.assertEqual(speed_for_window(2000,1000,'hi',True),1.0)
