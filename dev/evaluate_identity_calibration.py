"""Compare existing source embeddings on labelled held-out cues; no synthesis."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.caption_voice_identity import unit,profiles,match_cue


def main():
    data=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    cues=data['cues']; embeddings=data['result']['cue_embeddings']; report={}
    for field in ('vector','calibrated_vector'):
        by_id={row['cue_id']:unit(row[field]) for row in embeddings}
        vectors={i:by_id[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in by_id}
        named=[i for i,c in enumerate(cues) if c.get('speaker_hint') and not c.get('speaker_collective') and i in vectors]
        tests=[]
        for index in named:
            if sum(cues[i]['speaker_hint']==cues[index]['speaker_hint'] for i in named)<2: continue
            templates,_=profiles(cues,vectors,{index})
            key,score,margin=match_cue(cues[index],vectors[index],templates,trust_hint=False)
            tests.append(dict(index=index,expected=cues[index]['speaker_hint'],predicted=templates[key]['label'] if key else None,score=score,margin=margin))
        templates,_=profiles(cues,vectors)
        scene=[]
        for i,c in enumerate(cues):
            if c['start']<263 and c['end']>215 and i in vectors:
                key,score,margin=match_cue(c,vectors[i],templates)
                scene.append(dict(index=i,start=c['start'],text=c['text'],predicted=templates[key]['label'] if key else None,score=score,margin=margin))
        report[field]=dict(correct=sum(t['predicted']==t['expected'] for t in tests),
            rejected=sum(t['predicted'] is None for t in tests),wrong=sum(t['predicted'] is not None and t['predicted']!=t['expected'] for t in tests),
            profiles=len(templates),held_out=tests,scene=scene)
    (ROOT/'docs/validation/2026-11-14-identity-calibration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:{name:value for name,value in v.items() if name not in ('held_out','scene')} for k,v in report.items()}))


if __name__=='__main__': main()
