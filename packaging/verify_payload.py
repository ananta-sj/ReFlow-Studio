"""Offline, model-free bundle checks; report limits explicitly."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    report_path = Path(sys.argv[1]).resolve()
    report = dict(passed=False,model_inference_test=False,clean_machine_test=False,
                  release_ready=False,root=str(ROOT),python=sys.executable)
    try:
        import main as application
        import config
        from core.integrity import IntegrityDoctor
        from core.model_registry import ModelRegistry
        from core.application_lock import ApplicationLock, AlreadyRunning
        from core.python_runtime import worker_python
        problems = IntegrityDoctor().check_libraries()
        with ApplicationLock(ROOT):
            try:
                with ApplicationLock(ROOT):
                    pass
            except AlreadyRunning:
                exclusion=True
            else:
                exclusion=False
        tools = {}
        for name in ('ffmpeg','ffprobe'):
            executable=shutil.which(name)
            if executable:
                result=subprocess.run([executable,'-version'],capture_output=True,
                    text=True,encoding='utf-8',errors='replace',timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                tools[name]=dict(path=executable,passed=result.returncode==0)
        checks=dict(desktop_dependencies=not problems,frontend_present=application.DIST_INDEX.is_file(),
                    relocated_root=Path(config.BASE_DIR).resolve()==ROOT,
                    packaged_python=Path(sys.executable).resolve().is_relative_to(ROOT),
                    real_worker=Path(worker_python()).resolve()==Path(sys.executable).resolve(),
                    no_model_connections=not ModelRegistry().list(),duplicate_launch_blocked=exclusion)
        report.update(checks=checks,library_problems=problems,media_tools=tools,
                      passed=all(checks.values()))
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error))
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
