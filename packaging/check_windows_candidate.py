"""Check a model-free relocated candidate without changing source settings."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('previous_portable_check', ROOT/'dev/verify_windows_portable_candidate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
EXTRA = '''
checks = {}
for name in ('xtts_runtime','recognition_runtime','m2m100_runtime',
             'separation_runtime','visual_runtime','nllb_runtime'):
    module = __import__('core.'+name, fromlist=['validate'])
    checks[name] = module.validate(root)['identity']
from core.optional_runtime import interpreter
for name in ('f5','vision','musetalk'):
    if not interpreter(name):
        raise RuntimeError('Optional runtime missing: '+name)
print('RUNTIME_RESULT '+json.dumps(checks))
import subprocess
tools = {}
for name in ('ffmpeg','ffprobe'):
    result = subprocess.run([str(root/'ffmpeg/bin'/(name+'.exe')), '-version'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:
        raise RuntimeError('Bundled media tool failed: '+name)
    tools[name] = result.stdout.splitlines()[0]
print('MEDIA_RESULT '+json.dumps(tools))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if not candidate.is_relative_to(ROOT/'dist') or not (candidate/'portable-manifest.json').is_file():
        raise ValueError('Expected a built candidate inside dist')
    manifest = json.loads((candidate/'portable-manifest.json').read_text(encoding='utf-8'))
    previous_audio = json.loads((ROOT/'docs/validation/2026-10-30-context-final-summary.json').read_text(encoding='utf-8'))
    audio_hashes = {name: previous.sha(candidate/name)==digest
                    for name,digest in previous_audio['source_sha256'].items()
                    if name.startswith('core/')}
    forbidden = [r['path'] for r in manifest['files'] if
                 r['path'].split('/')[0] in {'models','outputs','temp','Sample','.git','.codex','.agents'}
                 or r['path'] in {'settings.json','models.json','ui_preferences.json',
                                  'queue_state.json','hardware_profile.json','graph.json'}
                 or '__pycache__' in r['path'].split('/') or r['path'].endswith('/direct_url.json')]
    env = {**os.environ, 'REFLOW_OFFLINE':'1', 'HF_HUB_OFFLINE':'1',
           'TRANSFORMERS_OFFLINE':'1', 'PYTHONDONTWRITEBYTECODE':'1',
           'PYTHONIOENCODING':'utf-8',
           'PATH':str(candidate/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''),
           'HF_HOME':str(candidate/'temp/qa-hf'), 'TORCH_HOME':str(candidate/'temp/qa-torch')}
    started = time.monotonic()
    result = subprocess.run([str(candidate/'build/windows-portable/python.exe'), '-B', '-X','utf8',
                             '-c', previous.CHILD+'\n'+EXTRA], cwd=candidate, env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=240, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    args.report.with_suffix('.worker.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    def payload(prefix):
        return next((json.loads(line[len(prefix):]) for line in result.stdout.splitlines()
                     if line.startswith(prefix)), None)
    core = payload('PORTABLE_RESULT ')
    runtimes = payload('RUNTIME_RESULT ')
    media = payload('MEDIA_RESULT ')
    checks = dict(personal_state_excluded=not forbidden,
                  tested_audio_sources_preserved=bool(audio_hashes) and all(audio_hashes.values()),
                  worker_succeeded=result.returncode==0,
                  relocated_base=core is not None and Path(core['base_dir']).resolve()==candidate,
                  bundled_interpreter=core is not None and Path(core['python_executable']).resolve()==candidate/'build/windows-portable/python.exe',
                  desktop_dependencies=core is not None and not core['library_problems'],
                  interface_present=core is not None and core['frontend_exists'],
                  model_connections_empty=core is not None and not core['registry_entries'],
                  duplicate_launch_blocked=core is not None and core['exclusion'],
                  modern_runtime_recipes_valid=runtimes is not None and len(runtimes)==6,
                  bundled_media_tools_run=media is not None and len(media)==2)
    report = dict(passed=all(checks.values()), checks=checks, forbidden=forbidden,
                  worker=core, runtime_identities=runtimes, tested_audio_sources=audio_hashes,
                  media_tools=media,
                  worker_exit_code=result.returncode,
                  elapsed_seconds=round(time.monotonic()-started,3), release_ready=False,
                  clean_machine_test=False, native_ui_test=False, model_inference_test=False)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='worker'},indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
