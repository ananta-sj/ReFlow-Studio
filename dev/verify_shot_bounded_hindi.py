"""Generate a short editorial shot-bounded review with unchanged IndicF5 settings."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',REFLOW_OFFLINE='1')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    from pydub import AudioSegment
    from core.audio_utils import AudioEngineer,load_speech_audio
    from core.cue_review import digest
    from core.pipeline import ReflowPipeline
    from core.providers.tts.indicf5_local import IndicF5TTSProvider
    from core.render_context import RenderContext,bind_job,run_process
    base=ROOT/'docs/validation'
    prior=read(base/'2026-10-08-spoken-hindi-full-video-887151ac.json')
    draft_path=base/'2026-10-08-shot-phrase-draft.json'
    draft=read(draft_path)
    profile=ROOT/'models/indicf5/references/abhishek/profile.json'
    source=ROOT/draft['source']
    original_video=Path(prior['directory'])/prior['output']
    assert digest(source)==prior['source_sha256'] and digest(original_video)==prior['output_sha256']
    destination=base/('2026-10-08-shot-bounded-hindi-'+uuid.uuid4().hex[:8])
    destination.mkdir()
    report=dict(completed=False,human_accepted=False,production_changed=False,
        voice_profile_changed=False,tempo_changed=False,live_tts=True,
        editorial_text_fixture_used=True,draft=str(draft_path),draft_sha256=digest(draft_path),
        scope='Original source 88–99.16 seconds only; no full-video synchronization claim.',
        source_sha256=digest(source),voice_profile_sha256=digest(profile),phrases=[])
    job=RenderContext(ROOT/'temp')
    provider=None
    try:
        with bind_job(job):
            provider=IndicF5TTSProvider(str(ROOT/'models/indicf5/evaluation/assets'),str(profile),'cuda:0')
            reference=provider.profile['reference_audio']
            # One-frame allowance at the crowd cut retains the faithful wording
            # and unchanged native pace: 2.5067 s versus the 2.48 s visual slot.
            phrases=[dict(row) for row in draft['phrases']]
            phrases[-1]['speech_window_end']=99.16
            for row in phrases:
                available=row.get('speech_window_end',row['end'])-row['start']
                predicted=provider.estimate_duration_seconds(row['text'])
                assert predicted<=available+.001
                output=destination/(row['shot']+'.wav')
                print('Generating '+row['shot']+' ('+str(round(predicted,3))+' seconds)',flush=True)
                provider.synthesize(row['text'],str(output),'hi',reference)
                clip=load_speech_audio(output)
                actual=len(clip)/1000
                assert actual<=available+.001 and abs(actual-predicted)<.001
                report['phrases'].append(dict(**row,predicted_seconds=predicted,actual_seconds=actual,
                    output=str(output),sha256=digest(output),result=provider.last_result))
            provider.release()
            report['speech_worker_released']=not getattr(job,'_indicf5_sessions',{})
            provider=None
            start,end=88,99.16
            milliseconds=round((end-start)*1000)
            stem=prior['stems']['dubbed']
            original_voice=Path(prior['directory'])/stem['file']
            assert digest(original_voice)==stem['sha256']
            # Retain the original preceding interview tail; replace only the
            # chart sentence region. The original opening question is unchanged.
            previous=AudioSegment.from_file(original_voice)
            voice=AudioSegment.silent(duration=milliseconds,frame_rate=previous.frame_rate)
            tail=previous[round(start*1000):90000]
            voice=voice.overlay(tail,position=0)
            opening=prior['cues'][11]
            first=load_speech_audio(Path(prior['directory'])/opening['file'])[:round(opening['result']['sentences'][0]['frames']/24)]
            voice=voice.overlay(first,position=2000)
            for row in report['phrases']:
                voice=voice.overlay(load_speech_audio(row['output']),position=round((row['start']-start)*1000))
            bg=prior['stems']['background']
            background=Path(prior['directory'])/bg['file']
            assert digest(background)==bg['sha256']
            mixed=AudioEngineer().dynamic_mix(voice,AudioSegment.from_file(background)[88000:99160],ducking_db=-12)
            master=destination/'shot-review-master.wav'
            mixed.export(master,format='wav').close()
            original_clip=job.workspace/'original-picture.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss',str(start),'-i',str(source),'-t',str(end-start),
                '-map','0:v:0','-an','-c:v','libx264','-preset','veryfast','-crf','18',str(original_clip)],check=True,timeout=180)
            output=destination/'SHOT_BOUNDED_HINDI_1m28_to_1m39.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(original_clip),'-i',str(master),
                '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True,timeout=180)
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],capture_output=True,check=True,timeout=120)
            media=json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,check=True).stdout)
            assert abs(float(media['format']['duration'])-(end-start))<.08
            assert {'video','audio'}.issubset({stream['codec_type'] for stream in media['streams']})
            assert digest(profile)==report['voice_profile_sha256']
            report.update(completed=True,output=str(output),output_sha256=digest(output),full_decode_pass=True,
                duration_seconds=float(media['format']['duration']),source_unchanged=digest(source)==report['source_sha256'],
                original_accepted_video_unchanged=digest(original_video)==prior['output_sha256'],
                previous_background_reused=True,new_separation=False,
                lighthouse_native_speech_end_seconds=phrases[-1]['start']+report['phrases'][-1]['actual_seconds'],
                lighthouse_visual_end_seconds=99.12,lighthouse_permitted_extension_seconds=.04)
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        if provider is not None:
            provider.release()
        job.cleanup()
        report['workspace_removed']=not job.workspace.exists()
        destination.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(destination.with_suffix('.json'),flush=True)


if __name__=='__main__':
    main()
