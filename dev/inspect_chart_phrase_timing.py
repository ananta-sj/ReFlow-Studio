"""Use installed Whisper word timestamps as diagnostic hints, not forced alignment."""
import json
import argparse
import os
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tail-only',action='store_true',help='Inspect source 99.16–119.50 seconds, without synthesizing or editing')
    args=parser.parse_args()
    import numpy as np
    import torch
    from transformers import AutoModelForSpeechSeq2Seq,AutoProcessor
    from core.whisper_turbo_assets import validate_assets
    from core.render_context import run_process
    base = ROOT/'docs/validation'
    evidence = base/('2026-10-09-source-tail-word-timing' if args.tail_only else '2026-10-08-chart-phrase-word-timing')
    evidence.mkdir(exist_ok=True)
    prior = json.loads((base/'2026-10-08-spoken-hindi-full-video-887151ac.json').read_text(encoding='utf-8'))
    cue = prior['cues'][11]
    original = Path(prior['directory'])/cue['file']
    with wave.open(str(original),'rb') as audio:
        assert audio.getframerate()==24000 and audio.getnchannels()==1 and audio.getsampwidth()==2
        pcm = audio.readframes(audio.getnframes())
    offset = cue['result']['sentences'][0]['frames']+4800
    frames = cue['result']['sentences'][1]['frames']
    hindi = evidence/'hindi-chart-sentence.wav'
    with wave.open(str(hindi),'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
        audio.writeframes(pcm[offset*2:(offset+frames)*2])
    english = evidence/('source-99p16-to-119p50.wav' if args.tail_only else 'source-90-to-99.wav')
    run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','99.16' if args.tail_only else '90','-i',str(ROOT/'Sample/2.mp4'),'-t','20.34' if args.tail_only else '9','-vn','-ac','1','-ar','16000',str(english)],check=True)
    contract = validate_assets(ROOT/'models/f5/reference-asr',verify_weights=True)
    print('Loading existing offline recognizer',flush=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(contract['model_path'],local_files_only=True,
        use_safetensors=True,dtype=torch.float16,attn_implementation='eager').to('cuda:0').eval()
    processor = AutoProcessor.from_pretrained(contract['model_path'],local_files_only=True)
    rows=[]
    for language,path in ([('en',english)] if args.tail_only else [('hi',hindi),('en',english)]):
        # Decode with the app's bundled FFmpeg; passing filenames to the newer
        # pipeline attempts an unavailable optional TorchCodec DLL on Windows.
        decoded = run_process(['ffmpeg','-v','error','-nostdin','-i',str(path),'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True,check=True)
        samples = np.frombuffer(decoded.stdout,dtype='<f4').copy()
        inputs = processor.feature_extractor(samples,sampling_rate=16000,return_tensors='pt',return_attention_mask=True).to('cuda:0')
        inputs['input_features'] = inputs['input_features'].to(model.dtype)
        with torch.inference_mode():
            generated = model.generate(**inputs,language=language,task='transcribe',max_new_tokens=200,
                return_timestamps=True,return_token_timestamps=True,return_segments=True,return_dict_in_generate=True)
        timestamps = [torch.cat([segment['token_timestamps'] for segment in segments]).cpu() for segments in generated['segments']]
        text,extra = processor.tokenizer._decode_asr([dict(tokens=generated['sequences'].cpu(),token_timestamps=timestamps)],
            return_timestamps='word',return_language=False,time_precision=.02)
        result = dict(text=text,**extra)
        rows.append(dict(language=language,audio=str(path),result=result))
        print(language,json.dumps(result,ensure_ascii=True),flush=True)
    output = evidence.with_suffix('.json')
    output.write_text(json.dumps(dict(diagnostic_only=True,forced_alignment=False,source_offset_seconds=99.16 if args.tail_only else 90,model_revision=contract['revision'],rows=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output,flush=True)


if __name__=='__main__':
    main()
