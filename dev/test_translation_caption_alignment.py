import unittest
from core.translation_caption_alignment import align


class CaptionAlignmentTests(unittest.TestCase):
    def test_tiny_boundary_rounding_does_not_append_the_next_speakers_words(self):
        proposals,issues=align([dict(start=1,end=2),dict(start=2,end=4)],
            [dict(start=1,end=1.95,text='Yes.'),dict(start=1.95,end=4,text='Next person.')])
        self.assertFalse(issues)
        self.assertEqual(proposals[0]['text'],'Yes.')
        self.assertEqual(proposals[1]['text'],'Next person.')

    def test_complete_grouped_turn_uses_human_caption_evidence_with_provenance(self):
        source=[dict(start=1,end=5,text='原文')]
        proposals,issues=align(source,[dict(start=.9,end=3,text='First.'),dict(start=3,end=5.1,text='Second.')])
        self.assertFalse(issues)
        self.assertEqual(proposals[0]['text'],'First. Second.')
        self.assertEqual(proposals[0]['original_source_text'],'原文')
        self.assertFalse(proposals[0]['meaning_verified'])

    def test_caption_spanning_two_characters_is_not_duplicated_or_guessed(self):
        proposals,issues=align([dict(start=0,end=2),dict(start=2,end=4)],
            [dict(start=0,end=4,text='Two different characters')])
        self.assertFalse(proposals)
        self.assertEqual(set(issues),{0,1})

    def test_uncovered_dialogue_and_large_offset_require_review(self):
        proposals,issues=align([dict(start=1,end=7,text='Source')],[dict(start=3,end=4,text='Incomplete')])
        self.assertFalse(proposals)
        self.assertEqual(issues[0],'auxiliary_caption_timing_uncertain')


if __name__=='__main__':unittest.main()
