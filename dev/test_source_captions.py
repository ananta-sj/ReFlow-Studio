import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.source_captions import classify, extract
from core.transcription import TranscriptionResult


def cue(start, end, text):
    return dict(start=start, end=end, text=text)


class SourceCaptionTests(unittest.TestCase):
    def test_inline_character_handoff_cannot_be_a_single_voice_anchor(self):
        spoken,_=classify([cue(0,4,'（父）ハハハ （娘）ウフフ'),cue(5,7,'（娘）こんにちは')],True)
        self.assertTrue(spoken[0]['multiple_caption_speakers'])
        self.assertFalse(spoken[1].get('multiple_caption_speakers',False))

    def test_speaker_and_readings_are_not_spoken(self):
        spoken, events = classify([cue(1, 3, '（マリ）ここを発（た）つ')], True)
        self.assertEqual(spoken[0]['text'], 'ここを発つ')
        self.assertEqual(spoken[0]['speaker_hint'], 'マリ')

    def test_song_and_sound_are_not_dialogue(self):
        spoken, events = classify([cue(0, 1, '♪～'), cue(2, 4, '♪歌だ'),
            cue(5, 6, '～♪'), cue(7, 8, '（くしゃみ）')], True)
        self.assertFalse(spoken)
        self.assertTrue(any(e['start'] == 0 and e['end'] == 6 for e in events))

    def test_background_music_does_not_restore_original_dialogue(self):
        spoken, events = classify([cue(0, 1, '♪～'), cue(2, 4, 'こんにちは'),
            cue(5, 6, '～♪')], True)
        self.assertEqual(len(spoken), 1)
        self.assertFalse(events)

    def test_overlapping_lyric_never_restores_dialogue(self):
        spoken, events = classify([cue(1, 5, '♪歌'), cue(2, 4, 'こんにちは')], True)
        self.assertEqual([(e['start'], e['end']) for e in events], [(1, 2), (4, 5)])

    def test_wrong_language_stream_is_not_selected(self):
        from types import SimpleNamespace
        with patch('core.render_context.run_process', return_value=SimpleNamespace(stdout=
                '{"streams":[{"index":2,"codec_name":"subrip","tags":{"language":"eng"}}]}')) as run:
            self.assertIsNone(extract('source.mkv', 'ja', '.'))
            self.assertEqual(run.call_count, 1)

    def test_explicit_names_override_merged_model_group(self):
        from core.caption_speakers import assign
        from pydub import AudioSegment
        transcript = TranscriptionResult([dict(cue(0, 2, 'こんにちは'), speaker_hint='A'),
            dict(cue(2, 4, 'こんばんは'), speaker_hint='B'), cue(4, 6, 'はい')], 'ja')
        result = dict(audio_seconds=6, device='cuda:0', turns=[dict(start=0, end=6, speaker='group')])
        with tempfile.TemporaryDirectory() as folder, patch('core.diarization.references',
                side_effect=[{'group':'group.wav'}, {'A':'a.wav', 'B':'b.wav'}]), patch(
                    'core.speech_performance.measure', return_value={}):
            refined, mapping = assign(AudioSegment.silent(duration=6000), transcript, result, Path(folder), 'test')
        rows = list(mapping.values())
        self.assertEqual([r['reference'] for r in rows[:2]], ['a.wav', 'b.wav'])
        self.assertEqual(rows[2]['reason'], 'merged_character_group')
        self.assertIsNone(rows[2]['reference'])

    def test_short_misgrouped_reply_does_not_rename_long_voice(self):
        from core.caption_speakers import assign
        from pydub import AudioSegment
        transcript = TranscriptionResult([dict(cue(0, 3, 'こんにちは'), speaker_hint='A'),
            dict(cue(3, 3.3, 'はい'), speaker_hint='B'), cue(3.3, 6, 'こんばんは')], 'ja')
        result = dict(audio_seconds=6, device='cuda:0', turns=[dict(start=0, end=6, speaker='group')])
        with tempfile.TemporaryDirectory() as folder, patch('core.diarization.references',
                side_effect=[{'group':'group.wav'}, {'A':'a.wav'}]), patch(
                    'core.speech_performance.measure', return_value={}):
            _, mapping = assign(AudioSegment.silent(duration=6000), transcript, result, Path(folder), 'test')
        rows = list(mapping.values())
        self.assertEqual(rows[2]['speaker'], 'A')
        self.assertEqual(rows[2]['reference'], 'a.wav')
        self.assertEqual(rows[1]['speaker'], 'B')
        self.assertIsNone(rows[1]['reference'])


if __name__ == '__main__':
    unittest.main()
