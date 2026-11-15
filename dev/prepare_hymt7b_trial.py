"""Explicitly approved isolated larger-model trial; active routes stay unchanged."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from dev.prepare_qwen_dialogue_trial import sha
from dev.resume_qwen_trial_downloads import transfer

ASSET=dict(name='HY-MT1.5-7B-Q4_K_M.gguf',size=4624649312,
    sha256='fc87637e4dd29547811a28170770c2ac17725fb7690b7c4aafa4f463c3e77568',
    url='https://huggingface.co/tencent/HY-MT1.5-7B-GGUF/resolve/126325496bc8e3575f1d8615b8ca951d8483f206/HY-MT1.5-7B-Q4_K_M.gguf')

def main():
    profile=json.loads((ROOT/'runtime_profiles/dialogue-hymt-evaluation/profile.json').read_text(encoding='utf-8'))
    runner=Path(profile['runner_profile'])
    for key,value in profile['runner_files'].items():
        if sha(runner/key)!=value:raise ValueError('Verified runner changed')
    folder=ROOT/'runtime_profiles/dialogue-hymt7b-evaluation'
    if folder.exists() and (folder/'.owner').read_text()!='reflow.hymt7b-trial.v1':
        raise ValueError('Unrecognized larger-model trial directory')
    folder.mkdir(exist_ok=True);(folder/'.owner').write_text('reflow.hymt7b-trial.v1')
    if not (folder/'model.gguf').exists() and shutil.disk_usage(folder).free<2*ASSET['size']+1024**3:
        raise RuntimeError('Need about 10 GB free for resumable download and verified assembly')
    names=('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')
    before={name:sha(ROOT/name) for name in names}
    transfer(ASSET,folder/'model.gguf',workers=32)
    if before!={name:sha(ROOT/name) for name in names}:raise ValueError('Application settings changed during preparation')
    receipt=dict(status='prepared-for-evaluation',approved=True,model=ASSET,
        runner_profile=str(runner),runner_files=profile['runner_files'],production_route_changed=False)
    (folder/'profile.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (ROOT/'docs/validation/2026-11-15-hymt7b-preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Larger trial model checksum verified; active models unchanged.',flush=True)

if __name__=='__main__':main()
