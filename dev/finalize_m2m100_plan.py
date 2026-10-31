"""Bind approved-scope fixes and a not-yet-approved installation proposal."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
OUT=ROOT/'docs/validation'


def main():
    from core.runtime_integrity import sha
    from core.xtts_runtime import validate as existing
    from core.nllb_runtime import validate as nllb
    plan_path=OUT/'2026-10-16-m2m100-runtime-proposal.json'
    plan=json.loads(plan_path.read_text())
    review=json.loads((OUT/'2026-10-16-m2m100-runtime-independent-review.json').read_text())
    advisories=json.loads((OUT/'2026-10-16-m2m100-runtime-advisories.json').read_text())
    assert review['metadata_checks_passed'] and review['proposal_sha256']==sha(plan_path)
    assert advisories['complete'] and advisories['match_count']==0
    assert existing()['identity']==plan['source_runtime_identity']
    assert nllb()['identity']=='1df86b1800ee5f17229b3be3972f2bfb83e28a2303d9b48d7caf2e2f947870bd'
    for name,count in [('2026-10-16-m2m100-lifecycle-focused.log',17),('2026-10-16-m2m100-lifecycle-full-backend.log',853)]:
        assert re.search(rf'Ran {count} tests.*?\nOK',(OUT/name).read_text(encoding='utf-8'),re.S)
    states=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in states.items())
    recovery=json.loads((ROOT/'core/recovery_sources.json').read_text())
    models={}
    for feature in ['m2m100','nllb']:
        source=recovery[feature]
        row=next(row for row in source['files'] if row['name']=='pytorch_model.bin')
        value=sha(ROOT/source['folder']/row['name'])
        assert value==row['sha256']
        models[feature]=value
    assert not (ROOT/'runtime_profiles/translation-candidate').exists()
    assert not (ROOT/'runtime_profiles/xtts-security-candidate/Lib/site-packages/sentencepiece').exists()
    assert not (ROOT/'temp/ollama-eval-c_lslq8w').exists()
    names=['core/llm_translator.py','core/providers/translation/ollama_m2m100_local.py','core/pipeline.py',
           'dev/test_m2m100_lifecycle.py','dev/prepare_m2m100_runtime_plan.py',
           'dev/audit_m2m100_runtime_plan.py','dev/finalize_m2m100_plan.py']
    result=dict(passed=True,release_ready=False,packages_added=False,runtime_created=False,
                package_archives_downloaded=False,models_downloaded=False,defaults_changed=False,
                protected_state_preserved=True,existing_runtime_identity_preserved=True,
                nllb_runtime_identity_preserved=True,model_hashes=models,
                target_token_validation_fixed=True,translation_stage_release_fixed=True,
                backend_tests=853,focused_tests=17,test_counts_overlap=True,
                proposed_packages=41,proposed_reused_packages=40,proposed_new_package='sentencepiece==0.2.2',
                proposed_new_archive_bytes=plan['new_download_bytes'],advisory_lookup_complete=True,
                advisory_matches=0,security_certification=False,installation_approval_required=True,
                proposal_sha256=sha(plan_path),source_sha256={name:sha(ROOT/name) for name in names})
    (OUT/'2026-10-16-m2m100-plan-and-repairs-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
