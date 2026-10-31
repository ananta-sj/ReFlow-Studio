"""Evaluation-only adapter for Coqui 0.27.5's removed Transformers import.

Uses the supported native Torch operation; changes no third-party source and
restores no obsolete generation/checkpoint-loading implementation.
"""
from importlib import metadata
from pathlib import Path
import sys
from functools import wraps

def activate():
    profile=Path(sys.executable).resolve().parent
    assert profile.name=='xtts-security-candidate'
    assert (profile/'.owner').read_text()=='reflow.xtts.security-candidate.2026-10-13'
    import torch
    import transformers
    from transformers import pytorch_utils
    assert torch.__version__=='2.14.1+cpu' and torch.version.cuda is None
    assert transformers.__version__=='5.19.0' and metadata.version('coqui-tts')=='0.27.5'
    assert not hasattr(pytorch_utils,'isin_mps_friendly'),'Re-evaluate the shim if upstream restores this name'
    elements=torch.tensor([1,2,3,2])
    assert torch.isin(elements,torch.tensor([2,4])).tolist()==[False,True,False,True]
    assert torch.isin(elements,2).tolist()==[False,True,False,True]
    pytorch_utils.isin_mps_friendly=torch.isin
    # Transformers 5 no longer synthesizes this mask for Coqui's custom GPT
    # wrapper. Its prefix/text/audio input is dense, so every input is visible.
    from TTS.tts.layers.xtts.gpt_inference import GPT2InferenceModel
    original_generate=GPT2InferenceModel.generate
    @wraps(original_generate)
    def generate_with_dense_mask(self,*args,**kwargs):
        inputs=args[0] if args else kwargs.get('inputs')
        if kwargs.get('attention_mask') is None:
            if not isinstance(inputs,torch.Tensor) or inputs.ndim!=2 or inputs.device.type!='cpu':
                raise ValueError('The XTTS evaluation adapter requires explicit dense CPU token inputs')
            kwargs['attention_mask']=torch.ones_like(inputs,dtype=torch.long)
        if kwargs['attention_mask'].ndim!=2 or not bool(torch.all(kwargs['attention_mask']==1)):
            raise ValueError('The evaluation adapter supports unpadded dense XTTS sequences only')
        return original_generate(self,*args,**kwargs)
    GPT2InferenceModel.generate=generate_with_dense_mask
    original_prepare=GPT2InferenceModel.prepare_inputs_for_generation
    @wraps(original_prepare)
    def prepare_with_explicit_mask(self,input_ids,*args,attention_mask=None,**kwargs):
        if attention_mask is None:
            # generate() elides the all-ones mask before prefill. At this
            # boundary input_ids still contains the complete growing sequence.
            if input_ids.ndim!=2 or input_ids.device.type!='cpu':
                raise ValueError('Cannot recover the dense XTTS sequence mask')
            attention_mask=torch.ones_like(input_ids,dtype=torch.long)
        if attention_mask.ndim!=2:
            raise ValueError('XTTS requires the original two-dimensional token mask')
        values=original_prepare(self,input_ids,*args,attention_mask=attention_mask,**kwargs)
        # The modern fast path may omit an all-visible mask. Coqui also uses
        # its full length to select the learned audio-token position embedding.
        values['attention_mask']=attention_mask
        return values
    GPT2InferenceModel.prepare_inputs_for_generation=prepare_with_explicit_mask
    return dict(activated=True,legacy_import='transformers.pytorch_utils.isin_mps_friendly',
        native_operation='torch.isin',explicit_dense_attention_mask=True,preserve_mask_for_position_embedding=True,
        third_party_files_modified=False,scope='exact CPU evaluation stack only')
