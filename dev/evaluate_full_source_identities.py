"""Evaluate full-episode source matching without translating or dubbing it."""
import json
import os
from pathlib import Path
import sys
from collections import Counter
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def main():
    from core.render_context import RenderContext,bind_job,run_process
    from core.cuda_providers import CudaSeparator
    from core.source_captions import extract
    from core.transcription import TranscriptionResult
    from core.pipeline_contracts import identify_cues,PipelineSpec,SettingsSnapshot
    from core.model_registry import ModelRegistry
    from core.run_manifest import RunManifest
    from core.diarization import prepare
    from core.caption_voice_identity import profiles,choose_cues,unit
    job=RenderContext(ROOT/'temp')
    report={}
    try:
        with bind_job(job):
            source=next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
            audio=job.workspace/'source.wav'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-vn','-ar','44100','-ac','2',str(audio)],check=True,timeout=180)
            print('Separating source for clean voice evidence',flush=True)
            vocals,_=CudaSeparator().separate(str(audio))
            captions=extract(source,'ja',job.workspace)
            cues=identify_cues(captions['dialogue'],'full-source-evaluation')
            transcript=TranscriptionResult(cues,'ja',None,'hint')
            manifest=RunManifest(job.workspace/'records',PipelineSpec('video_dub'),source,ModelRegistry(),SettingsSnapshot({}))
            print('Detecting source identities',flush=True)
            refined,mapping=prepare(str(audio),transcript,None,'cuda:0',manifest,'full-source-evaluation',
                [(e['start'],e['end']) for e in captions['preserved_events']],reference_audio_path=vocals)
            result=json.loads((job.workspace/'community-speakers/turns.json').read_text(encoding='utf-8'))
            private=ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation'
            private.mkdir(exist_ok=True)
            (private/'inputs.json').write_text(json.dumps(dict(cues=cues,result=result),ensure_ascii=False),encoding='utf-8')
            vector_map={row['cue_id']:unit(row['vector']) for row in result['cue_embeddings']}
            vectors={i:vector_map[c['cue_id']] for i,c in enumerate(cues) if c['cue_id'] in vector_map}
            named=[i for i,c in enumerate(cues) if c.get('speaker_hint') and not c.get('speaker_collective') and i in vectors]
            held_out=[]
            for index in named:
                if sum(cues[i]['speaker_hint']==cues[index]['speaker_hint'] for i in named)<2: continue
                hidden=deepcopy(cues);hidden[index].pop('speaker_hint',None)
                templates,named_templates=profiles(hidden,vectors)
                choices,evidence=choose_cues(hidden,vectors,templates,named_templates)
                key=choices[index];score=evidence[index]['similarity'];margin=evidence[index]['margin']
                held_out.append(dict(index=index,expected=cues[index]['speaker_hint'],
                    predicted=templates[key]['label'] if key else None,score=score,margin=margin))
            report=dict(source_cues=len(cues),utterances=len(refined),
                ready_source_cues=sum(len(c.get('source_fragments') or [c]) for c in refined if mapping[c['cue_id']]['reference']),
                reasons=dict(Counter(row.get('reason') for row in mapping.values())),
                reference_count=len({row['reference'] for row in mapping.values() if row['reference']}),
                held_out=held_out,wrong_confident=sum(r['predicted'] is not None and r['predicted']!=r['expected'] for r in held_out),
                scene=[dict(start=c['start'],end=c['end'],speaker=c.get('speaker'),status=c.get('speaker_match'))
                       for c in refined if c['start']<260 and c['end']>218],human_quality_accepted=False)
            print(json.dumps({k:v for k,v in report.items() if k not in ('scene','held_out')},ensure_ascii=True),flush=True)
    finally:
        (ROOT/'docs/validation/2026-11-14-full-source-identities.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        job.cleanup()


if __name__=='__main__': main()
