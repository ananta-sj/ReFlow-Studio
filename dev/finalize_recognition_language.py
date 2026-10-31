"""Bind hint acceptance to current sources without rewriting old evidence."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/validation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    integrity = json.loads((OUT/'2026-10-15-recognition-candidate-file-integrity-after-language-hints.json').read_text())
    baseline = json.loads((OUT/'2026-10-13-desktop-runtime-boundary-integrity.json').read_text())
    changed = {name: dict(before=value, current=sha(ROOT/name))
               for name, value in baseline['source_sha256'].items() if sha(ROOT/name) != value}
    # The fixed pipeline is deliberately different. Every other source tracked
    # by this historical baseline must still match; retain the failed raw receipt.
    assert set(changed) == {'core/pipeline.py'}, changed
    assert all(value for key, value in integrity['checks'].items() if key != 'original_sources_preserved')
    receipts = {route: json.loads((OUT/f'2026-10-15-recognition-language-{route}.json').read_text())
                for route in ['cpu', 'gpu']}
    assert all(receipt['passed'] for receipt in receipts.values())
    logs = {'full_backend': ('2026-10-15-recognition-language-full-backend.log', 815),
            'desktop_scoped': ('2026-10-15-recognition-language-desktop-scoped.log', 79)}
    for filename, count in logs.values():
        assert re.search(rf'Ran {count} tests.*?\nOK', (OUT/filename).read_text(encoding='utf-8'), re.S)
    names = ['core/recognition_language.py', 'core/transcription.py', 'core/providers/base.py',
             'core/pipeline.py', 'core/stage_checkpoints.py', 'core/providers/stt/cloud_rest.py',
             'core/providers/stt/whisper_local.py', 'core/providers/stt/whisper_turbo_local.py',
             'core/stt/stt_handler.py', 'core/run_stt.py', 'core/whisper_turbo_worker.py',
             'dev/test_recognition_language.py', 'dev/test_engine_import_boundaries.py',
             'dev/test_stage_checkpoints.py', 'dev/test_whisper_turbo_integration.py',
             'dev/evaluate_recognition_language.py', 'dev/finalize_recognition_language.py']
    sources = {name: sha(ROOT/name) for name in names}
    # Verify both original and converted weights, not just file sizes.
    import sys
    sys.path[:0] = [str(ROOT), str(ROOT/'core')]
    from core.whisper_turbo_assets import validate_assets
    original = validate_assets(ROOT/'models/f5/reference-asr', verify_weights=True)
    conversion = json.loads((OUT/'2026-10-15-recognition-model-conversion-compat.json').read_text())
    assert original == conversion['source']
    for name, row in conversion['files'].items():
        path = (ROOT/'models/whisper/ct2-turbo-candidate-compat'/name).resolve()
        assert path.is_relative_to((ROOT/'models/whisper/ct2-turbo-candidate-compat').resolve())
        assert sha(path) == row['sha256']
    result = dict(passed=True, release_ready=False, defaults_changed=False, models_downloaded=False,
                  packages_added=False, source_sha256=sources, deliberate_historical_source_changes=changed,
                  remaining_baseline_sources_preserved=True,
                  package_payloads_verified=integrity['payload_files_checked'],
                  original_state_and_models_preserved=True, original_and_converted_whisper_hashes_verified=True,
                  original_xtts_identity_preserved=True, automatic_hindi_detection_fixed=False,
                  cpu_hindi_hint_passed=True, gpu_hindi_hint_passed=True,
                  tests={key: dict(log=filename, count=count) for key, (filename, count) in logs.items()},
                  test_counts_overlap=True, per_feature_runtime_routing_integrated=False,
                  notice_packages_without_files=integrity['notice_packages_without_files'])
    receipt = OUT/'2026-10-15-recognition-language-acceptance.json'
    receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
    profile_path = ROOT/'runtime_profiles/recognition-candidate/profile.json'
    profile = json.loads(profile_path.read_text())
    profile.update(handler_sha256=sources['core/stt/stt_handler.py'], worker_sha256=sources['core/run_stt.py'],
                   hint_repair_acceptance='../../docs/validation/'+receipt.name,
                   hint_repair_acceptance_sha256=sha(receipt),
                   hint_repair_source_sha256={name: sources[name] for name in
                       ['core/recognition_language.py', 'core/transcription.py', 'core/providers/stt/whisper_local.py']})
    assert not profile['release_eligible'] and not profile['production_default']
    assert not profile['hindi_auto_detection_verified']
    profile_path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
