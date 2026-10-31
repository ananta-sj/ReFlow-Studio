"""Offline GPU recognition using the exact previously evaluated ASR model."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def session(params):
    import numpy as np
    import soundfile as sf
    import torch
    import transformers
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, StoppingCriteria
    from core.whisper_turbo_assets import validate_assets
    from core.render_context import run_process
    from core.transcription import TranscriptionResult, require_media_bounds
    from core.whisper_completion import require_finished_decoder
    contract = validate_assets(params['model_path'],verify_weights=True)
    if (torch.__version__ != '2.9.1+cu128' or transformers.__version__ != '5.18.0'
            or not torch.cuda.is_available()):
        raise RuntimeError('Whisper turbo requires the existing verified NVIDIA GPU runtime.')
    torch.set_num_threads(2)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(contract['model_path'],local_files_only=True,
        use_safetensors=True).to('cuda:0').eval()
    processor = AutoProcessor.from_pretrained(contract['model_path'],local_files_only=True)
    folder = Path(params['session_dir'])
    def check_stop(*_):
        if (folder/'stop').exists():
            raise RuntimeError('Whisper recognition cancelled.')
    class Stop(StoppingCriteria):
        def __call__(self,*args,**kwargs):
            check_stop()
            return False
    hook = model.model.decoder.register_forward_pre_hook(check_stop)
    print(json.dumps(dict(engine='whisper_turbo',stage='model-ready',dtype=str(model.dtype))),flush=True)
    last = 0
    try:
        while not (folder/'stop').exists():
            for request in sorted(folder.glob('call-????????.json')):
                sequence = int(request.stem[5:])
                if sequence <= last:
                    continue
                response = dict(ok=False,engine='whisper_turbo',worker_pid=os.getpid(),sequence=sequence)
                try:
                    call = json.loads(request.read_text(encoding='utf-8'))
                    from core.recognition_language import whisper_language
                    hint = whisper_language(call.get('source_language', 'auto'))
                    if hint and f'<|{hint}|>' not in model.generation_config.lang_to_id:
                        raise ValueError(f'This Whisper model does not support source language {hint!r}.')
                    audio = folder/'source-16k.wav'
                    run_process(['ffmpeg','-v','error','-nostdin','-y','-i',call['audio_path'],
                        '-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(audio)],check=True,timeout=1800)
                    samples, rate = sf.read(audio,dtype='float32')
                    if rate != 16000 or samples.ndim != 1 or not len(samples) or not np.isfinite(samples).all():
                        raise ValueError('Invalid decoded recognition audio.')
                    duration = len(samples)/rate
                    cues, blocks = [], []
                    for first in range(0,len(samples),30*rate):
                        check_stop()
                        block = samples[first:first+30*rate]
                        if not np.max(np.abs(block)):
                            blocks.append(dict(start=first/rate,digital_silence=True))
                            continue
                        inputs = processor.feature_extractor(block,sampling_rate=rate,return_tensors='pt',
                            return_attention_mask=True).to('cuda:0')
                        inputs['input_features'] = inputs['input_features'].to(dtype=model.dtype)
                        # Same masked first-decoder-step language scores as upstream
                        # detect_language, retaining the probability instead of inventing it.
                        language_ids = list(model.generation_config.lang_to_id.values())
                        with torch.inference_mode():
                            decoder = torch.tensor([[model.generation_config.decoder_start_token_id]],device='cuda:0')
                            logits = model(input_features=inputs['input_features'],decoder_input_ids=decoder,
                                           use_cache=False).logits[0,-1,language_ids].float()
                            probabilities = logits.softmax(-1)
                            best = int(probabilities.argmax())
                            token = language_ids[best]
                            confidence = float(probabilities[best])
                            label = processor.tokenizer.convert_ids_to_tokens(token)[2:-2]
                            generated = model.generate(**inputs,task='transcribe',language=hint or label,return_timestamps=True,
                                return_dict_in_generate=True,return_segments=True,output_scores=True,
                                max_new_tokens=440,do_sample=False,stopping_criteria=[Stop()])
                        tokens = generated['sequences']
                        decoder_checks = []
                        for segment in generated['segments'][0]:
                            underlying = segment['result']
                            steps = len(underlying['scores'])
                            require_finished_decoder(underlying['sequences'],steps,processor.tokenizer.eos_token_id)
                            decoder_checks.append(dict(generated_steps=steps,ended_with_eos=True))
                        decoded = processor.tokenizer.decode(tokens[0].tolist(),skip_special_tokens=True,output_offsets=True)
                        blocks.append(dict(start=first/rate,language=label,probability=confidence,
                                           decoder_completion=decoder_checks,**decoded))
                        for item in decoded.get('offsets',[]):
                            begin, end = item['timestamp']
                            text = item['text'].strip()
                            if begin is None or end is None or not text:
                                raise ValueError('Whisper returned an incomplete timed phrase.')
                            absolute_start = first/rate+begin
                            absolute_end = min(first/rate+end,(first+len(block))/rate)
                            if not 0 <= absolute_start < absolute_end <= duration:
                                raise ValueError('Whisper returned timestamps outside decoded audio.')
                            cues.append(dict(start=absolute_start,end=absolute_end,text=text,
                                asr_block_boundary=bool(first and begin == 0)))
                        print(json.dumps(dict(engine='whisper_turbo',stage='recognized',start=first/rate)),flush=True)
                    spoken = [row for row in blocks if not row.get('digital_silence')]
                    languages = {row['language'] for row in spoken}
                    language = next(iter(languages)) if len(languages) == 1 else None
                    probability = min(row['probability'] for row in spoken) if language else None
                    result = TranscriptionResult(cues,hint or language,probability,'hint' if hint else None)
                    require_media_bounds(result,duration)
                    response.update(ok=True,transcription=result.to_payload(),blocks=blocks,duration_seconds=duration,
                                    language_probability_basis='minimum masked language-token probability across 30-second blocks',
                                    recognition_dtype=str(model.dtype),model_revision=contract['revision'])
                except Exception:
                    response['error'] = traceback.format_exc()[-6000:]
                pending = request.with_suffix('.response.tmp')
                pending.write_text(json.dumps(response,ensure_ascii=False),encoding='utf-8')
                os.replace(pending,request.with_suffix('.response.json'))
                last = sequence
            time.sleep(.05)
    finally:
        hook.remove()


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request['operation'] != 'whisper_turbo_session':
        raise ValueError('Unsupported Whisper operation.')
    session(request['params'])
