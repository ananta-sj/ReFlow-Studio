"""Run the existing production provider offline on common comparison inputs."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'


def main():
    import torch
    from core.providers.translation.nllb_local import NLLBLocalProvider
    from core.render_context import RenderContext, bind_job
    from dev.translation_evaluation_cases import load_cases
    torch.set_num_threads(2)
    assert torch.cuda.is_available(), 'GPU required for this baseline'
    report = dict(completed=False, offline=True, production_changed=False,
                  semantic_quality_accepted=False, cases=[])
    receipt = ROOT / 'docs/validation/2026-10-08-nllb-comparison-baseline.json'
    started = time.monotonic()
    job = RenderContext(ROOT / 'temp')
    try:
        with bind_job(job):
            provider = NLLBLocalProvider(str(ROOT / 'models/translation/nllb_600M'), device='cuda:0')
            provider._ensure_loaded()
            report['transformers_version'] = __import__('transformers').__version__
            for case in load_cases():
                before = time.monotonic()
                translated = provider.translate(case['source'], 'Hindi', source_language='English')
                row = {**case, 'translation':translated,
                       'elapsed_seconds':round(time.monotonic()-before, 3)}
                report['cases'].append(row)
                receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(row, ensure_ascii=False), flush=True)
        report['completed'] = True
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),
                      elapsed_seconds=round(time.monotonic()-started, 3))
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(receipt=str(receipt), completed=report['completed'])), flush=True)


if __name__ == '__main__':
    main()
