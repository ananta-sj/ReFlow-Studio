"""Offline experiment only: multiple source voice styles with held-out labels."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
import core.caption_voice_identity as policy

def candidate(vector,templates,*,minimum=.60,margin=.08):
    scores=[]
    for key,profile in templates.items():
        similarities=sorted((policy.cosine(vector,v) for v in profile['prototypes']),reverse=True)
        score=policy.cosine(vector,profile['center'])
        if len(similarities)>=2:score=max(score,sum(similarities[:2])/2)
        scores.append((key,score))
    scores.sort(key=lambda row:row[1],reverse=True)
    if not scores:return None,0.,0.
    best,score=scores[0]
    other=next((s for key,s in scores[1:] if templates[best]['generic'] or templates[key]['label']!=templates[best]['label']),-1.)
    return (best if score>=minimum and score-other>=margin else None),score,score-other

def main():
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues'];raw={r['cue_id']:policy.unit(r['vector']) for r in data['result']['cue_embeddings']}
    vectors={i:raw[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in raw}
    def profiles(rows):
        templates,named=policy.profiles(rows,vectors)
        for profile in templates.values():profile['prototypes']=[vectors[i] for i in profile['indices']]
        return templates,named
    policy.match=candidate
    templates,named=profiles(cues);assigned,_=policy.choose_cues(cues,vectors,templates,named)
    held=[]
    for index,cue in enumerate(cues):
        if not cue.get('speaker_hint') or cue.get('speaker_collective') or cue.get('multiple_caption_speakers') or index not in vectors:continue
        if sum(c.get('speaker_hint')==cue['speaker_hint'] for c in cues)<2:continue
        hidden=copy.deepcopy(cues);hidden[index].pop('speaker_hint',None)
        templates,named=profiles(hidden);choices,_=policy.choose_cues(hidden,vectors,templates,named)
        held.append(dict(index=index,expected=cue['speaker_hint'],predicted=templates[choices[index]]['label'] if choices[index] else None))
    report=dict(assigned=sum(v is not None for v in assigned.values()),
        correct=sum(r['expected']==r['predicted'] for r in held),
        wrong=sum(r['predicted'] is not None and r['expected']!=r['predicted'] for r in held),
        rejected=sum(r['predicted'] is None for r in held),held_out=held,production_changed=False,
        caveat='Caption labels are limited evidence; generic role labels do not establish actor identity.')
    (ROOT/'docs/validation/2026-11-15-voice-prototypes.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='held_out'}))

if __name__=='__main__':main()
