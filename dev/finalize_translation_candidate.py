"""Final current-source acceptance and original-state/model preservation."""
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]


def main():
    from core.runtime_integrity import sha
    from core.m2m100_runtime import validate,model_contract
    from core.xtts_runtime import validate as original_runtime
    from core.nllb_runtime import validate as original_nllb
    from core.recognition_runtime import validate as original_recognition
    route=validate();model_contract(verify_weights=True)
    assert original_runtime()['identity']=='85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163'
    assert original_nllb()['identity']=='1df86b1800ee5f17229b3be3972f2bfb83e28a2303d9b48d7caf2e2f947870bd'
    assert original_recognition()['identity']=='f065c87ef27f370e060a5bdc4e2ba0e9f5056d8d7e8e8abe16ba1715dc696162'
    build=json.loads((OUT/'2026-10-16-translation-candidate-build.json').read_text())
    native=json.loads((OUT/'2026-10-16-translation-candidate-native.json').read_text())
    live=json.loads((OUT/'2026-10-16-m2m100-routing-real-corrected.json').read_text())
    ui=json.loads((OUT/'2026-10-16-m2m100-routing-native.json').read_text())
    cleanup=json.loads((OUT/'2026-10-16-translation-candidate-closeout.json').read_text())
    upstream=json.loads((OUT/'2026-10-16-translation-candidate-upstream-notices.json').read_text())
    assert upstream['collected'] and not upstream['packages_modified']
    assert {row['package'] for row in upstream['sources']}==set(cleanup['notice_packages_without_files'])
    for row in upstream['sources']:
        assert sha(ROOT/row['file'])==row['sha256']
        assert (ROOT/row['file']).stat().st_size==row['bytes']
    assert all(item.get('passed') for item in [native,live,ui,cleanup]) and build['completed']
    assert live['runtime']['identity']==route['identity']
    tests={'backend':('2026-10-16-m2m100-routing-full-backend.log',867),
           'desktop_focused':('2026-10-16-m2m100-routing-focused.log',73)}
    for name,count in tests.values():
        assert re.search(rf'Ran {count} tests.*?\nOK',(OUT/name).read_text(encoding='utf-8'),re.S),name
    states=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name)==row['current'].lower() for name,row in states.items())
    original_assets=json.loads((OUT/'2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    assert all(sha(ROOT/name)==value for name,value in original_assets.items())
    prior_nllb=json.loads((OUT/'2026-10-16-nllb-existing-runtime-feasibility.json').read_text())['model_sha256']
    assert all(sha(ROOT/'models/translation/nllb_600M'/name)==value for name,value in prior_nllb.items())
    assert not (ROOT/'temp/translation-candidate-2026-10-16-staging').exists()
    assert not (ROOT/'temp/ollama-eval-c_lslq8w').exists()
    profile_path=Path(route['profile'])/'profile.json'
    profile=json.loads(profile_path.read_text())
    profile.update(status='candidate-offline-validated',runtime_verified=True,
                   real_model_inference_verified=True,persistent_session_verified=True,
                   per_feature_routing_integrated=True,semantic_quality_accepted=False,
                   acceptance='../../docs/validation/2026-10-16-translation-candidate-acceptance.json',
                   runtime_identity=route['identity'])
    assert not profile['production_default'] and not profile['release_eligible']
    profile_path.write_text(json.dumps(profile,indent=2),encoding='utf-8')
    # scandir reuses directory-entry metadata; avoid a separate ancestor walk
    # for every file when measuring the already-owned candidate tree.
    total=0;file_count=0;cache_dirs=[]
    for directory,dirs,files in os.walk(route['profile']):
        cache_dirs.extend(str(Path(directory)/name) for name in dirs if name=='__pycache__')
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):total+=entry.stat(follow_symlinks=False).st_size;file_count+=1
    names=['core/m2m100_runtime.py','core/m2m100_worker.py','core/llm_translator.py',
           'core/providers/translation/m2m100_isolated.py','core/providers/translation/ollama_m2m100_local.py',
           'core/providers/resolve.py','core/pipeline.py','core/settings.py','core/cue_review.py',
           'core/runtime_checks.py','core/engine_readiness.py','core/runtime_probe_contract.py',
           'core/runtime_probe_worker.py','bridge/api.py','frontend/src/pages/Settings.tsx',
           'frontend/src/lib/api.ts','packaging/build_portable.py','dev/test_m2m100_runtime.py',
           'dev/build_translation_candidate.py','dev/evaluate_translation_candidate.py',
           'dev/evaluate_m2m100_routing.py','dev/evaluate_m2m100_settings_native.py',
           'dev/prepare_m2m100_routing_recipe.py','dev/close_translation_candidate.py',
           'dev/finalize_translation_candidate.py','dev/collect_translation_upstream_notices.py']
    result=dict(passed=True,release_ready=False,defaults_changed=False,models_downloaded=False,
        approved_packages=41,reused_packages=40,new_package='sentencepiece==0.2.2',
        archive_bytes_downloaded=build['new_archive_bytes'],copied_payload_files_verified=build['copied_payload_files'],
        sentencepiece_payload_files_verified=cleanup['sentencepiece_payload_files_verified'],
        native_checks=len(native['checks']),real_checks=len(live['checks']),native_ui_checks=len(ui['checks']),
        tests={key:dict(log=name,count=count) for key,(name,count) in tests.items()},test_counts_overlap=True,
        runtime_identity=route['identity'],candidate_bytes=total,candidate_files=file_count,cache_directories=cache_dirs,
        owned_staging_removed=True,staging_bytes_removed=cleanup['staging_bytes_removed'],
        original_state_runtime_and_model_hashes_preserved=True,ollama_absent=True,
        notice_packages_without_files=cleanup['notice_packages_without_files'],
        installed_package_notice_count=cleanup['notice_packages_with_files'],
        upstream_notice_supplements=upstream['sources'],distribution_rights_cleared=False,
        semantic_quality_approved=False,complete_subtitle_pipeline_validated=True,complete_video_workflow_validated=False,
        service_discovery_mocked=True,live_api_calls=False,portable_copy_created=False,
        source_sha256={name:sha(ROOT/name) for name in names},
        runtime_profile_sha256=sha(profile_path),
        frontend_dist_sha256={str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'frontend/dist').rglob('*')) if path.is_file()})
    (OUT/'2026-10-16-translation-candidate-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
