"""Compare decoded picture and audio timing without changing either reviewed video."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')


def main():
    import numpy as np
    from scipy.signal import correlate,correlation_lags
    from core.render_context import run_process
    base = ROOT/'docs/validation'
    prior = json.loads((base/'2026-10-08-spoken-hindi-full-video-887151ac.json').read_text(encoding='utf-8'))
    current = json.loads((base/'2026-10-08-reviewed-strong-whisper-video-2f75ebb6.json').read_text(encoding='utf-8'))
    paths = [Path(prior['directory'])/prior['output'],Path(current['output'])]
    audio = []
    pictures = []
    for path in paths:
        decoded = run_process(['ffmpeg','-v','error','-nostdin','-i',str(path),'-vn','-ac','1','-ar','8000','-f','f32le','-'],capture_output=True,check=True,timeout=120)
        audio.append(np.frombuffer(decoded.stdout,dtype='<f4').astype(np.float64))
        decoded = run_process(['ffmpeg','-v','error','-nostdin','-i',str(path),'-an','-vf','fps=5,scale=64:36','-pix_fmt','gray','-f','rawvideo','-'],capture_output=True,check=True,timeout=120)
        pictures.append(np.frombuffer(decoded.stdout,dtype=np.uint8).reshape(-1,36,64).astype(np.float32))
    rows = []
    for start,end in [(0,6),(9,14),(30,37),(52,55),(68.66,81.82),(90,110),(115.62,119.24)]:
        left,right = [a[round(start*8000):round(end*8000)] for a in audio]
        size = min(len(left),len(right))
        left,right = left[:size],right[:size]
        values = correlate(right,left,mode='full',method='fft')
        lags = correlation_lags(len(right),len(left),mode='full')
        allowed = abs(lags)<=8000
        best = int(lags[allowed][values[allowed].argmax()])
        coefficient = float(np.dot(left,right)/(np.linalg.norm(left)*np.linalg.norm(right)))
        rows.append(dict(start=start,end=end,new_audio_lag_seconds=best/8000,zero_lag_correlation=coefficient))
    count = min(len(pictures[0]),len(pictures[1]))
    video_scores = []
    for shift in range(-5,6):
        indices = np.arange(5,count-5)
        difference = pictures[1][indices+shift]-pictures[0][indices]
        video_scores.append(dict(new_video_shift_seconds=shift/5,mean_absolute_pixel_difference=float(abs(difference).mean())))
    report = dict(read_only=True,prior=str(paths[0]),current=str(paths[1]),audio_windows=rows,
        video_alignment=video_scores,best_video_alignment=min(video_scores,key=lambda row:row['mean_absolute_pixel_difference']),
        note='Decoded file timing comparison; does not measure subjective phrase-to-picture alignment or in-app playback startup.')
    output = base/'2026-10-08-reviewed-video-sync-audit.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
