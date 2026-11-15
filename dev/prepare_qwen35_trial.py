"""Approved replacement of the failed isolated MT trial, without changing app models."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from dev.prepare_qwen_dialogue_trial import sha
from dev.resume_qwen_trial_downloads import transfer
from core.runtime_integrity import safe_path

ASSET=dict(name='Qwen3.5-9B-Q4_K_M.gguf',size=5680522464,
    sha256='03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8',
    url='https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/3885219b6810b007914f3a7950a8d1b469d598a5/Qwen3.5-9B-Q4_K_M.gguf')

def main():
    old=safe_path(ROOT/'runtime_profiles/dialogue-hymt7b-evaluation')
    previous=json.loads((old/'profile.json').read_text(encoding='utf-8'))
    if (old/'.owner').read_text()!='reflow.hymt7b-trial.v1':raise ValueError('Unknown old trial directory')
    runner=safe_path(previous['runner_profile'])
    if not runner.is_relative_to(ROOT/'runtime_profiles'):raise ValueError('Runner must remain inside this project')
    for name,digest in previous['runner_files'].items():
        if sha(runner/name)!=digest:raise ValueError('Verified runner changed')
    target=safe_path(ROOT/'runtime_profiles/dialogue-qwen35-evaluation')
    if target.exists() and (target/'.owner').read_text()!='reflow.qwen35-trial.v1':raise ValueError('Unknown replacement directory')
    target.mkdir(exist_ok=True);(target/'.owner').write_text('reflow.qwen35-trial.v1')
    if not (target/'model.gguf').exists() and shutil.disk_usage(target).free<2*ASSET['size']+1024**3:
        raise RuntimeError('Need about 13 GB free for resumable transfer and checksum verification')
    names=('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')
    before={name:sha(ROOT/name) for name in names}
    transfer(ASSET,target/'model.gguf',workers=32)
    if before!={name:sha(ROOT/name) for name in names}:raise ValueError('Application settings changed during preparation')
    retired=0
    if (target/'profile.json').exists():
        receipt=json.loads((target/'profile.json').read_text(encoding='utf-8'))
        if receipt.get('model',{}).get('sha256')!=ASSET['sha256']:raise ValueError('Replacement receipt changed')
        retired=receipt.get('retired_trial_bytes',0)
    weights=old/'model.gguf'
    if weights.exists():
        if weights.is_symlink() or weights.resolve()!=weights.absolute() or sha(weights)!=previous['model']['sha256']:
            raise ValueError('Old trial weights changed; not removing them')
        retired=weights.stat().st_size;weights.unlink()
    previous.update(weights_retired=True,status='quality-rejected-not-for-production')
    (old/'profile.json').write_text(json.dumps(previous,indent=2),encoding='utf-8')
    receipt=dict(status='prepared-for-evaluation',approved=True,model=ASSET,
        runner_profile=str(runner),runner_files=previous['runner_files'],retired_trial_bytes=retired,
        production_route_changed=False,application_configuration=before)
    (target/'profile.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (ROOT/'docs/validation/2026-11-15-qwen35-preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Replacement checksum verified; failed MT trial weights retired; app models unchanged.',flush=True)

if __name__=='__main__':main()
