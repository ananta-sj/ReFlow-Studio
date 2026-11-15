"""Compare an already installed translation alternative on source scene lines."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.providers.translation.m2m100_isolated import IsolatedM2M100Provider
    from core.render_context import RenderContext,bind_job
    cues=json.loads((ROOT/'docs/diagnostics/overnight-20261114-metadata/identity-evaluation/inputs.json').read_text(encoding='utf-8'))['cues']
    job=RenderContext(ROOT/'temp'); provider=IsolatedM2M100Provider(); rows=[]
    try:
        with bind_job(job):
            for index in (25,27,29,31,32):
                text=cues[index]['text']; started=time.monotonic()
                translated=provider.translate(text,'Hindi',source_language='ja')
                rows.append(dict(index=index,source=text,translation=translated,seconds=time.monotonic()-started))
                print(json.dumps(rows[-1],ensure_ascii=True),flush=True)
    finally:
        provider.release();job.cleanup()
        (ROOT/'docs/validation/2026-11-14-scene-m2m100.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
