"""Coqui 0.27.5 compatibility for the pinned modern CUDA engine."""
from functools import wraps
from importlib.metadata import version


def activate():
    import torch
    import transformers
    from transformers import pytorch_utils
    if (torch.__version__ != '2.14.1+cu130' or transformers.__version__ != '5.19.0'
            or version('coqui-tts') != '0.27.5'):
        raise RuntimeError('Unsupported CUDA XTTS package versions')
    if hasattr(pytorch_utils, 'isin_mps_friendly'):
        raise RuntimeError('Revalidate the CUDA XTTS compatibility recipe')
    pytorch_utils.isin_mps_friendly = torch.isin
    from TTS.tts.layers.xtts.gpt_inference import GPT2InferenceModel
    generate = GPT2InferenceModel.generate
    prepare = GPT2InferenceModel.prepare_inputs_for_generation

    @wraps(generate)
    def dense_generate(self, *args, **kwargs):
        inputs = args[0] if args else kwargs.get('inputs')
        if kwargs.get('attention_mask') is None:
            if not isinstance(inputs, torch.Tensor) or inputs.ndim != 2:
                raise ValueError('XTTS requires dense token inputs')
            kwargs['attention_mask'] = torch.ones_like(inputs, dtype=torch.long)
        if kwargs['attention_mask'].ndim != 2 or not bool(torch.all(kwargs['attention_mask'] == 1)):
            raise ValueError('XTTS requires an unpadded token sequence')
        return generate(self, *args, **kwargs)

    @wraps(prepare)
    def dense_prepare(self, input_ids, *args, attention_mask=None, **kwargs):
        if attention_mask is None:
            if input_ids.ndim != 2:
                raise ValueError('XTTS token mask could not be recovered')
            attention_mask = torch.ones_like(input_ids, dtype=torch.long)
        values = prepare(self, input_ids, *args, attention_mask=attention_mask, **kwargs)
        values['attention_mask'] = attention_mask
        return values

    GPT2InferenceModel.generate = dense_generate
    GPT2InferenceModel.prepare_inputs_for_generation = dense_prepare
    import soundfile
    from torchaudio.functional import resample
    from TTS.tts.models import xtts

    def reference_audio(path, sampling_rate):
        samples, input_rate = soundfile.read(path, dtype='float32', always_2d=True)
        audio = torch.from_numpy(samples.T).mean(dim=0, keepdim=True)
        if not audio.numel() or not bool(torch.isfinite(audio).all()):
            raise ValueError('Invalid XTTS reference audio')
        if input_rate != sampling_rate:
            audio = resample(audio, input_rate, sampling_rate)
        return audio.clamp_(-1, 1)

    xtts.load_audio = reference_audio
