"""Run two automatically matched character turns through the actual dub code."""
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--publish-auditions',action='store_true',help='Keep explicitly unaccepted listening samples')
    parser.add_argument('--dialogue-case',choices=['scene-japanese','scene-with-embedded-english'])
    parser.add_argument('--short-reference-context',action='store_true')
    parser.add_argument('--hymt-report',choices=['full-report.json','full-contextual-report.json',
        'full-contextual-english-captions-history-report.json'])
    parser.add_argument('--qwen35-case',choices=['first-europe-trip','scene'])
    parser.add_argument('--only-mother',action='store_true')
    args=parser.parse_args()
    from pydub import AudioSegment
    from core.render_context import RenderContext,bind_job,run_process
    from core.run_manifest import file_identity
    from core.cuda_providers import CudaSeparator,CudaNLLBProvider,CudaXTTSProvider,CudaWhisperProvider
    from core.caption_voice_identity import assign
    from core.transcription import TranscriptionResult
    from core.pipeline import ReflowPipeline
    from core.audio_utils import AudioEngineer
    from core.speech_timing import SpeechTimingReviewRequired
    from core.speech_generation_budget import SpeechGenerationLimitExceeded
    from core.batch_intelligibility import similarity
    archive=ROOT/'docs/diagnostics/overnight-20261114-metadata'
    data=json.loads((archive/'identity-evaluation/inputs.json').read_text(encoding='utf-8'))
    recorded=json.loads((archive/'outputs/run_records/f936a15389e54a9083195d418780b2c6/manifest.json').read_text(encoding='utf-8'))
    source=next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
    if file_identity(source)['sha256']!=recorded['source']['sha256']:
        raise ValueError('Source changed since cached voice evaluation')
    job=RenderContext(ROOT/'temp'); speech=translator=recognizer=None; report={'human_quality_accepted':False,'cues':[]}
    try:
        with bind_job(job):
            audio=job.workspace/'source.wav'
            context_args=['-ss','205'] if args.short_reference_context else []
            duration_args=['-t','62'] if args.short_reference_context else []
            run_process(['ffmpeg','-v','error','-nostdin','-y',*context_args,'-i',str(source),*duration_args,'-vn','-ar','44100','-ac','2',str(audio)],check=True,timeout=180)
            print('Preparing clean automatic character references',flush=True)
            vocals,_=CudaSeparator().separate(str(audio))
            with open(vocals,'rb') as stream:
                clean=AudioSegment.from_file(stream,format='wav').set_channels(1)
            if args.short_reference_context:
                clean=AudioSegment.silent(duration=round(data['result']['audio_seconds']*1000),frame_rate=clean.frame_rate).overlay(clean,position=205000)
            transcript=TranscriptionResult(data['cues'],'ja',None,'hint')
            transcript,mapping=assign(clean,transcript,data['result'],job.workspace,'scene-acceptance')
            selected=[]
            for original_index in ((37,) if args.only_mother else (29,37)):
                start=data['cues'][original_index]['start']
                cue=next(c for c in transcript if abs(c['start']-start)<.001)
                if not mapping[cue['cue_id']]['reference']:
                    raise ValueError('Scene turn still needs a character reference')
                selected.append(cue)
            if not args.only_mother and len({c['speaker'] for c in selected})!=2:
                raise ValueError('Scene collapsed two different characters')
            pipeline=ReflowPipeline(); pipeline._batch_speaker_rows=mapping
            if args.qwen35_case:
                evaluated=json.loads((ROOT/'docs/validation/qwen35-trial-20261115'/(args.qwen35_case+'-report.json')).read_text(encoding='utf-8'))
                if not evaluated.get('text_review',{}).get('selected_turns_passed'):
                    raise ValueError('Review Qwen candidate meaning before generating speech')
                for cue in selected:
                    indices=[i for i,c in enumerate(data['cues']) if c['start']>=cue['start']-.001 and c['end']<=cue['end']+.001]
                    candidate=next((r for r in reversed(evaluated['results']) if r.get('source_indices')==indices),None)
                    if (not candidate or not candidate['within_word_budget'] or candidate['fact_alarms']
                            or candidate['output']['uncertain']):
                        raise ValueError('No eligible Qwen candidate for this source turn')
                    cue['text']=candidate['output']['text']
                report['translation_engine']='Qwen3.5-9B Q4 isolated adaptation trial'
            elif args.hymt_report:
                evaluated=json.loads((ROOT/'docs/validation/hymt-trial-20261114'/args.hymt_report).read_text(encoding='utf-8'))
                if not evaluated.get('text_review',{}).get('selected_turns_passed'):raise ValueError('Review the candidate wording before speech generation')
                for cue in selected:
                    indices=[i for i,c in enumerate(data['cues']) if c['start']>=cue['start']-.001 and c['end']<=cue['end']+.001]
                    candidate=next((r for r in evaluated['results'] if r.get('source_indices')==indices),None)
                    if candidate is None:raise ValueError('No exact candidate for the grouped source turn')
                    cue['text']=candidate['translation']
                report['translation_engine']='HY-MT1.5-1.8B Q8'
            elif args.dialogue_case:
                evaluated=json.loads((ROOT/'docs/validation/qwen-scene-20261114/report.json').read_text(encoding='utf-8'))
                candidate=next(r for r in evaluated['results'] if r['name']==args.dialogue_case)
                wording={row['id']:row for row in candidate['output']}
                for cue in selected:
                    indices=[i for i,c in enumerate(data['cues']) if c['start']>=cue['start']-.001 and c['end']<=cue['end']+.001]
                    if not indices or any(wording[str(i)]['uncertain'] for i in indices):raise ValueError('Model flagged this dialogue for review')
                    cue['text']=' '.join(wording[str(i)]['text'] for i in indices)
                report['dialogue_case']=args.dialogue_case
            else:
                translator=CudaNLLBProvider(pipeline.registry.get_active('translation')['local_path'])
                for cue in selected:
                    cue['text']=pipeline._translate_line(cue['text'],'Hindi',translator,'',None,'',source_language='ja',cue=cue)
                translator.release(); translator=None
            speech=CudaXTTSProvider(); paths=[]
            for index,cue in enumerate(selected):
                row=dict(start=cue['start'],end=cue['end'],speaker=cue['speaker'],source_text=cue['source_text'],text=cue['text'])
                started=time.monotonic()
                call_args=(index,cue,['CLONED_USER'],'hi',speech,{},None,mapping[cue['cue_id']]['reference'],'cuda:0',AudioEngineer())
                try:
                    take=pipeline._dub_segment(*call_args,next_start=cue['end']+.35,retain_overflow=False)
                    row['alternate']=False
                except (SpeechTimingReviewRequired,SpeechGenerationLimitExceeded):
                    take=pipeline._dub_segment(*call_args,next_start=cue['end']+.35,alternate_take=True,retain_overflow=False)
                    row['alternate']=True
                path=job.workspace/f'character-{index+1}.wav'
                take.export(path,format='wav').close(); paths.append(path)
                row.update(audio_seconds=len(take)/1000,seconds=time.monotonic()-started)
                report['cues'].append(row)
                print(json.dumps(row,ensure_ascii=True),flush=True)
            speech.release(); speech=None
            recognizer=CudaWhisperProvider(str(ROOT/'models/whisper/ct2-turbo-candidate-compat/model'))
            results=recognizer.transcribe_takes([str(p) for p in paths],'hi')
            if len(results)!=len(paths):raise ValueError('Incomplete word check')
            for row,result in zip(report['cues'],results):
                observed=' '.join(c['text'] for c in result)
                row.update(observed=observed,word_similarity=similarity(row['text'],observed,'hi'))
            report['word_check_threshold']=.8 if args.qwen35_case else .55
            report['word_check_passed']=all(r['word_similarity']>=report['word_check_threshold'] for r in report['cues'])
            if report['word_check_passed'] and args.publish_auditions:
                destination=ROOT/('outputs/qwen35-scene-trial-20261115' if args.qwen35_case else 'outputs/scene-test-20261114');destination.mkdir(exist_ok=True)
                for index,path in enumerate(paths):
                    target=destination/('mother.wav' if args.only_mother else path.name)
                    job.publish(path,target);report['cues'][index]['audition']=str(target)
            print(json.dumps(report,ensure_ascii=True),flush=True)
    except Exception as error:
        report['error']=str(error)
        print(type(error).__name__+': '+str(error),flush=True)
        raise
    finally:
        for provider in (speech,translator,recognizer):
            release=getattr(provider,'release',None)
            if callable(release):
                try: release()
                except Exception as error:report.setdefault('cleanup_errors',[]).append(str(error))
        job.cleanup()
        report_name=('2026-11-15-scene-pipeline-qwen35-'+args.qwen35_case+'.json') if args.qwen35_case else '2026-11-14-scene-pipeline-hymt.json' if args.hymt_report else '2026-11-14-scene-pipeline-qwen.json' if args.dialogue_case else '2026-11-14-scene-pipeline.json'
        (ROOT/'docs/validation'/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
