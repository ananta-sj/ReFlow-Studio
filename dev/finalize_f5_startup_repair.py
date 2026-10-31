"""Bind F5 startup repair evidence to tests and protected original assets."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha

def main():
    folder=ROOT/'docs/validation';checks={};tests={}
    read=lambda name:json.loads((folder/name).read_text(encoding='utf-8'))
    for name,file in [('backend','2026-10-16-f5-startup-final-backend.log'),('focused','2026-10-16-f5-startup-final-focused.log')]:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',(folder/file).read_text(encoding='utf-8'));assert match,file
        tests[name]=dict(count=int(match[1]),seconds=float(match[2]),log=file)
    startup=read('2026-10-16-f5-lazy-startup.json')
    checks['bounded_startup_passed']=startup['import_passed'] and startup['seconds']<55 and not startup['model_constructed']
    checks['heavy_optional_imports_deferred']=not any(startup[key] for key in ['transformers_loaded','trainer_loaded','wandb_loaded'])
    probe=read('2026-10-16-f5-lazy-probe-complete.json')
    checks['unchanged_deadline_probe_passed']=probe['status']=='passed' and not probe['model_loaded'] and probe['reference_asr_deferred']
    asr=read('2026-10-16-f5-reference-asr.json')
    checks['real_reference_asr_passed']=asr['passed'] and asr['expected_words_match'] and asr['reference_asr_released'] and not asr['f5_speech_model_constructed']
    speech=read('2026-10-16-f5-lazy-speech-final.json')
    checks['final_real_speech_passed']=speech['passed'] and speech['peak']>0 and speech['source_and_model_hashes_preserved'] and sha(Path(speech['output']))==speech['output_sha256']
    checks['owned_jobs_cleaned']=all(row['owned_processes_exited'] and row['workspace_removed'] for row in [startup,asr,speech])
    checks['upstream_sources_and_speech_model_preserved']=all(sha(ROOT/name)==digest for name,digest in speech['asset_sha256'].items())
    baseline=read('2026-10-10-control-paths-state-integrity.json')['state']
    checks['protected_state_preserved']=all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    previous=read('2026-10-16-separation-candidate-acceptance.json')
    checks['built_frontend_preserved']=all(sha(ROOT/name)==digest for name,digest in previous['frontend_dist_sha256'].items())
    preceding=read('2026-10-16-remaining-engines-acceptance.json')
    checks['preceding_engine_repairs_preserved']=all(sha(ROOT/name)==digest for name,digest in preceding['source_sha256'].items() if name.startswith('core/'))
    from core.separation_runtime import validate as separation
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    identities={name:call()['identity'] for name,call in [('separation',separation),('xtts',xtts),('nllb',nllb),('recognition',recognition),('translation',translation)]}
    checks['five_runtime_identities_preserved']=identities==preceding['runtime_identities']
    sources=['core/f5_imports.py','core/feature_worker.py','core/runtime_probe_worker.py','dev/test_f5_imports.py','dev/test_f5_worker_order.py','dev/test_runtime_probe.py',
        'dev/diagnose_f5_lazy_startup.py','dev/evaluate_f5_lazy_speech.py','dev/evaluate_f5_reference_asr.py','dev/prepare_visual_runtime_feasibility.py','dev/finalize_f5_startup_repair.py']
    report=dict(passed=all(checks.values()),release_ready=False,checks=checks,tests=tests,test_counts_overlap=True,
        packages_installed=False,package_archives_downloaded=False,models_downloaded=False,defaults_changed=False,
        runtime_identities=identities,quality_accepted=False,hindi_quality_validated=False,new_gpu_tests=False,
        automatic_reference_full_render_validated=False,real_persistent_session_validated=False,
        source_sha256={name:sha(ROOT/name) for name in sources})
    (folder/'2026-10-16-f5-startup-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    assert report['passed']
if __name__=='__main__':main()
