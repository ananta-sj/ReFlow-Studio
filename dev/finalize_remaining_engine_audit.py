"""Bind remaining-engine repairs to fresh tests, native evidence and preservation."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'core')]
from core.runtime_integrity import sha

def main():
    folder=ROOT/'docs/validation';checks={};tests={}
    for name,file in [('backend','2026-10-16-remaining-engines-full-backend.log'),('focused','2026-10-16-remaining-engines-focused.log')]:
        match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK',(folder/file).read_text(encoding='utf-8'));assert match,file
        tests[name]=dict(count=int(match[1]),seconds=float(match[2]),log=file)
    for name in ['legacy','desktop']:
        report=json.loads((folder/f'2026-10-16-remaining-engines-{name}.json').read_text())
        checks[name+'_probe_completed']=len(report['observations'])==6 and report['saved_state_unchanged'] and report['source_unchanged']
    for name,file in [('filter','2026-10-16-clean-visual-boundary.json'),('gfpgan','2026-10-16-installed-gfpgan-real.json'),('wav2lip','2026-10-16-installed-wav2lip-real.json')]:
        report=json.loads((folder/file).read_text());checks[name+'_real_passed']=report['passed'] and report['workspace_removed']
        if name!='filter':checks[name+'_models_preserved']=report['model_hashes_preserved'] and report['owned_processes_exited']
    baseline=json.loads((folder/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    checks['protected_state_preserved']=all(sha(ROOT/name)==row['current'].lower() for name,row in baseline.items())
    previous=json.loads((folder/'2026-10-16-separation-candidate-acceptance.json').read_text())
    checks['preceding_integration_sources_preserved']=all(sha(ROOT/name)==digest for name,digest in previous['source_sha256'].items() if name.startswith('core/'))
    checks['built_frontend_preserved']=all(sha(ROOT/name)==digest for name,digest in previous['frontend_dist_sha256'].items())
    f5=json.loads((folder/'2026-10-16-f5-import-diagnosis.json').read_text())
    checks['f5_diagnostic_process_and_workspace_released']=f5['owned_processes_exited'] and f5['workspace_removed'] and f5['model_constructed'] is False
    from core.separation_runtime import validate as separation
    from core.xtts_runtime import validate as xtts
    from core.nllb_runtime import validate as nllb
    from core.recognition_runtime import validate as recognition
    from core.m2m100_runtime import validate as translation
    identities={name:call()['identity'] for name,call in [('separation',separation),('xtts',xtts),('nllb',nllb),('recognition',recognition),('translation',translation)]}
    old=json.loads((folder/'2026-10-16-separation-helpers-acceptance.json').read_text())['runtime_identities_preserved']
    checks['runtime_identities_preserved']=all(identities[name]==value for name,value in {**old,'separation':previous['runtime_identity']}.items())
    sources=['core/rvc/rvc_handler.py','core/lipsync_handler.py','core/providers/filter/nudenet_local.py','core/providers/enhancer/gfpgan_local.py',
        'dev/test_optional_cancellation.py','dev/evaluate_clean_visual_boundary.py','dev/evaluate_installed_visual_engine.py',
        'dev/audit_remaining_engine_inventory.py','dev/diagnose_f5_import_timeout.py','dev/finalize_remaining_engine_audit.py']
    report=dict(passed=all(checks.values()),release_ready=False,checks=checks,tests=tests,test_counts_overlap=True,
        packages_installed=False,package_archives_downloaded=False,models_downloaded=False,defaults_changed=False,
        runtime_identities=identities,rvc_conversion_validated=False,musetalk_render_validated=False,f5_import_validated=False,
        new_gpu_tests=False,clean_machine_validated=False,quality_accepted=False,
        f5_import_diagnosis=f5,
        source_sha256={name:sha(ROOT/name) for name in sources})
    (folder/'2026-10-16-remaining-engines-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    assert report['passed']
if __name__=='__main__':main()
