import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.batch_speakers import group_vectors, analyze
from core.failure_diagnostics import summarize
from core.stage_checkpoints import stage_code_identity


class BatchCharacterTests(unittest.TestCase):
    def test_complete_linkage_does_not_chain_different_voices(self):
        labels, _ = group_vectors([[1, 0], [.9, .1], [0, 1], [.1, .9]])
        self.assertEqual(labels, ['Speaker 1', 'Speaker 1', 'Speaker 2', 'Speaker 2'])

    def test_nonfinite_embedding_is_rejected(self):
        with self.assertRaises(ValueError):
            group_vectors([[float('nan'), 1]])

    def test_repeated_speakers_receive_distinct_source_references(self):
        from pydub.generators import Sine
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            audio = sum([Sine(hz).to_audio_segment(duration=1800) for hz in (150, 350, 150, 350)])
            source = folder/'source.wav'
            audio.export(source, format='wav').close()
            cues = [dict(cue_id=str(i), start=i*1.8, end=(i+1)*1.8) for i in range(4)]
            import numpy as np
            vectors = iter([np.array([1., 0.]), np.array([0., 1.]), np.array([1., 0.]), np.array([0., 1.])])
            result = analyze(source, cues, folder, lambda clip: next(vectors))
            self.assertEqual(len(result['speakers']), 2)
            refs = [row['reference'] for row in result['cues']]
            self.assertEqual(refs[0], refs[2])
            self.assertEqual(refs[1], refs[3])
            self.assertNotEqual(refs[0], refs[1])

    def test_export_edit_does_not_invalidate_inference_code(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project/'core').mkdir()
            original = (root/'core/pipeline.py').read_text(encoding='utf-8')
            path = project/'core/pipeline.py'
            path.write_text(original, encoding='utf-8')
            before = {stage: stage_code_identity(project, stage) for stage in ('stt', 'translation')}
            path.write_text(original.replace("ffmpeg_preset=\"slow\"", "ffmpeg_preset=\"veryfast\""), encoding='utf-8')
            self.assertEqual(before, {stage: stage_code_identity(project, stage) for stage in before})
            path.write_text(original.replace("source_language = normalize_source_selection(source_language)", "source_language = str(source_language)"), encoding='utf-8')
            self.assertNotEqual(before['stt'], stage_code_identity(project, 'stt'))

    def test_failure_message_is_retained_without_service_credentials(self):
        result = summarize(RuntimeError('Segment 7 failed: token=secret123 https://host/private'))
        self.assertIn('Segment 7 failed', result['message'])
        self.assertNotIn('secret123', result['message'])
        self.assertNotIn('https://host', result['message'])

    def test_large_source_block_is_split_at_pauses(self):
        from pydub import AudioSegment
        from pydub.generators import Sine
        from core.batch_speakers import pause_turns
        audio = Sine(220).to_audio_segment(duration=1600)+AudioSegment.silent(duration=400)+Sine(350).to_audio_segment(duration=1600)
        turns = pause_turns(audio, 0, 3.6)
        self.assertEqual(len(turns), 2)
        self.assertAlmostEqual(turns[0][1], turns[1][0])

    def test_runaway_translation_is_rejected_for_multiple_languages(self):
        from core.dialogue_integrity import require_reasonable, DialogueIntegrityReviewRequired
        for phrase in ('देखो, ', 'all right, ', 'd’accord, ', 'はい、'):
            with self.subTest(phrase=phrase), self.assertRaises(DialogueIntegrityReviewRequired):
                require_reasonable('A short source line.', phrase*100)

    def test_short_repeated_hindi_syllables_are_rejected(self):
        from core.dialogue_integrity import require_reasonable, DialogueIntegrityReviewRequired
        with self.assertRaises(DialogueIntegrityReviewRequired):
            require_reasonable('こら バロン ダメだったら フフフッ',
                'मैं बैरन हूँ, अगर नहीं होता तो फ़फ़फ़फ़फफ़फ़')
        self.assertEqual(require_reasonable('え?', 'क्या?'), 'क्या?')

    def test_short_emphasis_and_normal_language_expansion_are_allowed(self):
        from core.dialogue_integrity import require_reasonable
        self.assertEqual(require_reasonable('No!', 'नहीं, नहीं, नहीं!'), 'नहीं, नहीं, नहीं!')
        self.assertEqual(require_reasonable('え?', 'क्या?'), 'क्या?')

    def test_readback_flags_gibberish(self):
        from core.batch_intelligibility import similarity
        self.assertGreater(similarity('मैं तेरह साल का हूँ।', 'मैं तेरह साल का हूं', 'hi'), .75)
        self.assertLess(similarity('मैं तेरह साल का हूँ।', 'बला लोला लाला', 'hi'), .55)

    def test_ordinary_sentences_are_not_retried_word_by_word(self):
        from core.dialogue_integrity import recovery_parts
        self.assertEqual(recovery_parts('Please come over here now'), [])

    def test_short_turn_padding_does_not_extend_the_dialogue_timeline(self):
        from pydub import AudioSegment
        from pydub.generators import Sine
        from core.batch_speakers import refine_turns
        from core.transcription import TranscriptionResult
        from core.render_context import RenderContext, bind_job
        with tempfile.TemporaryDirectory() as folder:
            job = RenderContext(folder)
            source = job.workspace/'source.wav'
            audio = Sine(220).to_audio_segment(duration=1600)+AudioSegment.silent(duration=400)+Sine(350).to_audio_segment(duration=1600)
            audio.export(source, format='wav').close()
            provider = Mock()
            def recognize(paths, language):
                self.assertTrue(all(len(AudioSegment.from_wav(path)) >= 3000 for path in paths))
                return [[dict(start=0, end=1.6, text='こんにちは')] for path in paths]
            provider.transcribe_takes.side_effect = recognize
            try:
                with bind_job(job):
                    result = refine_turns(source, TranscriptionResult([dict(start=0, end=3.6, text='こんにちは')], 'ja'), provider)
                self.assertEqual(len(result), 2)
                self.assertAlmostEqual(result[-1]['end'], 3.6)
            finally:
                job.cleanup()

    def test_unreasonable_text_is_rejected_even_if_asr_repeated_it(self):
        from core.dialogue_integrity import require_speech_window, DialogueIntegrityReviewRequired
        with self.assertRaises(DialogueIntegrityReviewRequired):
            require_speech_window('hello '*100, 3)

    def test_shared_translation_guard_recovers_without_passing_loop_to_speech(self):
        from core.pipeline import ReflowPipeline
        from core.source_language import resolve_source_language
        provider = Mock()
        provider.translate.side_effect = ['देखो, '*100, 'देखो।', 'वह वहाँ है।']
        output = ReflowPipeline._translate_line('ほら あそこから見てるもの', 'Hindi', provider,
            '', None, '', source_language=resolve_source_language('ja'))
        self.assertEqual(output, 'देखो। वह वहाँ है।')
        self.assertEqual(provider.translate.call_count, 3)
