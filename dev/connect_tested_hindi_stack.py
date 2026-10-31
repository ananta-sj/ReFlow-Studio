"""Connect existing accepted assets through app APIs; preserve prior selection evidence."""
import json
from pathlib import Path
import shutil
import sys
import threading
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]

def main():
    from core.model_registry import ModelRegistry
    from core.cue_review import digest
    from bridge.api import PythonBridge
    receipt=ROOT/'docs/validation/2026-10-09-tested-hindi-app-selection.json'
    if receipt.exists():
        raise ValueError('Configuration already recorded; inspect before repeating')
    validation=json.loads((ROOT/'docs/validation/2026-10-09-automatic-hindi-video-95a5a0e6.json').read_text(encoding='utf-8'))
    assert validation['completed'] and validation['full_decode_pass']
    bridge=PythonBridge.__new__(PythonBridge)
    bridge.registry=ModelRegistry()
    bridge._render_lock=threading.Lock()
    bridge._render_thread=None
    bridge._active_downloads=set()
    stages=('stt','translation','tts')
    before={stage:bridge.registry.get_active(stage) for stage in stages}
    # The examined setup has no selected engines. Refuse to overwrite an
    # independently changed user selection between audit and execution.
    if any(before.values()):
        raise ValueError('App selections changed since audit; preserve the current selection')
    registry=ROOT/'models.json'
    backup=ROOT/'docs/validation/2026-10-09-model-selection-before.json'
    shutil.copy2(registry,backup)
    report=dict(completed=False,prior_selection={stage:None for stage in stages},
        registry_backup=str(backup),registry_backup_sha256=digest(backup),new_downloads=False,
        new_packages=False,existing_runtime_changed=False,voice_profile_changed=False,
        scope='Existing installed English-to-Hindi engines; no other-language support inferred',connections=[])
    try:
        calls=[('stt',bridge.connect_whisper_turbo),('translation',bridge.connect_indictrans2),
            ('tts',lambda:bridge.connect_hindi_voice('abhishek','cuda:0',confirmed=True))]
        for stage,connect in calls:
            result=connect()
            if not result['ok']: raise RuntimeError(result.get('message','Connection failed'))
            entry=result['model']
            selected=bridge.set_active_model(stage,entry['id'])
            if not selected['ok']: raise RuntimeError(selected.get('message','Selection failed'))
            report['connections'].append({key:entry.get(key) for key in ('id','stage_type','display_name','request_preset','local_path')})
        reopened=ModelRegistry()
        assert all(reopened.get_active(stage)['id']==row['id'] for stage,row in zip(stages,report['connections']))
        report.update(completed=True,selection_reopens_correctly=True,registry_sha256_after=digest(registry))
    finally:
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(receipt,flush=True)

if __name__=='__main__': main()
