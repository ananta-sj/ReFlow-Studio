"""Actual owned Demucs subprocess cancellation, without installing or downloading."""
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',
                  REFLOW_WORKER_PYTHON=str(ROOT/'build/windows-portable/python.exe'))


def main():
    from unittest.mock import patch
    from core.audio_separator import AudioSeparator,DEMUCS_SHA256
    from core.render_context import RenderContext,bind_job,run_process,RenderCancelled
    from core.runtime_integrity import sha
    assert sha(ROOT/'models/uvr/955717e8-8726e21a.th')==DEMUCS_SHA256
    report=dict(passed=False,decoder_boundary_verified=False,packages_installed=False,models_downloaded=False)
    job=RenderContext(ROOT/'temp');done=threading.Event();observed=threading.Event();thread=None
    def stop_active_child():
        deadline=time.monotonic()+60
        while not done.wait(.02) and time.monotonic()<deadline:
            with job.lock:
                active=[process for process in job.processes if process.poll() is None]
            if active:
                report['observed_active_pid']=active[0].pid
                observed.set()
                report['stop_requested_at']=time.monotonic()
                job.request_stop()
                return
    try:
        with bind_job(job):
            source=job.workspace/'source.wav'
            run_process([str(ROOT/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y',
                '-i',str(ROOT/'Sample/2.mp4'),'-t','3','-vn','-ac','2','-ar','44100',str(source)],check=True,timeout=60)
            engine=AudioSeparator('cpu')
            thread=threading.Thread(target=stop_active_child,daemon=True);thread.start()
            try:
                with patch('core.downloader.download_with_progress',side_effect=AssertionError('No model download allowed')):
                    engine.separate(str(source))
            except RenderCancelled:
                report['exact_cancel_type_preserved']=True
            else:
                raise AssertionError('Separation did not raise RenderCancelled')
            report['cancel_return_seconds']=round(time.monotonic()-report.pop('stop_requested_at'),3)
            report['active_child_observed']=observed.is_set()
            report['owned_processes_exited']=not job.processes
    finally:
        done.set()
        if thread:thread.join(timeout=2)
        job.cleanup()
        report['workspace_removed']=not job.workspace.exists()
        report['passed']=all(report.get(key) for key in ['exact_cancel_type_preserved','active_child_observed','owned_processes_exited','workspace_removed'])
        report['source_sha256']={name:sha(ROOT/name) for name in ['core/audio_separator.py','core/run_demucs.py','dev/evaluate_separation_cancellation.py']}
        (ROOT/'docs/validation/2026-10-16-separation-cancellation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
    return not report['passed']


if __name__=='__main__':raise SystemExit(main())
