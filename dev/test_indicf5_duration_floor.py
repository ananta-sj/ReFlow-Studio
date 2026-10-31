"""Explicit short-utterance budgets do not alter default calibrated durations."""
import unittest
from core.indicf5_duration import sentence_hops,validate_minimum_sentence_seconds,segment_text


class DurationMathTests(unittest.TestCase):
    def test_continuous_mode_keeps_question_with_context_and_default_is_unchanged(self):
        text='ऊब गए? जगाने को ये एनिमेटेड चार्ट।'
        self.assertEqual(segment_text(text),['ऊब गए?','जगाने को ये एनिमेटेड चार्ट।'])
        self.assertEqual(segment_text(text,True),[text])
        self.assertEqual(segment_text(text),['ऊब गए?','जगाने को ये एनिमेटेड चार्ट।'])

    def test_invalid_continuous_mode_and_text_fail(self):
        for value in ['true',1,None]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                segment_text('hello',value)
        for value in ['',None,'x'*4001]:
            with self.assertRaises(ValueError):
                segment_text(value,True)
    def test_default_exactly_preserves_existing_hop_formula(self):
        profile=dict(calibration_seconds=7.744,calibration_text='A calibration sentence.')
        for text in ['ऊब गए?','hello','a much longer sentence.'*40]:
            expected=max(1,round(7.744*len(text.encode('utf-8'))/len(profile['calibration_text'].encode('utf-8'))*24000/256))
            self.assertEqual(sentence_hops(text,profile),expected)
        self.assertEqual(profile,dict(calibration_seconds=7.744,calibration_text='A calibration sentence.'))

    def test_floor_rounds_up_and_cannot_shorten_longer_native_speech(self):
        profile=dict(calibration_seconds=1,calibration_text='x'*100)
        self.assertGreaterEqual(sentence_hops('x',profile,minimum_sentence_seconds=.9)*256/24000,.9)
        self.assertEqual(sentence_hops('x'*200,profile,minimum_sentence_seconds=.9),sentence_hops('x'*200,profile))

    def test_invalid_floor_is_rejected(self):
        for value in [True,False,'1',0,-1,.09,5.01,float('nan'),float('inf')]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_minimum_sentence_seconds(value)


