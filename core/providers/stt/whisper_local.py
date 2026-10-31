from core.render_context import current_job, check_cancelled, run_process
"""Local Whisper STT provider - shells out to run_stt.py in a fresh
subprocess, matching the pipeline's original behavior. That subprocess
boundary is deliberate (see run_stt.py): it keeps Whisper's CPU-only
faster-whisper load isolated from the main process, so a crash there
can't take the app down with it. Transcribing in-process here would
silently drop that isolation."""

import json
import os
import subprocess
import sys
import tempfile

from core.providers.base import STTProvider
from core.transcription import normalize_transcription
from core.python_runtime import project_root

_CORE_DIR = str(project_root() / 'core')
_WORKER_SCRIPT = os.path.join(_CORE_DIR, "run_stt.py")


class WhisperLocalProvider(STTProvider):
    def __init__(self, model_size="medium", runtime='legacy'):
        if runtime not in (None, 'legacy', 'isolated'):
            raise ValueError('Unknown recognition runtime selection')
        self.model_size = model_size
        self.runtime = runtime or 'legacy'

    def transcribe(self, audio_path, source_language='auto'):
        from core.source_language import normalize_source_selection
        selected = normalize_source_selection(source_language)
        self.worker_interpreter = None
        self.runtime_identity = None
        from core.recognition_runtime import resolve
        route = resolve(self.runtime)
        self.worker_interpreter = route['executable']
        self.runtime_identity = route.get('identity')
        self.device = 'cpu'
        with tempfile.TemporaryDirectory(dir=current_job().workspace if current_job() else None) as tmp_dir:
            out_json = os.path.join(tmp_dir, "transcript.json")
            # timeout: transcription can legitimately take a while on a long
            # file, especially CPU-only, but an unbounded call meant a
            # genuine hang in the worker process would block the render
            # thread forever with no way to tell it apart from "still
            # working" - bridge/api.py's render loop turns any exception
            # (including this timeout) into a visible render_error.
            log_path = os.path.join(tmp_dir, 'worker.log')
            try:
                with open(log_path, 'wb') as log:
                    run_process(
                        [self.worker_interpreter, '-B', _WORKER_SCRIPT, audio_path, out_json, self.model_size]
                        + ([selected] if selected != 'auto' else []),
                        check=True, timeout=3600, stdout=log, stderr=subprocess.STDOUT,
                    )
            except subprocess.CalledProcessError as exc:
                with open(log_path, 'rb') as log:
                    log.seek(0, os.SEEK_END)
                    log.seek(max(0, log.tell() - 6000))
                    detail = log.read().decode('utf-8', errors='replace')
                raise RuntimeError(f'Transcription worker failed: {detail}') from exc
            with open(out_json, "r", encoding="utf-8") as f:
                return normalize_transcription(json.load(f))
