"""Small real transfer through the owned-process repository downloader."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
from core.render_context import RenderContext, bind_job
from core.downloader import download_with_progress


def main():
    job = RenderContext(ROOT / 'temp')
    report = {'acceptance': False, 'revision': '84e5a410d9cead4de2f847e7c9369a6440bdfaca'}
    try:
        with bind_job(job):
            destination = job.workspace / 'snapshot'
            updates = list(download_with_progress('https://huggingface.co/SWivid/F5-TTS', str(destination),
                allow_patterns=['F5TTS_v1_Base/vocab.txt'], revision=report['revision']))
            path = destination / 'F5TTS_v1_Base/vocab.txt'
            if not path.is_file() or path.stat().st_size == 0 or updates[-1]['phase'] != 'done':
                raise RuntimeError('Repository transfer did not publish its requested file')
            report.update(acceptance=True, bytes=path.stat().st_size, updates=len(updates))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        (ROOT / 'docs/validation/2026-10-04-hf-process-transfer.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report))


if __name__ == '__main__':
    main()
