"""Compare the same Hindi reference with the existing GPU Whisper route."""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(REFLOW_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
                  PATH=str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''))


def main():
    from core.providers.stt.whisper_turbo_local import WhisperTurboLocalProvider
    from core.render_context import RenderContext, bind_job
    profile_path = ROOT / 'models/indicf5/references/abhishek/profile.json'
    reference = json.loads(profile_path.read_text(encoding='utf-8'))
    report = dict(completed=False, model_downloaded=False, existing_runtime_only=True)
    with tempfile.TemporaryDirectory(prefix='recognition-baseline-', dir=ROOT / 'temp') as folder:
        job = RenderContext(folder)
        try:
            with bind_job(job):
                provider = WhisperTurboLocalProvider(str(ROOT / 'models/f5/reference-asr'))
                result = provider.transcribe(str(profile_path.parent / reference['reference_audio']))
                report.update(completed=True, transcription=result.to_payload(), worker_released=provider.worker_released)
        except BaseException as error:
            report['error'] = repr(error)
        finally:
            job.cleanup()
            report['workspace_removed'] = not job.workspace.exists()
    (ROOT / 'docs/validation/2026-10-15-recognition-existing-gpu-baseline.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['completed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
