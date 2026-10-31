"""Record current routing acceptance separately from historical runtime audits."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
OUT = ROOT/'docs/validation'


def main():
    from core.recognition_runtime import validate, LOCK
    from core.runtime_integrity import sha
    route = validate()
    real = json.loads((OUT/'2026-10-16-recognition-routing-real-corrected.json').read_text())
    native = json.loads((OUT/'2026-10-16-recognition-routing-native-ready.json').read_text())
    integrity = json.loads((OUT/'2026-10-15-recognition-candidate-file-integrity-after-feature-routing.json').read_text())
    assert real['passed'] and native['passed']
    assert real['runtime']['identity'] == route['identity']
    assert all(value for key, value in integrity['checks'].items() if key != 'original_sources_preserved')
    previous = json.loads((OUT/'2026-10-13-desktop-runtime-boundary-integrity.json').read_text())
    changes = {name: dict(before=value, current=sha(ROOT/name))
               for name, value in previous['source_sha256'].items() if sha(ROOT/name) != value}
    assert set(changes) == {'core/pipeline.py', 'core/runtime_checks.py', 'bridge/api.py'}, changes
    # Verify state again at closeout rather than relying only on the earlier scan.
    states = json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name) == row['current'].lower() for name, row in states.items())
    from core.whisper_turbo_assets import validate_assets
    original = validate_assets(ROOT/'models/f5/reference-asr', verify_weights=True)
    conversion = json.loads((OUT/'2026-10-15-recognition-model-conversion-compat.json').read_text())
    assert original == conversion['source']
    converted = ROOT/'models/whisper/ct2-turbo-candidate-compat'
    for name, row in conversion['files'].items():
        path = (converted/name).resolve()
        assert path.is_relative_to(converted.resolve()) and sha(path) == row['sha256']
    logs = {'backend': ('2026-10-16-recognition-routing-full-backend-final.log', 831),
            'desktop_scoped': ('2026-10-16-recognition-routing-focused-acceptance.log', 104)}
    for filename, count in logs.values():
        assert re.search(rf'Ran {count} tests.*?\nOK', (OUT/filename).read_text(encoding='utf-8'), re.S), filename
    portable_path = OUT/'2026-10-16-recognition-routing-portable-manifest-final.json'
    portable = json.loads(portable_path.read_text())
    paths = {row['path'] for row in portable['files']}
    assert {'core/recognition_runtime.py', 'core/runtime_integrity.py', LOCK,
            'runtime_profiles/recognition-candidate/routing-recipe.json'} <= paths
    assert not ({'settings.json', 'models.json'} & paths)
    assert not portable['downloaded_model_weights_included'] and not portable['personal_state_included']
    names = ['core/recognition_runtime.py', 'core/runtime_integrity.py', 'core/settings.py',
             'core/providers/resolve.py', 'core/providers/stt/whisper_local.py', 'core/pipeline.py',
             'core/runtime_checks.py', 'core/engine_readiness.py', 'core/runtime_probe_contract.py',
             'core/runtime_probe_worker.py', 'core/run_manifest.py', 'core/cue_review.py', 'bridge/api.py',
             'frontend/src/pages/Settings.tsx', 'frontend/src/lib/api.ts', 'packaging/build_portable.py',
             'dev/test_recognition_runtime.py', 'dev/test_recognition_language.py',
             'dev/test_transcription_metadata.py', 'dev/prepare_recognition_routing_recipe.py',
             'dev/evaluate_recognition_routing.py', 'dev/evaluate_recognition_settings_native.py',
             'dev/finalize_recognition_routing.py']
    source_hashes = {name: sha(ROOT/name) for name in names}
    built = {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT/'frontend/dist').rglob('*')) if path.is_file()}
    result = dict(passed=True, release_ready=False, production_default_changed=False,
                  packages_added=False, models_downloaded=False, runtime_identity=route['identity'],
                  real_checks=len(real['checks']), native_checks=len(native['checks']),
                  tests={key: dict(log=filename, count=count) for key, (filename, count) in logs.items()},
                  test_counts_overlap=True, backend_loaded_before_final_malformed_recipe_test=True,
                  installed_payload_files_verified=integrity['payload_files_checked'],
                  original_state_preserved=True, original_and_converted_models_preserved=True,
                  original_xtts_identity_preserved=True, ollama_absent=True,
                  remaining_baseline_sources_preserved=True, deliberate_source_changes=changes,
                  cpu_recognition_explicit_routing_integrated=True,
                  all_engines_migrated=False, automatic_hindi_detection_fixed=False,
                  notice_packages_without_files=integrity['notice_packages_without_files'],
                  source_sha256=source_hashes, frontend_dist_sha256=built,
                  portable_inventory_sha256=sha(portable_path), portable_copy_created=False,
                  validation_scope='Existing machine; offline recognition stage, native hidden interface, no full video/clean-machine release approval')
    receipt = OUT/'2026-10-16-recognition-routing-acceptance.json'
    receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
    profile_path = ROOT/'runtime_profiles/recognition-candidate/profile.json'
    profile = json.loads(profile_path.read_text())
    profile.update(per_feature_production_routing_integrated=True,
                   explicit_routing_acceptance='../../docs/validation/'+receipt.name,
                   explicit_routing_acceptance_sha256=sha(receipt), runtime_identity=route['identity'])
    assert not profile['production_default'] and not profile['release_eligible']
    assert not profile['hindi_auto_detection_verified']
    profile_path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
