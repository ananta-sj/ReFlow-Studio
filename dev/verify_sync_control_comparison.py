"""Measure exact-frame timing and prepare a single-file baseline A/B comparison.

No speech placement, model inference, tempo or voice parameters are changed.
"""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    import numpy as np
    from scipy.signal import correlate,correlation_lags
    from core.cue_review import digest
    from core.render_context import RenderContext,bind_job,run_process
    base = ROOT/'docs/validation'
    old = read(base/'2026-10-08-spoken-hindi-full-video-887151ac.json')
    new = read(base/'2026-10-08-reviewed-strong-whisper-video-2f75ebb6.json')
    paths = [Path(old['directory'])/old['output'],Path(new['output'])]
    assert digest(paths[0])==old['output_sha256'] and digest(paths[1])==new['output_sha256']
    folder = base/('2026-10-08-sync-control-'+uuid.uuid4().hex[:8])
    folder.mkdir()
    report = dict(completed=False,source_paths=[str(path) for path in paths],
        original_timing_preserved=True,speech_placement_changed=False,voice_resynthesized=False,
        production_changed=False,source_start_seconds=88,source_end_seconds=105,
        note='A is accepted original, B is first unadjusted reviewed export. Rejected manual offsets are excluded. Same playback file and encoding settings reduce independent player/encoder differences; live preview playback is still not measurable here.')
    job = RenderContext(ROOT/'temp')
    try:
        with bind_job(job):
            pictures,audio=[],[]
            for path in paths:
                decoded=run_process(['ffmpeg','-v','error','-nostdin','-ss','88','-i',str(path),'-t','17','-an',
                    '-vf','fps=25,scale=64:36','-pix_fmt','gray','-f','rawvideo','-'],capture_output=True,check=True,timeout=120)
                pictures.append(np.frombuffer(decoded.stdout,dtype=np.uint8).reshape(-1,36,64).astype(np.float32))
                decoded=run_process(['ffmpeg','-v','error','-nostdin','-ss','88','-i',str(path),'-t','17','-vn',
                    '-ac','1','-ar','48000','-f','f32le','-'],capture_output=True,check=True,timeout=120)
                audio.append(np.frombuffer(decoded.stdout,dtype='<f4').astype(np.float64))
            count=min(map(len,pictures))
            rows=[]
            for shift in range(-25,26):
                index=np.arange(25,count-25)
                rows.append(dict(shift_frames=shift,shift_seconds=shift/25,
                    pixel_error=float(abs(pictures[1][index+shift]-pictures[0][index]).mean())))
            report['frame_alignment']=dict(fps=25,best=min(rows,key=lambda row:row['pixel_error']),
                zero_shift=rows[25],negative_one_frame=rows[24],positive_one_frame=rows[26])
            windows=[]
            for start,end in [(88,90),(90,94),(94,97),(97,100),(100,103),(103,105)]:
                first,last=round((start-88)*48000),round((end-88)*48000)
                left,right=[clip[first:last] for clip in audio]
                values=correlate(right,left,mode='full',method='fft')
                lags=correlation_lags(len(right),len(left),mode='full')
                allowed=abs(lags)<=48000
                best=int(lags[allowed][values[allowed].argmax()])
                windows.append(dict(start=start,end=end,new_audio_lag_samples=best,
                    lag_seconds=best/48000,zero_lag_correlation=float(np.dot(left,right)/(np.linalg.norm(left)*np.linalg.norm(right)))))
            report['audio_alignment_48000hz']=windows
            assert report['frame_alignment']['best']['shift_frames']==0
            assert all(row['new_audio_lag_samples']==0 for row in windows)
            pieces=[]
            for index,path in enumerate(paths):
                clip=job.workspace/('A-original.mp4' if index==0 else 'B-unadjusted-review.mp4')
                run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','88','-i',str(path),'-t','17',
                    '-map','0:v:0','-map','0:a:0','-vf','setpts=PTS-STARTPTS','-af','asetpts=PTS-STARTPTS',
                    '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
                    '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(clip)],check=True,timeout=180)
                pieces.append(clip)
            output=folder/'A_ORIGINAL_THEN_B_UNADJUSTED_REVIEW.mp4'
            # One continuous player clock. Separate halves retain their own audio;
            # video is not delayed relative to it by a guessed correction.
            run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(pieces[0]),'-i',str(pieces[1]),
                '-filter_complex','[0:v]setpts=PTS-STARTPTS[v0];[0:a]asetpts=PTS-STARTPTS[a0];[1:v]setpts=PTS-STARTPTS[v1];[1:a]asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
                '-map','[v]','-map','[a]','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
                '-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True,timeout=180)
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(output),'-f','null','-'],capture_output=True,check=True,timeout=120)
            media=json.loads(run_process(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,check=True).stdout)
            assert {'audio','video'}.issubset({stream['codec_type'] for stream in media['streams']})
            assert abs(float(media['format']['duration'])-34)<.15
            report.update(completed=True,output=str(output),output_sha256=digest(output),
                full_decode_pass=True,duration_seconds=float(media['format']['duration']),
                original_inputs_unchanged=digest(paths[0])==old['output_sha256'] and digest(paths[1])==new['output_sha256'],
                comparison_halves=[dict(label='A accepted original',start=0,end=17),dict(label='B first unadjusted review',start=17,end=34)],
                human_comparison_accepted=False)
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        job.cleanup()
        report['workspace_removed']=not job.workspace.exists()
        folder.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(folder.with_suffix('.json'),flush=True)


if __name__=='__main__':
    main()
