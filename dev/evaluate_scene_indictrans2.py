"""Evaluate the already installed English-Hindi model on aligned scene turns."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]

def main():
    from core.render_context import RenderContext,bind_job
    from core.providers.translation.indictrans2_local import IndicTrans2LocalProvider
    evidence=json.loads((ROOT/'docs/validation/hymt-trial-20261114/full-contextual-english-captions-report.json').read_text(encoding='utf-8'))
    report=dict(completed=False,production_route_changed=False,human_quality_accepted=False,results=[])
    job=RenderContext(ROOT/'temp');provider=IndicTrans2LocalProvider(ROOT/'models/translation/indictrans2-evaluation')
    try:
        with bind_job(job):
            for case in evidence['results']:
                started=time.monotonic()
                translated=provider.translate(case['source'],'Hindi',source_language='en')
                row={k:case[k] for k in ('name','source','source_indices','original_japanese','caption_evidence','available_seconds')}
                row.update(translation=translated,seconds=time.monotonic()-started)
                report['results'].append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
            report['completed']=True
    except Exception as exc:
        report['error']=str(exc);raise
    finally:
        provider.release();job.cleanup()
        (ROOT/'docs/validation/2026-11-15-scene-indictrans2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
