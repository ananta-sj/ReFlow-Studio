"""No-install Demucs runtime probes and real short legacy/desktop separation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]

CODE=r'''
import json,os,sys,time
from pathlib import Path
from unittest.mock import patch
root,scratch,worker=map(Path,sys.argv[1:])
sys.path[:0]=[str(root),str(root/'core')]
os.environ['REFLOW_WORKER_PYTHON']=str(worker)
from core.audio_separator import AudioSeparator
from core.audio_utils import load_playable_audio
from core.render_context import RenderContext,bind_job,run_process
report=dict(completed=False,quality_accepted=False,worker=str(worker))
job=RenderContext(scratch/'temp');started=time.monotonic()
try:
    with bind_job(job):
        source=job.workspace/'source.wav'
        run_process([str(root/'ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-y','-i',str(root/'Sample/2.mp4'),'-t','1','-vn','-ac','2','-ar','44100',str(source)],check=True,timeout=60)
        with patch('core.downloader.download_with_progress',side_effect=AssertionError('No model download authorized')):
            paths=AudioSeparator('cpu').separate(str(source))
        report['stems']=[dict(name=Path(path).name,bytes=Path(path).stat().st_size,duration_ms=len(load_playable_audio(path))) for path in paths]
        assert all(abs(row['duration_ms']-1000)<=50 for row in report['stems'])
        report['completed']=True
except Exception as error:
    report.update(error_type=type(error).__name__,error=str(error))
finally:
    report['owned_processes_exited']=not job.processes
    job.cleanup()
    report.update(workspace_removed=not job.workspace.exists(),elapsed_seconds=round(time.monotonic()-started,3))
    (scratch/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
'''


def main():
    from core.runtime_probe import probe
    from core.runtime_integrity import sha
    profiles={'legacy':ROOT/'build/windows-portable/python.exe',
              'desktop':ROOT/'runtime_profiles/desktop-candidate/python.exe',
              'translation':ROOT/'runtime_profiles/translation-candidate/python.exe'}
    weights=ROOT/'models/uvr/955717e8-8726e21a.th'
    from core.audio_separator import DEMUCS_SHA256
    assert sha(weights)==DEMUCS_SHA256
    baseline=json.loads((ROOT/'docs/validation/2026-10-10-control-paths-state-integrity.json').read_text())['state']
    before={name:sha(ROOT/name) for name in baseline}
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8',
         'OMP_NUM_THREADS':'2','REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
         'PATH':str(ROOT/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')}
    report=dict(audit_completed=False,release_ready=False,packages_installed=False,models_downloaded=False,
                probes={},real_runs={},source_seconds=1,model_sha256=DEMUCS_SHA256)
    for name,executable in profiles.items():
        report['probes'][name]=probe('demucs',str(executable),'cpu')
    # Both actual calls start in the desktop parent. Only the worker selection changes.
    for name in ('desktop','legacy'):
        with tempfile.TemporaryDirectory(prefix='separation-audit-',dir=ROOT/'temp') as scratch:
            result=subprocess.run([str(profiles['desktop']),'-B','-c',CODE,str(ROOT),scratch,str(profiles[name])],
                env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
            assert result.returncode==0,result.stderr[-2000:]
            report['real_runs'][name]=json.loads((Path(scratch)/'result.json').read_text())
    report['protected_state_unchanged']=all(sha(ROOT/name)==value==baseline[name]['current'].lower() for name,value in before.items())
    report['weights_unchanged']=sha(weights)==DEMUCS_SHA256
    report['runtime_migration_needed']=not report['real_runs']['desktop']['completed']
    report['audit_completed']=all([report['protected_state_unchanged'],report['weights_unchanged'],
        *(row['workspace_removed'] and row['owned_processes_exited'] for row in report['real_runs'].values())])
    report['source_sha256']={name:sha(ROOT/name) for name in ['core/audio_separator.py','core/run_demucs.py',
        'core/python_runtime.py','core/runtime_checks.py','core/runtime_probe_contract.py','core/runtime_probe_worker.py',
        'dev/audit_separation_boundary.py','dev/test_audio_separator.py']}
    destination=ROOT/'docs/validation/2026-10-16-separation-boundary.json'
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report['audit_completed'] else 1


if __name__=='__main__':raise SystemExit(main())
