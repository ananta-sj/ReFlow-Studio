"""Recognize candidate speech using the already installed offline Whisper worker."""
import json
import os
from pathlib import Path
import re
import sys
import time
import argparse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
                  PATH=str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))

def words(text):return re.findall(r'[a-z0-9]+',text.lower())

def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['xtts-candidate','xtts-security-candidate'],default='xtts-candidate')
    parser.add_argument('--label',default='audited-network');args=parser.parse_args()
    assert args.label.replace('-','').isalnum()
    from core.providers.stt.whisper_turbo_local import WhisperTurboLocalProvider
    from core.render_context import RenderContext,bind_job
    evaluation=json.loads((OUT/f'2026-10-13-{args.profile}-live-evaluation-{args.label}.json').read_text(encoding='utf-8'))
    assert evaluation['acceptance']
    job=RenderContext(ROOT/'temp');started=time.monotonic()
    receipt=dict(passed=False,existing_model_only=True,model_downloaded=False,
        naturalness_human_accepted=False,asr_is_not_a_naturalness_judge=True)
    try:
        provider=WhisperTurboLocalProvider(str(ROOT/'models/f5/reference-asr'))
        with bind_job(job):result=provider.transcribe(evaluation['output_file'])
        payload=result.to_payload()
        receipt['transcription']=payload
        # The normalized transcription payload is checked without synthetic text substitutions.
        segments=payload['segments']
        actual=' '.join(segment['text'] for segment in segments)
        expected=evaluation['spoken_text']
        error=distance(words(expected),words(actual))/len(words(expected))
        receipt.update(expected_text=expected,recognized_text=actual,word_error_rate=round(error,4),
            worker_released=provider.worker_released,worker_interpreter=provider.worker_interpreter,
            passed=error<=.2 and provider.worker_released)
    except Exception as error:
        import traceback
        receipt.update(error=str(error),traceback=traceback.format_exc())
    finally:
        job.cleanup()
        receipt['workspace_removed']=not job.workspace.exists()
        receipt['passed'] &= receipt['workspace_removed']
        receipt['elapsed_seconds']=round(time.monotonic()-started,3)
        (OUT/f'2026-10-13-{args.profile}-speech-content.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2));return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
