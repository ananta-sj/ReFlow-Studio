"""Render accepted continuous intro alongside untouched family/lighthouse takes."""
import json
import argparse
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser=argparse.ArgumentParser()
    options=parser.add_mutually_exclusive_group()
    options.add_argument('--candidate-context',type=Path,default=None,
        help='Completed experimental context receipt; does not imply human acceptance')
    options.add_argument('--spliced-intro',type=Path,default=None,
        help='Completed question-only splice receipt; reviewed chart suffix retained')
    args=parser.parse_args()
    from pydub import AudioSegment
    from core.audio_utils import AudioEngineer
    from core.cue_review import digest
    from core.render_context import RenderContext,bind_job,run_process
    base=ROOT/'docs/validation'
    original=read(base/'2026-10-08-spoken-hindi-full-video-887151ac.json')
    shots=read(base/'2026-10-08-shot-bounded-hindi-38a36120.json')
    context_path=args.spliced_intro or args.candidate_context or base/'2026-10-09-question-context-cba76d9e.json'
    context=read(context_path)
    assert context['completed']
    if args.spliced_intro is not None:
        assert context['question_human_accepted'] and context['reviewed_rest_suffix_sample_exact']
        continuous=Path(context['output'])
        assert digest(continuous)==context['output_sha256']
    else:
        assert digest(context['listening'])==context['listening_sha256']
        continuous=Path(context['listening']).parent/'continuous-context.wav'
        assert digest(continuous)==context['result']['output_sha256']
    if args.candidate_context is None and args.spliced_intro is None:
        approval=read(base/'2026-10-09-question-context-user-feedback.json')
        assert approval['opening_naturalness_accepted']
        assert digest(context['listening'])==approval['listening_sha256']
    source=ROOT/'Sample/2.mp4'
    assert digest(source)==original['source_sha256']
    folder=base/('2026-10-09-accepted-intro-video-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    protected={row['shot']:digest(row['output']) for row in shots['phrases']}
    report=dict(completed=False,live_tts=False,new_separation=False,source_sha256=digest(source),
        context_receipt=context_path.name,
        opening_audio_human_accepted=args.candidate_context is None,video_human_accepted=False,production_changed=False,
        question_and_chart_generated_together=args.spliced_intro is None,
        question_only_spliced=args.spliced_intro is not None,family_lighthouse_timing_changed=False,
        previous_background_reused=True,scope='Source 88.000–99.160 seconds; no full-video acceptance claim.')
    job=RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            old_voice=original['stems']['dubbed']
            voice_path=Path(original['directory'])/old_voice['file']
            assert digest(voice_path)==old_voice['sha256']
            previous=AudioSegment.from_file(voice_path)
            voice=AudioSegment.silent(duration=11160,frame_rate=previous.frame_rate)
            voice=voice.overlay(previous[88000:90000],position=0)
            intro=AudioSegment.from_file(continuous)
            assert abs(len(intro)/1000-context['actual_seconds'])<=.001
            assert 90+len(intro)/1000<=93.6
            voice=voice.overlay(intro,position=2000)
            report['placements']=[dict(name='question+chart intro',start=90,end=90+len(intro)/1000)]
            for name in ['family','lighthouse']:
                row=next(row for row in shots['phrases'] if row['shot']==name)
                assert digest(row['output'])==row['sha256']
                clip=AudioSegment.from_file(row['output'])
                assert row['start']>=report['placements'][-1]['end']
                voice=voice.overlay(clip,position=round((row['start']-88)*1000))
                report['placements'].append(dict(name=name,start=row['start'],end=row['start']+len(clip)/1000,sha256=row['sha256']))
            bg=original['stems']['background']
            background_path=Path(original['directory'])/bg['file']
            assert digest(background_path)==bg['sha256']
            mixed=AudioEngineer().dynamic_mix(voice,AudioSegment.from_file(background_path)[88000:99160],ducking_db=-12)
            master=folder/'accepted-intro-master.wav'
            mixed.export(master,format='wav').close()
            picture=job.workspace/'picture.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','88','-i',str(source),'-t','11.16',
                '-map','0:v:0','-an','-c:v','libx264','-preset','veryfast','-crf','18',str(picture)],check=True,timeout=180)
            output=folder/'ACCEPTED_INTRO_SHOT_REVIEW.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(picture),'-i',str(master),
                '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True,timeout=180)
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],capture_output=True,check=True,timeout=120)
            media=json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,check=True).stdout)
            assert abs(float(media['format']['duration'])-11.16)<.08
            assert {'video','audio'}.issubset({stream['codec_type'] for stream in media['streams']})
            assert digest(source)==report['source_sha256']
            assert digest(shots['output'])==shots['output_sha256']
            assert all(digest(row['output'])==protected[row['shot']] for row in shots['phrases'])
            report.update(completed=True,output=str(output),output_sha256=digest(output),full_decode_pass=True,
                source_unchanged=True,prior_review_and_three_phrase_files_unchanged=True,
                duration_seconds=float(media['format']['duration']))
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        job.cleanup()
        report['workspace_removed']=not job.workspace.exists()
        folder.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(folder.with_suffix('.json'),flush=True)


if __name__=='__main__':
    main()
