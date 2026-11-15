"""Measure exact inference phases for a short Hindi line, using existing assets."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--experiments',action='store_true')
    parser.add_argument('--fast-only',action='store_true')
    args=parser.parse_args()
    from core.cuda_runtime import validate
    from core.render_context import RenderContext, bind_job, run_process
    from core.feature_session import FeatureSession
    from core.audio_utils import load_speech_audio
    job = RenderContext(ROOT/'temp')
    report = []
    worker = None
    try:
        with bind_job(job):
            reference = job.workspace/'reference.wav'
            source = next(Path(r'C:\Users\19shr\Downloads\New folder').glob('*Perrine HD 01*'))
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'), '-v','error','-nostdin','-y','-ss','231.8',
                '-i',str(source),'-t','6','-vn','-ac','1','-ar','24000',str(reference)],check=True,timeout=60)
            route = validate('speech')
            modes=['fast-cudnn','fast-cudnn'] if args.fast_only else ['native','fast-cudnn','amp'] if args.experiments else ['baseline','baseline']
            worker = FeatureSession(job,route['executable'],dict(stage='speech',model_path=str(ROOT/'models/xtts/default'),profile_modes=modes),
                worker=ROOT/'dev/profile_cuda_speech_worker.py',operation='cuda_session')
            for mode, alternate in zip(modes, (False,False,False) if args.experiments else (False,True)):
                output = job.workspace/('take-'+mode+'-'+str(alternate)+'.wav')
                started = time.monotonic()
                worker.call(dict(text='माँ, क्या हम अब चलें?',language='hi',reference_audio=str(reference),
                    output_path=str(output),alternate_take=alternate))
                row = dict(mode=mode,alternate=alternate,elapsed_seconds=time.monotonic()-started,
                    audio_seconds=len(load_speech_audio(output))/1000,
                    profile=json.loads((worker.folder/'timings.jsonl').read_text().splitlines()[-1]))
                report.append(row)
                print(json.dumps({key:value for key,value in row.items() if key!='profile'}),flush=True)
    finally:
        if worker: worker.close()
        destination=ROOT/'docs/validation'/('2026-11-14-xtts-phase-cold-fast.json' if args.fast_only else '2026-11-14-xtts-phase-experiments.json' if args.experiments else '2026-11-14-xtts-phase-profile.json')
        destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
        job.cleanup()


if __name__=='__main__': main()
