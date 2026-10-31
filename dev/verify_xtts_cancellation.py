"""Observe real XTTS generation, cancel at a token boundary, preserve prior output."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
from core.render_context import RenderContext, RenderCancelled, bind_job, run_process
from core import generation_control
from core.model_assets import RECOVERY_SOURCES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/validation/2026-10-04-xtts-cancellation.json')
    args = parser.parse_args()
    job = RenderContext(ROOT / 'temp')
    observed = threading.Event()
    report = dict(acceptance=False, engine='xtts', offline=True, prior_output_preserved=False)
    started = time.monotonic()
    try:
        from core.tts.tts_handler import TTSHandler
        from transformers import StoppingCriteria
        reference = job.workspace / 'reference.wav'
        with bind_job(job):
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '6', '-vn', '-ar', '24000', '-ac', '1', str(reference)], check=True, timeout=60)
        model = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']), language='en')
        output = job.workspace / 'synthesis.wav'
        output.write_bytes(reference.read_bytes())
        prior = hashlib.sha256(output.read_bytes()).hexdigest()
        original_kwargs = generation_control.generation_kwargs

        class ObservedCriteria(StoppingCriteria):
            def __init__(self, criteria):
                self.criteria = criteria

            def __call__(self, input_ids, scores, **kwargs):
                observed.set()
                return self.criteria(input_ids, scores, **kwargs)

            def __deepcopy__(self, memo):
                return self

        def instrument():
            kwargs = original_kwargs()
            kwargs['stopping_criteria'] = [ObservedCriteria(value) for value in kwargs['stopping_criteria']]
            return kwargs

        def synthesize():
            with bind_job(job):
                model.generate_audio('This is a longer speech generation check. ' * 8,
                                     str(output), 'en', str(reference))

        with patch.object(generation_control, 'generation_kwargs', instrument), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(synthesize)
            if not observed.wait(120):
                job.request_stop()
                if future.done():
                    future.result()
                raise RuntimeError('No real generation token boundary was observed')
            cancelled_at = time.monotonic()
            job.request_stop()
            try:
                future.result(timeout=15)
            except RenderCancelled:
                report['cancellation_seconds'] = round(time.monotonic() - cancelled_at, 3)
            else:
                raise RuntimeError('XTTS generation ignored cancellation')
        report['prior_output_preserved'] = hashlib.sha256(output.read_bytes()).hexdigest() == prior
        if not report['prior_output_preserved'] or list(job.workspace.glob('.reflow-*')):
            raise RuntimeError('Cancelled generation changed output or retained a staging file')
        report.update(acceptance=True, real_token_boundary_observed=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic() - started, 3), workspace_removed=not job.workspace.exists())
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
