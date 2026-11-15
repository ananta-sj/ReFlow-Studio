"""Evaluate installed NLLB using embedded English captions as explicit evidence."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.render_context import RenderContext,bind_job
    from core.providers.translation.nllb_local import NLLBLocalProvider
    cues=json.loads((ROOT/'docs/validation/2026-11-14-scene-english-captions.json').read_text(encoding='utf-8'))
    job=RenderContext(ROOT/'temp'); provider=NLLBLocalProvider(str(ROOT/'models/translation/nllb_600M'),runtime='isolated'); rows=[]
    try:
        with bind_job(job):
            for index in (2,4,7,8):
                source=cues[index]['text']; started=time.monotonic()
                translated=provider.translate(source,'Hindi',source_language='en')
                rows.append(dict(source=source,translation=translated,start=cues[index]['start'],end=cues[index]['end'],seconds=time.monotonic()-started))
                print(json.dumps(rows[-1],ensure_ascii=True),flush=True)
    finally:
        provider.release();job.cleanup()
        (ROOT/'docs/validation/2026-11-14-caption-nllb.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
