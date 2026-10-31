"""Compare actual decoded old/new candidate speech without rewriting either file."""
import hashlib
import json
import os
from pathlib import Path
import sys
import math
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ['PATH']=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')

def main():
    from core.audio_utils import load_speech_audio
    old=json.loads((OUT/'2026-10-13-xtts-candidate-live-evaluation-audited-network.json').read_text(encoding='utf-8'))
    new=json.loads((OUT/'2026-10-13-xtts-security-candidate-live-evaluation-dense-position.json').read_text(encoding='utf-8'))
    a=load_speech_audio(old['output_file']);b=load_speech_audio(new['output_file'])
    same_format=(a.channels,a.frame_rate,a.sample_width)==(b.channels,b.frame_rate,b.sample_width)
    report=dict(old_file=old['output_file'],new_file=new['output_file'],same_spoken_text=old['spoken_text']==new['spoken_text'],
        same_decoded_format=same_format,old_frames=a.frame_count(),new_frames=b.frame_count(),
        decoded_pcm_identical=same_format and a.raw_data==b.raw_data,
        old_pcm_sha256=hashlib.sha256(a.raw_data).hexdigest(),new_pcm_sha256=hashlib.sha256(b.raw_data).hexdigest(),
        audio_files_modified=False,human_naturalness_accepted=False)
    if same_format and a.frame_count()==b.frame_count():
        x=a.get_array_of_samples();y=b.get_array_of_samples()
        differences=[int(u)-int(v) for u,v in zip(x,y)]
        rms=math.sqrt(sum(d*d for d in differences)/len(differences))
        signal=math.sqrt(sum(int(u)**2 for u in x)/len(x))
        report.update(max_sample_difference=max(abs(d) for d in differences),rms_sample_difference=rms,
            normalized_rms_difference=rms/(2**(8*a.sample_width-1)),
            signal_to_difference_db=20*math.log10(signal/rms) if rms else None)
    (OUT/'2026-10-13-xtts-security-candidate-pcm-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
