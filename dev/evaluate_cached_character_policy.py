"""Validate updated routing against cached real source vectors, with labels held out."""
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.caption_voice_identity import unit,profiles,choose_cues


def main(destination=None,algorithm='centroid with labelled-source fallback'):
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues']; by_id={r['cue_id']:unit(r['vector']) for r in data['result']['cue_embeddings']}
    vectors={i:by_id[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in by_id}
    templates,named=profiles(cues,vectors)
    choices,evidence=choose_cues(cues,vectors,templates,named)
    held=[]
    for index,cue in enumerate(cues):
        if (not cue.get('speaker_hint') or cue.get('speaker_collective') or cue.get('multiple_caption_speakers')
                or index not in vectors or sum(c.get('speaker_hint')==cue['speaker_hint'] for c in cues)<2): continue
        hidden=copy.deepcopy(cues); hidden[index].pop('speaker_hint',None)
        trial,anchors=profiles(hidden,vectors)
        routed,_=choose_cues(hidden,vectors,trial,anchors)
        key=routed[index]
        held.append(dict(index=index,expected=cue['speaker_hint'],predicted=trial[key]['label'] if key else None))
    report=dict(algorithm=algorithm,source_cues=len(cues),assigned=sum(bool(v) for v in choices.values()),
        correct=sum(r['expected']==r['predicted'] for r in held),rejected=sum(r['predicted'] is None for r in held),
        wrong=sum(r['predicted'] is not None and r['expected']!=r['predicted'] for r in held),held_out=held,
        scene=[dict(index=i,start=cues[i]['start'],speaker=templates[choices[i]]['label'] if choices[i] else None,
            evidence=evidence[i]) for i in range(25,39)],human_quality_accepted=False)
    blocked=[]
    for row in held:
        index=row['index'];minute=int(cues[index]['start']//60)
        hidden=copy.deepcopy(cues)
        for cue in hidden:
            if int(cue['start']//60)==minute:cue.pop('speaker_hint',None)
        trial,anchors=profiles(hidden,vectors);routed,_=choose_cues(hidden,vectors,trial,anchors)
        key=routed[index]
        blocked.append(dict(index=index,expected=row['expected'],predicted=trial[key]['label'] if key else None))
    report['withheld_minute_blocks']=dict(
        correct=sum(r['expected']==r['predicted'] for r in blocked),
        wrong=sum(r['predicted'] is not None and r['expected']!=r['predicted'] for r in blocked),
        rejected=sum(r['predicted'] is None for r in blocked),cues=blocked)
    mothers={25,27,28,32,37,38}
    report['known_scene']=dict(correct=sum(r['speaker']==('マリ' if r['index'] in mothers else 'ペリーヌ') for r in report['scene']),
        rejected=sum(r['speaker'] is None for r in report['scene']),
        wrong=sum(r['speaker'] is not None and r['speaker']!=('マリ' if r['index'] in mothers else 'ペリーヌ') for r in report['scene']))
    (destination or ROOT/'docs/validation/2026-11-15-character-policy.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('held_out','scene','withheld_minute_blocks')}))
    print(json.dumps({k:v for k,v in report['withheld_minute_blocks'].items() if k!='cues'}))


if __name__=='__main__': main()
