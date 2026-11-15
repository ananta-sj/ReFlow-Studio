"""Test voice evidence without zero-padding variable-length caption audio."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYANNOTE_METRICS_ENABLED='0',OMP_NUM_THREADS='2')


def main():
    import pandas
    import torch
    import numpy as np
    import soundfile
    from pyannote.audio import Pipeline
    from core.render_context import RenderContext,bind_job,run_process
    from core.diarization_runtime import validate
    from core.caption_voice_identity import profiles,match,unit
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues']; job=RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            source=next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
            audio=job.workspace/'source.wav'
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-i',str(source),'-vn','-ar','16000','-ac','1',str(audio)],check=True,timeout=120)
            waveform=torch.from_numpy(soundfile.read(audio,dtype='float32')[0])[None,:]
            torch.set_num_threads(2)
            pipeline=Pipeline.from_pretrained(validate()['model']).to(torch.device('cuda:0'))
            vectors={}; records=[]
            for index,cue in enumerate(cues):
                clip=waveform[:,round(cue['start']*16000):min(round(cue['end']*16000),round(cue['start']*16000)+96000)]
                if clip.shape[-1]<10400: continue
                embedding=pipeline._embedding(clip[None,:,:])[0]
                if not np.isfinite(embedding).all() or np.linalg.norm(embedding)==0: continue
                vectors[index]=unit(embedding.tolist())
                records.append(dict(index=index,cue_id=cue['cue_id'],vector=vectors[index]))
                if index%60==0: print('Source cue',index,flush=True)
            padding=[]
            for index in (20,25,26,27,28,29,32,37,38,161):
                cue=cues[index]; clip=waveform[:,round(cue['start']*16000):round(cue['end']*16000)]
                values=torch.zeros((1,1,96000)); masks=torch.zeros((1,96000))
                values[:,:,:clip.shape[-1]]=clip; masks[:,:clip.shape[-1]]=1
                vector=unit(pipeline._embedding(values,masks=masks)[0].tolist())
                padding.append(dict(index=index,cosine_same_audio_different_padding=sum(a*b for a,b in zip(vector,vectors[index]))))
            named=[i for i,c in enumerate(cues) if c.get('speaker_hint') and not c.get('speaker_collective') and i in vectors]
            held=[]
            for index in named:
                if sum(cues[i]['speaker_hint']==cues[index]['speaker_hint'] for i in named)<2:continue
                templates,_=profiles(cues,vectors,{index}); key,score,margin=match(vectors[index],templates)
                held.append(dict(index=index,expected=cues[index]['speaker_hint'],predicted=templates[key]['label'] if key else None,score=score,margin=margin))
            templates,_=profiles(cues,vectors)
            scene=[]
            for i,cue in enumerate(cues):
                if cue['start']<267 and cue['end']>214 and i in vectors:
                    key,score,margin=match(vectors[i],templates)
                    scene.append(dict(index=i,start=cue['start'],text=cue['text'],predicted=templates[key]['label'] if key else None,score=score,margin=margin))
            report=dict(padding=padding,held_out=held,scene=scene,vectors=records,
                correct=sum(r['predicted']==r['expected'] for r in held),rejected=sum(r['predicted'] is None for r in held),
                wrong=sum(r['predicted'] is not None and r['predicted']!=r['expected'] for r in held))
            (ROOT/'docs/validation/2026-11-14-unpadded-source-voices.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:report[k] for k in ('correct','rejected','wrong','padding')}),flush=True)
    finally: job.cleanup()


if __name__=='__main__': main()
