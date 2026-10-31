"""Bind timing repair tests, one actual synthesis, replay and preservation."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha

def main():
    out=ROOT/'docs/validation';read=lambda filename:json.loads((out/filename).read_text(encoding='utf-8'))
    tests={}
    for name,filename in [('backend','2026-10-16-speech-timing-final-backend.log'),('focused','2026-10-16-speech-timing-verified-focused.log')]:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',(out/filename).read_text(encoding='utf-8'));assert match,filename
        tests[name]=dict(count=int(match[1]),seconds=float(match[2]),log=filename)
    actual=read('2026-10-16-speech-overflow-diagnosis.json');replay=read('2026-10-16-speech-timing-replay.json')
    checks={}
    checks['one_local_synthesis_passed']=actual['passed'] and actual['owned_processes_exited'] and actual['workspace_removed']
    checks['raw_audio_preserved']=sha(Path(actual['output']))==actual['output_sha256']==replay['raw_source_sha256']
    checks['all_replay_checks_passed']=replay['passed'] and all(replay['checks'].values()) and replay['new_model_calls']==0
    checks['durable_overflow_take_verified']=sha(Path(replay['candidate']))==replay['measured_conflict']['candidate']['sha256']
    checks['review_flag_survives_cleanup']=json.loads(Path(replay['manifest']).read_text())['review_required'] and replay['workspace_removed'] and replay['owned_processes_exited']
    baseline=read('2026-10-10-control-paths-state-integrity.json')['state']
    checks['protected_state_preserved']=all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    original=read('2026-10-13-xtts-candidate-preservation-before.json')['assets']
    checks['original_xtts_assets_preserved']=all(sha(ROOT/name)==digest for name,digest in original.items())
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    from core.separation_runtime import validate as separation
    from core.visual_runtime import validate as visual
    identities={name:call()['identity'] for name,call in [('xtts',xtts),('nllb',nllb),('recognition',recognition),('translation',translation),('separation',separation),('visual',visual)]}
    previous=read('2026-10-16-visual-candidate-acceptance.json')
    checks['six_runtime_identities_preserved']=identities=={**previous['existing_runtime_identities_preserved'],'visual':previous['runtime_identity']}
    checks['built_frontend_preserved']=all(sha(ROOT/name)==digest for name,digest in previous['frontend_dist_sha256'].items())
    sources=['core/speech_timing.py','core/pipeline.py','core/dialogue_adaptation.py','dev/test_speech_integrity.py','dev/test_parallel_speech.py',
        'dev/test_measured_speech_timing.py','dev/diagnose_measured_speech_overflow.py','dev/evaluate_speech_timing_replay.py','dev/finalize_speech_timing.py']
    report=dict(passed=all(checks.values()),checks=checks,tests=tests,test_counts_overlap=True,
        packages_installed=False,models_downloaded=False,defaults_changed=False,release_ready=False,
        new_actual_model_takes=1,seeded_diagnostic_seconds=actual['raw_seconds'],exact_trailing_silence_seconds=actual['trailing_digital_silence_seconds'],
        original_six_second_cue_completed=False,automatic_wording_adaptation_configured=False,original_text_unchanged=True,
        natural_speed_for_spacious_non_hindi=True,last_cue_can_use_existing_media_tail=True,
        runtime_identities=identities,source_sha256={name:sha(ROOT/name) for name in sources})
    (out/'2026-10-16-speech-timing-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));assert report['passed']
if __name__=='__main__':main()
