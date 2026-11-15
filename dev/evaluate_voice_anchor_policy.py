"""Measure reference-duration eligibility, without changing production thresholds."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.caption_voice_identity import profiles,match,unit


def evaluate(cues,vectors):
    anchors={i:v for i,v in vectors.items() if cues[i]['end']-cues[i]['start']>=1.5 and not cues[i].get('multiple_caption_speakers')}
    named=[i for i in anchors if cues[i].get('speaker_hint') and not cues[i].get('speaker_collective')]
    reports=[]
    for minimum,margin in ((.6,.08),(.55,.15),(.5,.15),(.5,.2)):
        held=[]
        for index in named:
            if sum(cues[i]['speaker_hint']==cues[index]['speaker_hint'] for i in named)<2:continue
            templates,_=profiles(cues,anchors,{index})
            key,score,difference=match(vectors[index],templates,minimum=minimum,margin=margin)
            held.append(dict(index=index,expected=cues[index]['speaker_hint'],predicted=templates[key]['label'] if key else None,score=score,margin=difference))
        templates,_=profiles(cues,anchors)
        scene=[]
        for index in range(25,39):
            if index not in vectors:continue
            key,score,difference=match(vectors[index],templates,minimum=minimum,margin=margin)
            scene.append(dict(index=index,predicted=templates[key]['label'] if key else None,score=score,margin=difference))
        reports.append(dict(minimum=minimum,margin=margin,correct=sum(r['predicted']==r['expected'] for r in held),
            rejected=sum(r['predicted'] is None for r in held),wrong=sum(r['predicted'] is not None and r['predicted']!=r['expected'] for r in held),
            held_out=held,scene=scene))
    return reports


def main():
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues']; by_id={row['cue_id']:unit(row['vector']) for row in data['result']['cue_embeddings']}
    vectors={i:by_id[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in by_id}
    reports=evaluate(cues,vectors)
    (ROOT/'docs/validation/2026-11-14-voice-anchor-policy.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ('minimum','margin','correct','rejected','wrong')} for r in reports]))


if __name__=='__main__': main()
