"""Audition a fuller opening question without changing accepted shot timings."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',REFLOW_OFFLINE='1')


def main():
    from pydub import AudioSegment
    from core.cue_review import digest
    from core.providers.tts.indicf5_local import IndicF5TTSProvider
    from core.render_context import RenderContext,bind_job,run_process
    base=ROOT/'docs/validation'
    accepted=json.loads((base/'2026-10-08-shot-bounded-hindi-38a36120.json').read_text(encoding='utf-8'))
    feedback=json.loads((base/'2026-10-09-shot-bounded-user-feedback.json').read_text(encoding='utf-8'))
    assert feedback['three_shot_phrases_accepted'] and not feedback['opening_question_accepted']
    assert digest(accepted['output'])==feedback['output_sha256']
    original_hashes={row['shot']:digest(row['output']) for row in accepted['phrases']}
    folder=base/('2026-10-09-opening-question-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    text=json.loads((base/'2026-10-09-opening-question-candidates.json').read_text(encoding='utf-8'))['candidates'][1]
    profile=ROOT/'models/indicf5/references/abhishek/profile.json'
    report=dict(completed=False,human_accepted=False,production_changed=False,text=text,
        voice_profile_changed=False,tempo_changed=False,accepted_shot_timings_changed=False,
        integrated_into_video=False,existing_question_seconds=.39466666666666667,
        voice_profile_sha256=digest(profile),accepted_clip=str(accepted['output']))
    provider=None
    job=RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            provider=IndicF5TTSProvider(str(ROOT/'models/indicf5/evaluation/assets'),str(profile),'cuda:0')
            predicted=provider.estimate_duration_seconds(text)
            output=folder/'opening-question-native.wav'
            provider.synthesize(text,str(output),'hi',provider.profile['reference_audio'])
            result=provider.last_result
            provider.release()
            report['worker_released']=not getattr(job,'_indicf5_sessions',{})
            provider=None
            speech=AudioSegment.from_file(output)
            assert abs(len(speech)/1000-predicted)<.001
            listening=folder/'OPENING_QUESTION_LISTEN.wav'
            padded=AudioSegment.silent(duration=250,frame_rate=speech.frame_rate)+speech+AudioSegment.silent(duration=400,frame_rate=speech.frame_rate)
            padded.export(listening,format='wav').close()
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(listening),'-f','null','-'],capture_output=True,check=True,timeout=60)
            assert digest(profile)==report['voice_profile_sha256']
            assert digest(accepted['output'])==feedback['output_sha256']
            assert all(digest(row['output'])==original_hashes[row['shot']] for row in accepted['phrases'])
            report.update(completed=True,live_tts=True,predicted_seconds=predicted,actual_seconds=len(speech)/1000,
                generation_result=result,output=str(output),output_sha256=digest(output),listening=str(listening),
                listening_sha256=digest(listening),full_decode_pass=True,accepted_clip_and_three_phrases_unchanged=True,
                current_opening_window_seconds=.6,current_window_fits=predicted<=.6,
                note='Standalone wording/delivery review. A comfortable pause plus this fuller question needs an opening timing plan; no accepted phrase placement has been changed.')
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
