"""Model-free relocated core checks; does not claim a clean-machine UI test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

CHILD = r'''
import json, os, sys
from pathlib import Path
root = Path.cwd()
sys.path[:0] = [str(root), str(root/'core')]
import main, config
from core.integrity import IntegrityDoctor
from core.application_lock import ApplicationLock, AlreadyRunning
from core.model_registry import ModelRegistry
from core.settings import Settings
from core.pipeline_contracts import PipelineSpec
libraries = IntegrityDoctor().check_libraries()
registry = ModelRegistry()
templates = [PipelineSpec(name, dict(target_lang='hi', source_language='en')).to_payload()
             for name in ('audio_dub','video_dub','video_dub_lipsync','subtitle_translate')]
with ApplicationLock(root):
    try:
        with ApplicationLock(root):
            pass
    except AlreadyRunning:
        exclusion = True
    else:
        exclusion = False
print('PORTABLE_RESULT ' + json.dumps(dict(root=str(root),base_dir=config.BASE_DIR,
    python=sys.version,python_executable=sys.executable,frontend_exists=main.DIST_INDEX.is_file(),
    library_problems=libraries, registry_entries=registry.list(),
    settings=Settings().all(),templates=templates,exclusion=exclusion)))
'''


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if not candidate.is_relative_to(ROOT / 'dist') or not (candidate / 'portable-manifest.json').is_file():
        raise ValueError('Expected an owned built candidate inside dist')
    receipt = dict(passed=False, candidate=str(candidate), clean_machine_test=False,
                   native_ui_test=False, model_inference_test=False)
    started = time.monotonic()
    try:
        manifest = json.loads((candidate / 'portable-manifest.json').read_text(encoding='utf-8'))
        missing = [item['path'] for item in manifest['files']
                   if not (candidate / item['path']).is_file() or (candidate / item['path']).stat().st_size != item['bytes']]
        forbidden = [item['path'] for item in manifest['files']
            if item['path'].split('/')[0] in {'models','outputs','temp','Sample','.git','.codex','runtime_profiles'}
            or item['path'] in {'settings.json','models.json','graph.json','queue_state.json','ui_preferences.json','hardware_profile.json'}
            or '__pycache__' in item['path'].split('/')]
        protected = ('main.py','README.txt','config.py','core/application_lock.py','bridge/api.py','frontend/dist/index.html')
        hashes = {name: dict(source=sha(ROOT / name), candidate=sha(candidate / name)) for name in protected}
        executable = candidate / 'build/windows-portable/python.exe'
        env = {**os.environ, 'REFLOW_OFFLINE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
               'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8',
               'PATH':str(candidate / 'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')}
        result = subprocess.run([str(executable),'-B','-X','utf8','-c',CHILD],cwd=candidate,
            env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=180,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        args.report.with_suffix('.worker.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        payload = next((json.loads(line.removeprefix('PORTABLE_RESULT ')) for line in result.stdout.splitlines()
                        if line.startswith('PORTABLE_RESULT ')), None)
        receipt.update(worker_exit_code=result.returncode,worker=payload,source_hashes=hashes,
                       inventory_files=len(manifest['files']),inventory_mismatches=missing,forbidden_inventory=forbidden)
        checks = dict(inventory_complete=not missing,personal_state_and_caches_excluded=not forbidden,
            current_app_files=all(item['source']==item['candidate'] for item in hashes.values()),
            relocated_worker_succeeded=result.returncode==0 and payload is not None,
            base_dir_relocated=payload is not None and Path(payload['base_dir']).resolve()==candidate,
            core_libraries_import=payload is not None and not payload['library_problems'],
            frontend_exists=payload is not None and payload['frontend_exists'],
            no_personal_model_connections=payload is not None and not payload['registry_entries'],
            duplicate_launch_blocked=payload is not None and payload['exclusion'])
        receipt.update(checks=checks,passed=all(checks.values()))
    except Exception as error:
        receipt.update(error_type=type(error).__name__,error=str(error))
    finally:
        receipt['elapsed_seconds']=round(time.monotonic()-started,3)
        args.report.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in receipt.items() if key not in {'worker','source_hashes'}},indent=2))
    return 0 if receipt['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
