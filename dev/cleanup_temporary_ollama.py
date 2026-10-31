"""Fallback teardown of one completed/aborted owned evaluation, never global Ollama."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('receipt',type=Path)
    args=parser.parse_args()
    report=json.loads(args.receipt.read_text(encoding='utf-8'))
    owned=Path(report['temporary_root']).absolute()
    if owned.resolve()!=owned or not owned.is_relative_to((ROOT/'temp').resolve()) or not owned.name.startswith('ollama-eval-'):
        raise RuntimeError('Refusing teardown outside the evaluation workspace')
    if not owned.exists():
        print('Evaluation runtime/model directory is already absent')
        return
    if (owned/'EVALUATION_OWNER').read_text(encoding='utf-8')!=owned.name:
        raise RuntimeError('Ownership marker mismatch')
    for directory,dirs,files in os.walk(owned,followlinks=False):
        for path in [Path(directory),*(Path(directory)/name for name in dirs+files)]:
            if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
                raise RuntimeError('Refusing teardown through reparse points')
    runtime=(owned/'runtime').resolve()
    processes=[]
    for process in psutil.process_iter(['exe','cmdline']):
        try:
            executable=process.info.get('exe')
            if executable and Path(executable).resolve().is_relative_to(runtime):
                processes.append(process)
            elif any(name in part for part in process.info.get('cmdline') or []
                     for name in ('evaluate_temporary_ollama.py', 'evaluate_temporary_dialogue_model.py')):
                raise RuntimeError('An evaluator is still running; wait for its own teardown')
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    for process in processes:
        try: process.terminate()
        except psutil.NoSuchProcess: pass
    _,alive=psutil.wait_procs(processes,timeout=5)
    for process in alive:
        try: process.kill()
        except psutil.NoSuchProcess: pass
    _,alive=psutil.wait_procs(alive,timeout=5)
    if alive: raise RuntimeError('Owned runtime processes have not exited')
    removed=sum(path.stat().st_size for path in owned.rglob('*') if path.is_file())
    for attempt in range(5):
        try:
            shutil.rmtree(owned)
            break
        except PermissionError:
            if attempt==4: raise
            time.sleep(.2*(attempt+1))
    result=dict(temporary_root=str(owned),removed_bytes=removed,temporary_runtime_models_removed=not owned.exists(),
        stopped_owned_pids=[process.pid for process in processes],fallback_cleanup=True)
    args.receipt.with_name(args.receipt.stem+'-fallback-cleanup.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
