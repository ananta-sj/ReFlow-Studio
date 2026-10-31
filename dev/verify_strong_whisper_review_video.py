"""Render a reviewed video without misrepresenting saved accepted takes as new TTS.

Fresh recognition and machine translation remain in their original review. This
separate diagnostic review imports the hash-bound accepted spoken draft/takes,
using their accepted timeline, and excludes the digitally silent final block.
"""
import json
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    from core import cue_review
    from core.audio_utils import load_speech_audio
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext,bind_job,run_process
    parser = argparse.ArgumentParser()
    parser.add_argument('--align-ending',action='store_true')
    parser.add_argument('--align-scenes',action='store_true')
    parser.add_argument('--accepted-shots',action='store_true',help='Integrate hash-bound approved short section and diagnostic tail anchors')
    args = parser.parse_args()
    if args.accepted_shots and (args.align_ending or args.align_scenes):
        parser.error('Accepted-shot integration cannot use the older rejected alignment experiments')
    if args.align_scenes:
        args.align_ending = True
    base = ROOT/'docs/validation'
    fresh_path = base/'2026-10-08-strong-whisper-app-review-9ad56e5a.json'
    old_path = base/'2026-10-08-spoken-hindi-full-video-887151ac.json'
    draft_path = base/'2026-10-08-full-video-spoken-hindi-draft.json'
    acceptance = read(base/'2026-10-08-full-video-user-acceptance.json')
    fresh,old,draft = read(fresh_path),read(old_path),read(draft_path)
    assert acceptance['human_full_video_baseline_accepted']
    assert cue_review.digest(old_path) == acceptance['render_receipt_sha256']
    assert cue_review.digest(draft_path) == acceptance['draft_sha256']
    accepted_video = Path(old['directory'])/old['output']
    assert cue_review.digest(accepted_video) == acceptance['output_sha256']
    assert fresh['completed'] and fresh['live_asr'] and fresh['live_translation']
    assert fresh['source_sha256'] == old['source_sha256'] == cue_review.digest(fresh['source'])
    last = fresh['recognition_result']['blocks'][-1]
    assert last['start'] == 120 and last['digital_silence'] is True
    assert draft['cases'][-1]['source'] == 'Thank you.'
    label = ('2026-10-09-approved-shot-full-video-' if args.accepted_shots else '2026-10-08-chart-scene-sync-' if args.align_scenes else '2026-10-08-ending-phrase-sync-' if args.align_ending else '2026-10-08-reviewed-strong-whisper-video-')+uuid.uuid4().hex[:8]
    folder = base/label
    folder.mkdir()
    store = cue_review.ReviewStore(folder)
    identifier = uuid.uuid4().hex
    work = store.folder(identifier)
    work.mkdir()
    manifest = read(Path(fresh['review_manifest']))
    manifest.update(id=identifier,revision=1,created_at=time.time(),recognition=fresh['transcription'],
        video_asset='source-video.mp4',assets={},cues=[],
        diagnostic_review_origin='Accepted prior spoken draft/takes imported; timeline restored by diagnostic reviewer, not automatic machine translation adaptation.')
    shutil.copy2(fresh['source'],work/'source-video.mp4')
    cases = [dict(case) for case in draft['cases'][:-1]]
    if args.accepted_shots:
        cases[12].update(start=116.19,end=118.526)
        cases[11]['end']=116.0
    for index,case in enumerate(cases):
        previous = old['cues'][index]
        assert previous['text'] == case['translation']
        original = Path(old['directory'])/previous['file']
        assert cue_review.digest(original) == previous['result']['output_sha256']
        filename = 'accepted-'+str(index+1)+'.wav'
        shutil.copy2(original,work/filename)
        if args.accepted_shots and index==11:
            from dev.build_accepted_shot_cue import build
            manifest['accepted_shot_integration']=build(work/filename,old,base)
            case['translation']=manifest['accepted_shot_integration']['subtitle_text']
        if args.align_ending and index == 11:
            # Reposition exact accepted PCM sentence chunks, not regenerated or
            # time-stretched speech. Original internal 200 ms gaps are excluded.
            import wave
            details = previous['result']['sentences']
            starts = [0,.5946666666666667,8.8,10.888,15,20.69]
            assert len(details)==len(starts)==6
            with wave.open(str(original),'rb') as audio:
                assert audio.getframerate()==24000 and audio.getnchannels()==1 and audio.getsampwidth()==2
                pcm = audio.readframes(audio.getnframes())
            original_frames = sum(row['frames'] for row in details)+5*4800
            assert len(pcm)==original_frames*2
            chunks,offset = [],0
            for number,row in enumerate(details):
                chunk = pcm[offset*2:(offset+row['frames'])*2]
                chunks.append(chunk)
                offset += row['frames']+(4800 if number < 5 else 0)
            clause_cuts = None
            if args.align_scenes:
                import numpy as np
                chart = chunks[1]
                cuts = [round(2.2*24000),round(4.15*24000)]
                # Word timestamps locate the two comma boundaries; inspect the
                # waveform too, because recognition timestamps are approximate.
                samples = np.frombuffer(chart,dtype='<i2').astype(float)/32768
                energies = [float(np.sqrt(np.mean(samples[cut-240:cut+240]**2))) for cut in cuts]
                assert all(energy < .005 for energy in energies)
                clauses = [chart[:cuts[0]*2],chart[cuts[0]*2:cuts[1]*2],chart[cuts[1]*2:]]
                assert b''.join(clauses)==chart
                chunks = [chunks[0],*clauses,*chunks[2:]]
                details = [dict(frames=len(chunk)//2) for chunk in chunks]
                starts = [0,1,4,7.45,10.456,12.544,15.73,20.69]
                clause_cuts = dict(original_sentence_cut_seconds=[2.2,4.15],
                    boundary_20ms_rms=energies,all_original_sentence_samples_retained=True,
                    timestamp_evidence='2026-10-08-chart-phrase-word-timing.json')
            total = round(starts[-1]*24000)+details[-1]['frames']
            aligned = bytearray(total*2)
            prior_end = 0
            for start,row,chunk in zip(starts,details,chunks):
                first = round(start*24000)
                assert first >= prior_end
                aligned[first*2:(first+row['frames'])*2] = chunk
                assert bytes(aligned[first*2:(first+row['frames'])*2]) == chunk
                prior_end = first+row['frames']
            with wave.open(str(work/filename),'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
                audio.writeframes(bytes(aligned))
            manifest['phrase_alignment_comparison'] = dict(cue=12,
                absolute_starts=[90+value for value in starts],
                speech_pcm_chunks_unchanged=True,tempo_changed=False,
                note='Editorial clause/shot anchors for this source; no automatic production alignment is implied.' if args.align_scenes else 'Editorial sentence anchors from source review; first two sentences unchanged. No automatic word alignment is implied.')
            if clause_cuts:
                manifest['phrase_alignment_comparison']['clause_cuts'] = clause_cuts
        seconds = len(load_speech_audio(work/filename))/1000
        following = cases[index+1]['start'] if index+1 < len(cases) else case['end']
        available = following-case['start']
        take = dict(file=filename,seconds=seconds,fits=round(seconds*1000)<=round(available*1000),sha256=cue_review.digest(work/filename))
        assert take['fits']
        manifest['cues'].append(dict(start=case['start'],end=case['end'],available_seconds=available,
            source_text=case['source'],text=case['translation'],candidate=take,accepted=take))
    stem = old['stems']['background']
    background = Path(old['directory'])/stem['file']
    assert cue_review.digest(background) == stem['sha256']
    shutil.copy2(background,work/'background.wav')
    manifest['assets'] = {p.name:cue_review.digest(p) for p in work.iterdir() if p.is_file()}
    store.save(manifest)
    pipe = ReflowPipeline()
    pipe.output_dir = str(folder)
    job = RenderContext(ROOT/'temp')
    report = dict(completed=False,fresh_preparation_receipt=str(fresh_path),
        raw_machine_translation_preserved=True,live_asr=not args.accepted_shots,live_translation=not args.accepted_shots,live_tts=False,
        accepted_takes_reused=12 if args.align_ending or args.accepted_shots else 13,retimed_take_count=2 if args.accepted_shots else 1 if args.align_ending else 0,
        speech_resynthesized=False,tempo_changed=False,editorial_timeline_fixture_used=True,
        accepted_wording_fixture_used=True,previous_background_reused=True,live_separation=False,
        removed_final_invented_thank_you=True,human_new_video_accepted=False,
        source_sha256=fresh['source_sha256'],review_manifest=str(work/'review.json'))
    if args.align_ending:
        report['phrase_alignment_comparison'] = manifest['phrase_alignment_comparison']
    if args.accepted_shots:
        report.update(accepted_shot_integration=manifest['accepted_shot_integration'],
            prior_live_recognition_translation_reused=True,
            charlie_signoff_start=116.19,charlie_signoff_waveform_changed=False)
    try:
        with bind_job(job):
            output = cue_review.operate(store,pipe,identifier,1,'render',None,None,
                lambda percent,message:print(percent,message,flush=True))
            decoded = run_process(['ffmpeg','-v','error','-nostdin','-i',output,'-f','null','-'],capture_output=True,check=True,timeout=300)
            result = run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',output],capture_output=True,check=True)
            media = json.loads(result.stdout)
            subtitle = next(s for s in media['streams'] if s['codec_type']=='subtitle')
            assert subtitle['tags']['language']=='hin'
            assert abs(float(media['format']['duration'])-manifest['duration']) < .15
            assert cue_review.digest(fresh['source'])==fresh['source_sha256']
            report.update(completed=True,output=output,output_sha256=cue_review.digest(output),
                full_decode_pass=True,subtitle_language='hin',duration=float(media['format']['duration']),
                source_unchanged=True,original_accepted_video_unchanged=cue_review.digest(accepted_video)==acceptance['output_sha256'])
            if args.accepted_shots:
                preview=folder/'APPROVED_SHOTS_AND_ENDING_1m28_to_1m59.mp4'
                run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','88','-i',output,'-t','31.16',
                    '-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','veryfast','-crf','18',
                    '-c:a','aac','-b:a','192k','-movflags','+faststart',str(preview)],check=True,timeout=180)
                run_process(['ffmpeg','-v','error','-nostdin','-i',str(preview),'-f','null','-'],capture_output=True,check=True,timeout=120)
                report.update(ending_preview=str(preview),ending_preview_sha256=cue_review.digest(preview),ending_preview_full_decode_pass=True)
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        folder.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(folder.with_suffix('.json'),flush=True)


if __name__ == '__main__':
    main()
