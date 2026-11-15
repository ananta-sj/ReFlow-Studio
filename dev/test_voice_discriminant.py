import math,unittest
from unittest.mock import patch
from core.voice_discriminant import train,propose
from core.caption_voice_identity import choose_cues

class VoiceDiscriminantTests(unittest.TestCase):
    def fixture(self):
        templates={'a':dict(label='Alice',indices=[0,1],center=[1.,0.,0.],generic=False),
                   'b':dict(label='Bob',indices=[2,3],center=[0.,1.,0.],generic=False)}
        vectors={0:[1.,0.,0.],1:[1.,0.,0.],2:[0.,1.,0.],3:[0.,1.,0.]}
        return templates,vectors

    def test_known_voices_match_but_unseen_and_ambiguous_voices_are_rejected(self):
        templates,vectors=self.fixture();model=train(templates,vectors)
        self.assertEqual(propose([1.,0.,0.],model)[0],'a')
        self.assertEqual(propose([0.,1.,0.],model)[0],'b')
        self.assertIsNone(propose([0.,0.,1.],model)[0])
        self.assertIsNone(propose([2**-.5,2**-.5,0.],model)[0])
        with self.assertRaises(ValueError):propose([float('nan'),0.,0.],model)

    def test_requires_multiple_original_examples_of_multiple_named_characters(self):
        templates,vectors=self.fixture();templates['b']['indices']=[2]
        self.assertIsNone(train(templates,vectors))
        templates['b']['indices']=[2,3];templates['b']['generic']=True
        self.assertIsNone(train(templates,vectors))

    def test_short_mixed_and_explicitly_labelled_cues_do_not_use_fallback(self):
        templates,_=self.fixture()
        cues=[dict(start=i*4,end=i*4+2,text='Line') for i in range(4)]
        cues[1]['end']=4.8;cues[2]['multiple_caption_speakers']=True;cues[3]['speaker_hint']='Unknown'
        vectors={i:[.5,.4,math.sqrt(.59)] for i in range(4)}
        with patch('core.voice_discriminant.train',return_value={}),patch('core.voice_discriminant.propose',return_value=('a',dict(method='labelled_source_discriminant'))) as propose_mock:
            choices,_=choose_cues(cues,vectors,templates,{})
        self.assertEqual(choices,{0:'a',1:None,2:None,3:None})
        self.assertEqual(propose_mock.call_count,1)

    def test_proposed_identity_cannot_train_or_promote_another_cue(self):
        templates,_=self.fixture()
        cues=[dict(start=i*10,end=i*10+2,text='Line') for i in range(3)]
        vector=[.56,.1,math.sqrt(1-.56**2-.1**2)]
        vectors={0:vector,1:vector,2:[1.,0.,0.]}
        with patch('core.voice_discriminant.train',return_value={}),patch('core.voice_discriminant.propose',side_effect=[('a',dict(method='labelled_source_discriminant')),(None,{})]):
            choices,_=choose_cues(cues,vectors,templates,{})
        self.assertEqual(choices[0],'a');self.assertIsNone(choices[1]);self.assertEqual(choices[2],'a')

if __name__=='__main__':unittest.main()
