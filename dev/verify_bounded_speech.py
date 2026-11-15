"""Exercise real GPU duration rejection and recovery, without publishing audio."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.render_context import RenderContext,bind_job,run_process
    from core.cuda_providers import CudaXTTSProvider
    from core.speech_generation_budget import SpeechGenerationLimitExceeded
    from core.audio_utils import load_speech_audio
    job=RenderContext(ROOT/'temp'); provider=CudaXTTSProvider(); report={}
    try:
        with bind_job(job):
            source=next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
            ref=job.workspace/'reference.wav'; output=job.workspace/'speech.wav'
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-ss','231.8',
                '-i',str(source),'-t','6','-vn','-ac','1','-ar','24000',str(ref)],check=True,timeout=60)
            started=time.monotonic()
            try:
                provider.synthesize_bounded('माँ, क्या हम अब चलें?',str(output),'hi',str(ref),max_seconds=.05)
                raise AssertionError('An unfinished take was accepted')
            except SpeechGenerationLimitExceeded:
                assert not output.exists(), 'Rejected audio was published'
            report['unfinished_rejected_without_file']=True
            report['first_call_seconds']=time.monotonic()-started
            started=time.monotonic()
            provider.synthesize_bounded('माँ, क्या हम अब चलें?',str(output),'hi',str(ref),max_seconds=12,alternate_take=True)
            report['completed_audio_seconds']=len(load_speech_audio(output))/1000
            report['recovery_call_seconds']=time.monotonic()-started
            report['human_quality_accepted']=False
            print(json.dumps(report),flush=True)
    finally:
        provider.release(); job.cleanup()
        (ROOT/'docs/validation/2026-11-14-bounded-speech.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__': main()
