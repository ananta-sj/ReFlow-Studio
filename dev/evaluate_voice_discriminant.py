"""Offline supervised voice experiment. Never changes production routing."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
import numpy as np
from core.caption_voice_identity import profiles,unit,cosine

def train(cues,vectors,regularization):
    templates,named=profiles(cues,vectors)
    keys=list(templates)
    indices=[i for i in named]
    x=np.asarray([vectors[i] for i in indices])
    y=np.asarray([[float(named[i]==key) for key in keys] for i in indices])
    weights=x.T@np.linalg.solve(x@x.T+regularization*np.eye(len(indices)),y)
    return templates,keys,weights

def predict(vector,trained,threshold,margin):
    templates,keys,weights=trained
    scores=np.asarray(vector)@weights
    order=np.argsort(scores)[::-1]
    if len(order)<2:return None
    best,second=order[:2]
    # Reject voices outside the known examples, even if the classifier picks a class.
    if scores[best]<threshold or scores[best]-scores[second]<margin:return None
    if cosine(vector,templates[keys[best]]['center'])<.45:return None
    return keys[best]

def main():
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues'];raw={r['cue_id']:unit(r['vector']) for r in data['result']['cue_embeddings']}
    vectors={i:raw[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in raw}
    held=[i for i,c in enumerate(cues) if c.get('speaker_hint') and not c.get('speaker_collective')
          and not c.get('multiple_caption_speakers') and i in vectors
          and sum(row.get('speaker_hint')==c['speaker_hint'] for row in cues)>1]
    reports=[]
    for regularization in (.1,1.,10.):
        trials={}
        for index in held:
            hidden=copy.deepcopy(cues);hidden[index].pop('speaker_hint',None)
            trials[index]=train(hidden,vectors,regularization)
        full=train(cues,vectors,regularization)
        for threshold in (.4,.6,.8):
            for margin in (.15,.3):
                rows=[]
                for index in held:
                    key=predict(vectors[index],trials[index],threshold,margin)
                    rows.append(dict(index=index,expected=cues[index]['speaker_hint'],
                        predicted=trials[index][0][key]['label'] if key else None))
                reports.append(dict(regularization=regularization,threshold=threshold,margin=margin,
                    correct=sum(r['expected']==r['predicted'] for r in rows),
                    wrong=sum(r['predicted'] is not None and r['expected']!=r['predicted'] for r in rows),
                    rejected=sum(r['predicted'] is None for r in rows),
                    assigned=sum(predict(v,full,threshold,margin) is not None for v in vectors.values()),
                    held_out=rows))
    destination=ROOT/'docs/validation/2026-11-15-voice-discriminant.json'
    blocked=[]
    for regularization,threshold,margin in ((.1,.4,.15),(.1,.4,.3),(.1,.6,.15)):
        windows={};rows=[]
        for index in held:
            block=int(cues[index]['start']//60)
            if block not in windows:
                hidden=copy.deepcopy(cues)
                for cue in hidden:
                    if int(cue['start']//60)==block:cue.pop('speaker_hint',None)
                windows[block]=train(hidden,vectors,regularization)
            model=windows[block];key=predict(vectors[index],model,threshold,margin)
            rows.append(dict(index=index,expected=cues[index]['speaker_hint'],predicted=model[0][key]['label'] if key else None))
        scene=[];model=train(cues,vectors,regularization)
        mothers={25,27,28,32,37,38}
        for index in range(25,39):
            key=predict(vectors[index],model,threshold,margin) if index in vectors else None
            scene.append(dict(index=index,expected='マリ' if index in mothers else 'ペリーヌ',predicted=model[0][key]['label'] if key else None))
        blocked.append(dict(regularization=regularization,threshold=threshold,margin=margin,
            correct=sum(r['expected']==r['predicted'] for r in rows),
            wrong=sum(r['predicted'] is not None and r['expected']!=r['predicted'] for r in rows),
            rejected=sum(r['predicted'] is None for r in rows),held_out=rows,scene=scene))
    destination.write_text(json.dumps(dict(production_changed=False,candidates=reports,
        withheld_minute_blocks=blocked,
        caveat='Threshold exploration on cached evidence, not independent acceptance or proof of unseen actor identity.'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in row.items() if k!='held_out'} for row in reports]))
    print(json.dumps([{k:v for k,v in row.items() if k!='held_out'} for row in blocked],ensure_ascii=True))

if __name__=='__main__':main()
