"""Reproduce real recognition timing before any translation model work."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['PATH'] = str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
from core.render_context import RenderContext, bind_job, run_process
from core.providers.resolve import resolve_stt
from dev.verify_workflows import FixtureRegistry
from core.pipeline import ReflowPipeline

job = RenderContext(ROOT/'temp')
try:
    with bind_job(job):
        audio = ROOT/'docs/validation/2026-10-08-app-review-timeline-24k.wav'
        source = ROOT/'docs/validation/2026-10-08-indictrans2-app-review-8fcdfd04/source-excerpt.mp4'
        run_process(['ffmpeg','-v','error','-nostdin','-y','-i',str(source),'-vn','-ac','1','-ar','24000',str(audio)],check=True,timeout=120)
        pipe = ReflowPipeline()
        pipe.registry = FixtureRegistry()
        transcript = pipe._transcribe_source(resolve_stt(pipe.registry,'tiny'),str(audio),True)
        report = dict(duration=pipe.get_duration(str(audio)),transcription=transcript.to_payload())
        (ROOT/'docs/validation/2026-10-08-app-review-timeline.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
finally:
    job.cleanup()
