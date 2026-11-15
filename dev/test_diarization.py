import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.diarization import validate_turns, clear_ranges, references, prepare


class DiarizationTests(unittest.TestCase):
    def test_scene_reference_uses_the_current_style_not_a_distant_same_voice(self):
        import numpy as np
        from pydub import AudioSegment
        from pydub.generators import Sine
        from core.diarization import scene_references
        audio=AudioSegment.silent(duration=67000,frame_rate=16000)
        audio=audio.overlay(Sine(220,sample_rate=16000).to_audio_segment(duration=6000),position=0)
        audio=audio.overlay(Sine(330,sample_rate=16000).to_audio_segment(duration=6000),position=60000)
        cues=[dict(cue_id='old',start=0,end=6,speaker='A',speaker_match='matched'),
              dict(cue_id='new',start=60,end=66,speaker='A',speaker_match='matched')]
        with tempfile.TemporaryDirectory() as folder:
            refs=scene_references(audio,cues,folder,{'A':'global.wav'})
            with open(refs['new']['reference'],'rb') as stream:clip=AudioSegment.from_file(stream,format='wav')
            samples=np.asarray(clip.get_array_of_samples(),dtype=float)
            peak=np.argmax(abs(np.fft.rfft(samples))) * clip.frame_rate/len(samples)
            self.assertAlmostEqual(peak,330,delta=1)
            self.assertEqual(refs['new']['source_cues'],['new'])

    def test_short_reference_never_borrows_a_different_character(self):
        from pydub.generators import Sine
        from core.diarization import scene_references
        audio=Sine(220).to_audio_segment(duration=9000)
        cues=[dict(cue_id='a',start=0,end=2,speaker='A',speaker_match='matched'),
              dict(cue_id='b',start=2,end=9,speaker='B',speaker_match='matched')]
        with tempfile.TemporaryDirectory() as folder:
            refs=scene_references(audio,cues,folder,{'A':'a.wav','B':'b.wav'})
        self.assertNotIn('a',refs)
        self.assertEqual(refs['b']['source_cues'],['b'])

    def test_caption_references_use_aligned_separated_vocals(self):
        from pydub.generators import Sine
        from core.render_context import RenderContext, bind_job
        from core.transcription import TranscriptionResult
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(folder)
            source, vocals = job.workspace/'source.wav', job.workspace/'vocals.wav'
            Sine(220).to_audio_segment(duration=6000).export(source, format='wav').close()
            clean = Sine(440).to_audio_segment(duration=6000)
            clean.export(vocals, format='wav').close()
            def execute(args, **kwargs):
                self.assertEqual(Path(args[3]), source.resolve())
                Path(args[4]).write_text(json.dumps(self.result()), encoding='utf-8')
            try:
                transcript = TranscriptionResult([dict(start=0, end=2, text='一', source_caption=True)], 'ja')
                with bind_job(job), patch('core.diarization_runtime.validate', return_value=dict(executable='python', identity='verified')), patch('core.render_context.run_process', side_effect=execute), patch('core.caption_speakers.assign', return_value=(transcript, {})) as assign:
                    prepare(source, transcript, Mock(), 'cuda:0', None, 'test', reference_audio_path=vocals)
                self.assertEqual(assign.call_args.args[0].raw_data, clean.raw_data)
            finally:
                job.cleanup()

    def result(self):
        return dict(audio_seconds=6, device='cuda:0', identity='verified', turns=[
            dict(start=0, end=2, speaker='A'), dict(start=2, end=4, speaker='B'),
            dict(start=4, end=6, speaker='C')])

    def test_more_than_two_speakers_are_retained(self):
        self.assertEqual(len(validate_turns(self.result())), 3)

    def test_overlapping_exclusive_turns_are_rejected(self):
        result = self.result()
        result['turns'][1]['start'] = 1
        with self.assertRaises(ValueError):
            validate_turns(result)

    def test_nonfinite_timestamps_are_rejected(self):
        result = self.result()
        result['turns'][1]['end'] = float('nan')
        with self.assertRaises(ValueError):
            validate_turns(result)

    def test_exclusions_are_subtracted_without_moving_the_timeline(self):
        self.assertEqual(clear_ranges(0, 10, [(2, 4), (7, 9)]), [(0, 2), (4, 7), (9, 10)])

    def test_music_and_overlapping_voices_cannot_be_reference_anchors(self):
        from pydub.generators import Sine
        with tempfile.TemporaryDirectory() as folder:
            audio = Sine(220).to_audio_segment(duration=6000)
            result = self.result()
            result['overlapping_turns'] = [*result['turns'], dict(start=.1, end=1.9, speaker='B')]
            saved = references(audio, result, Path(folder), excluded=[(4, 6)])
            self.assertNotIn('A', saved)
            self.assertNotIn('C', saved)
            self.assertIn('B', saved)

    def test_source_turns_keep_their_character_after_recognition(self):
        from pydub import AudioSegment
        from pydub.generators import Sine
        from core.render_context import RenderContext, bind_job
        from core.transcription import TranscriptionResult
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            job = RenderContext(folder)
            source = job.workspace/'source.wav'
            Sine(220).to_audio_segment(duration=6000).export(source, format='wav').close()
            vocals = job.workspace/'vocals.wav'
            Sine(440).to_audio_segment(duration=6000).export(vocals, format='wav').close()
            manifest = Mock(folder=folder/'records')
            manifest.folder.mkdir()
            recognizer = Mock()
            def recognize(paths, language):
                self.assertEqual(language, 'ja')
                self.assertTrue(all(len(AudioSegment.from_wav(path)) >= 30000 for path in paths))
                return [[dict(start=0, end=2, text=word)] for word in ('一', '二', '三')]
            recognizer.transcribe_takes.side_effect = recognize
            def execute(args, **kwargs):
                Path(args[4]).write_text(json.dumps(self.result()), encoding='utf-8')
            try:
                with bind_job(job), patch('core.diarization_runtime.validate', return_value=dict(executable='python', identity='verified')), patch('core.render_context.run_process', side_effect=execute):
                    cues, mapping = prepare(source, TranscriptionResult([], 'ja'), recognizer,
                                            'cuda:0', manifest, 'test-source', reference_audio_path=vocals)
                self.assertEqual([cue['speaker'] for cue in cues], ['A', 'B', 'C'])
                self.assertEqual(len({row['reference'] for row in mapping.values()}), 3)
                self.assertTrue(all(row['status'] == 'matched' for row in mapping.values()))
                self.assertTrue(all(row['source_measure']['pitch'] > 400 for row in mapping.values()))
                recognizer.release.assert_called_once()
            finally:
                job.cleanup()
