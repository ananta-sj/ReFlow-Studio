"""Owner-approved replacement of failed trial weights; reuse the verified runner."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from dev.prepare_qwen_dialogue_trial import sha
from dev.resume_qwen_trial_downloads import transfer

ASSET=dict(name='HY-MT1.5-1.8B-Q8_0.gguf',size=1908528288,
    sha256='6789b06d0902f2f5312c0e1703d56ccbddfcfb6c653d22519b7c720f7db9a98e',
    url='https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/resolve/265b2e615a7dc9b06c435dc878829ad99a512ba2/HY-MT1.5-1.8B-Q8_0.gguf')


def main():
    old=ROOT/'runtime_profiles/dialogue-qwen-evaluation';profile=json.loads((old/'profile.json').read_text(encoding='utf-8'))
    if profile['status']!='quality-rejected-not-for-production':raise ValueError('Previous trial is not marked rejected')
    runner={key:value for key,value in profile['files'].items() if Path(key).parts[0]=='bin'}
    if not runner:raise ValueError('No verified runner files in the preparation receipt')
    for key,value in runner.items():
        if sha(old/key)!=value:raise ValueError('Verified portable runner changed')
    target=ROOT/'runtime_profiles/dialogue-hymt-evaluation'
    if target.exists() and (target/'.owner').read_text()!='reflow.hymt-dialogue-trial.v1':raise ValueError('Unrecognized trial directory')
    target.mkdir(exist_ok=True);(target/'.owner').write_text('reflow.hymt-dialogue-trial.v1')
    before={name:sha(ROOT/name) for name in ('settings.json','models.json','graph.json','ui_preferences.json','hardware_profile.json')}
    transfer(ASSET,target/'model.gguf',workers=32)
    previous=old/'model.gguf';removed=0
    if (target/'profile.json').exists():
        removed=json.loads((target/'profile.json').read_text(encoding='utf-8')).get('retired_qwen_bytes',0)
    if previous.exists():
        if previous.resolve()!=previous or not previous.is_relative_to(ROOT) or previous.stat().st_size!=profile['model']['size'] or sha(previous)!=profile['model']['sha256']:
            raise ValueError('Failed model changed; do not delete it')
        removed=previous.stat().st_size;previous.unlink()
    profile['weights_retired']=True
    (old/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    if before!={name:sha(ROOT/name) for name in before}:raise ValueError('Application configuration changed during preparation')
    receipt=dict(status='prepared-for-evaluation',approved=True,model=ASSET,runner_profile=str(old),runner_files=runner,
        retired_qwen_bytes=removed,application_configuration=before,production_route_changed=False)
    (target/'profile.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (ROOT/'docs/validation/2026-11-14-hymt-preparation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Replacement verified; failed Qwen weights removed; active app models unchanged.',flush=True)


if __name__=='__main__':main()
