"""Compare existing-model routes on actual problem cues; never auto-approve text."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')


def main():
    from core.cuda_providers import CudaNLLBProvider
    from core.render_context import RenderContext, bind_job
    provider = CudaNLLBProvider(str(ROOT/'models/translation/nllb_600M'))
    job = RenderContext(ROOT/'temp')
    rows = []
    try:
        with bind_job(job):
            for source in ('私はとても ここを発つ気になれないの',
                           '1日も早く2人で おじい様の所へ行きなさいって',
                           'こら バロン ダメだったら フフフッ'):
                direct = provider.translate(source, 'Hindi', source_language='ja')
                english = provider.translate(source, 'English', source_language='ja')
                pivot = provider.translate(english, 'Hindi', source_language='en')
                rows.append(dict(source=source, direct=direct, english=english, pivot=pivot))
                print(json.dumps(rows[-1], ensure_ascii=True), flush=True)
    finally:
        provider.release()
        job.cleanup()
        path = ROOT/'docs/validation/2026-11-13-translation-pivot.json'
        path.write_text(json.dumps(dict(automatic_acceptance=False, cues=rows), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
