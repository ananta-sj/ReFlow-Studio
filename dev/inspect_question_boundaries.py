"""Existing offline ASR and low-energy spans: hints for a reviewed question splice."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')

def main():
    import numpy as np
    import soundfile as sf
    import torch
    from transformers import AutoModelForSpeechSeq2Seq,AutoProcessor
    from core.whisper_turbo_assets import validate_assets
    from core.render_context import run_process
    from core.cue_review import digest
    base=ROOT/'docs/validation'
    output=base/'2026-10-09-question-splice-boundary.json'
    contract=validate_assets(ROOT/'models/f5/reference-asr',verify_weights=True)
    print('Loading installed offline recognizer',flush=True)
    model=AutoModelForSpeechSeq2Seq.from_pretrained(contract['model_path'],local_files_only=True,
        use_safetensors=True,dtype=torch.float16,attn_implementation='eager').to('cuda:0').eval()
    processor=AutoProcessor.from_pretrained(contract['model_path'],local_files_only=True)
    rows=[]
    for name,receipt_name in [('reviewed_rest','2026-10-09-question-context-96ddf6e4.json'),
        ('accepted_question','2026-10-09-question-context-f38f4769.json')]:
        receipt=json.loads((base/receipt_name).read_text(encoding='utf-8'))
        path=Path(receipt['listening']).parent/'continuous-context.wav'
        assert digest(path)==receipt['result']['output_sha256']
        decoded=run_process(['ffmpeg','-v','error','-nostdin','-i',str(path),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True)
        samples=np.frombuffer(decoded.stdout,dtype='<f4').copy()
        inputs=processor.feature_extractor(samples,sampling_rate=16000,return_tensors='pt',return_attention_mask=True).to('cuda:0')
        inputs['input_features']=inputs['input_features'].to(model.dtype)
        with torch.inference_mode():
            generated=model.generate(**inputs,language='hi',task='transcribe',max_new_tokens=160,
                return_timestamps=True,return_token_timestamps=True,return_segments=True,return_dict_in_generate=True)
        timestamps=[torch.cat([seg['token_timestamps'] for seg in segments]).cpu() for segments in generated['segments']]
        transcript,extra=processor.tokenizer._decode_asr([dict(tokens=generated['sequences'].cpu(),token_timestamps=timestamps)],
            return_timestamps='word',return_language=False,time_precision=.02)
        pcm,rate=sf.read(path,dtype='float64')
        assert rate==24000 and pcm.ndim==1
        window=240
        blocks=pcm[:len(pcm)//window*window].reshape(-1,window)
        rms=np.sqrt(np.mean(blocks**2,axis=1))
        db=20*np.log10(np.maximum(rms,1e-10))
        quiet=db<-38
        spans=[]
        start=None
        for i,value in enumerate(list(quiet)+[False]):
            if value and start is None: start=i
            if not value and start is not None:
                if i-start>=3: spans.append(dict(start=start*.01,end=i*.01,seconds=(i-start)*.01))
                start=None
        row=dict(name=name,receipt=receipt_name,audio=str(path),sha256=digest(path),
            transcript=transcript,asr=extra,low_energy_threshold_dbfs=-38,low_energy_spans=spans)
        rows.append(row)
        print(json.dumps(row,ensure_ascii=True),flush=True)
    del model,processor
    torch.cuda.empty_cache()
    output.write_text(json.dumps(dict(completed=True,diagnostic_only=True,forced_alignment=False,
        model_revision=contract['revision'],rows=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output,flush=True)

if __name__=='__main__': main()
