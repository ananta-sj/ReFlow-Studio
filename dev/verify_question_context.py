"""Keep wording and total budget while testing one continuous question+context."""
import json
import argparse
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',REFLOW_OFFLINE='1')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--budget',type=float,default=None)
    parser.add_argument('--question',default=None,help='Optional Hindi question wording for a standalone context audition')
    parser.add_argument('--seed',type=int,default=None,help='Evaluation profile only; original profile stays unchanged')
    args=parser.parse_args()
    if args.budget is not None and not (.1<=args.budget<=3.5):
        parser.error('Budget must be finite and within 0.1–3.5 seconds for this shot trial')
    if args.seed is not None and not 0<=args.seed<2**32:
        parser.error('Seed must be an unsigned 32-bit integer')
    import numpy as np
    import soundfile as sf
    from pydub import AudioSegment
    from core.cue_review import digest
    from core.providers.tts.indicf5_local import IndicF5TTSProvider,load_reference_profile
    from core.render_context import RenderContext,bind_job,run_process
    base=ROOT/'docs/validation'
    old=json.loads((base/'2026-10-08-spoken-hindi-full-video-887151ac.json').read_text(encoding='utf-8'))
    accepted=json.loads((base/'2026-10-08-shot-bounded-hindi-38a36120.json').read_text(encoding='utf-8'))
    opening=old['cues'][11]
    original,rate=sf.read(Path(old['directory'])/opening['file'],dtype='int16')
    question=opening['result']['sentences'][0]
    chart=next(row for row in accepted['phrases'] if row['shot']=='chart')
    chart_pcm,chart_rate=sf.read(chart['output'],dtype='int16')
    assert rate==chart_rate==24000
    control=np.concatenate([original[:question['frames']],np.zeros(4800,dtype='int16'),chart_pcm])
    question_text=args.question if args.question is not None else question['text']
    if not question_text.strip() or not question_text.rstrip().endswith('?') or len(question_text)>80:
        parser.error('Question must be nonblank, end with ? and contain at most 80 characters')
    text=question_text+' '+chart['text']
    profile=ROOT/'models/indicf5/references/abhishek/profile.json'
    protected={row['shot']:digest(row['output']) for row in accepted['phrases']}
    folder=base/('2026-10-09-question-context-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    report=dict(completed=False,human_accepted=False,text=text,integrated_into_video=False,
        production_defaults_changed=False,voice_profile_changed=False,profile_sha256=digest(profile),
        evaluation_seed=args.seed,evaluation_profile_changed=args.seed is not None,
        wording_matches_segmented_control=question_text==question['text'],control_seconds=len(control)/rate,
        question_wording_changed=question_text!=question['text'],question_text=question_text,
        fixed_total_budget=args.budget is None,post_synthesis_time_stretch=False,
        requested_budget_seconds=args.budget)
    job=RenderContext(ROOT/'temp')
    provider=None
    try:
        with bind_job(job):
            selected_profile=profile
            if args.seed is not None:
                evaluation=load_reference_profile(profile)
                evaluation.pop('profile_path',None)
                evaluation['seed']=args.seed
                selected_profile=folder/'evaluation-profile.json'
                selected_profile.write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                report['evaluation_profile_sha256']=digest(selected_profile)
            provider=IndicF5TTSProvider(str(ROOT/'models/indicf5/evaluation/assets'),str(selected_profile),'cuda:0')
            sf.write(folder/'segmented-control.wav',control,rate,subtype='PCM_16')
            output=folder/'continuous-context.wav'
            budget=args.budget if args.budget is not None else len(control)/rate
            predicted=provider.estimate_duration_seconds(text,minimum_sentence_seconds=budget,continuous_utterance=True)
            print('Generating question with context in one model utterance',flush=True)
            provider.synthesize(text,str(output),'hi',provider.profile['reference_audio'],minimum_sentence_seconds=budget,continuous_utterance=True)
            result=provider.last_result
            actual,actual_rate=sf.read(output,dtype='int16')
            assert actual_rate==rate and abs(len(actual)/rate-predicted)<1/rate
            assert abs(len(actual)/rate-budget)<=256/rate
            assert len(result['sentences'])==1 and result['sentences'][0]['text']==text
            # Same live worker, no continuous-mode option: ensure opt-in context
            # is not sticky and the accepted default question stays identical.
            default=folder/'default-regression.wav'
            regression=provider if args.seed is None else IndicF5TTSProvider(str(ROOT/'models/indicf5/evaluation/assets'),str(profile),'cuda:0')
            regression.synthesize(question['text'],str(default),'hi',regression.profile['reference_audio'])
            default_pcm,_=sf.read(default,dtype='int16')
            assert np.array_equal(default_pcm,original[:question['frames']])
            provider.release()
            provider=None
            listening=folder/'QUESTION_WITH_CONTEXT_LISTEN.wav'
            speech=AudioSegment.from_file(output)
            padded=AudioSegment.silent(duration=250,frame_rate=rate)+speech+AudioSegment.silent(duration=400,frame_rate=rate)
            padded.export(listening,format='wav').close()
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(listening),'-f','null','-'],capture_output=True,check=True)
            assert digest(profile)==report['profile_sha256']
            assert digest(accepted['output'])==accepted['output_sha256']
            assert all(digest(row['output'])==protected[row['shot']] for row in accepted['phrases'])
            report.update(completed=True,actual_seconds=len(actual)/rate,predicted_seconds=predicted,
                result=result,one_model_utterance_verified=True,default_pcm_regression_pass=True,
                worker_released=not getattr(job,'_indicf5_sessions',{}),listening=str(listening),
                listening_sha256=digest(listening),full_decode_pass=True,accepted_video_and_three_takes_unchanged=True)
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        if provider is not None:
            provider.release()
        job.cleanup()
        report['workspace_removed']=not job.workspace.exists()
        folder.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(folder.with_suffix('.json'),flush=True)


if __name__=='__main__':
    main()
