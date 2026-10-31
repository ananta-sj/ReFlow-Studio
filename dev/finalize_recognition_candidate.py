"""Bind real recognition acceptance, conversion, source and cleanup evidence."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PROFILE = ROOT / 'runtime_profiles/recognition-candidate'
MODEL = ROOT / 'models/whisper/ct2-turbo-candidate-compat'
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    from core.whisper_turbo_assets import validate_assets
    original = validate_assets(ROOT / 'models/f5/reference-asr', verify_weights=True)
    conversion = json.loads((OUT / '2026-10-15-recognition-model-conversion-compat.json').read_text())
    assert conversion['completed'] and conversion['original_preserved']
    for name, row in conversion['files'].items():
        path = MODEL / name
        assert path.resolve().is_relative_to(MODEL.resolve()) and sha(path) == row['sha256']
    receipts = {phase: json.loads((OUT / f'2026-10-15-recognition-candidate-{phase}.json').read_text())
                for phase in ['native-media', 'native-hindi-hinted', 'provider']}
    auto_hindi = json.loads((OUT / '2026-10-15-recognition-candidate-native-hindi.json').read_text())
    baseline = json.loads((OUT / '2026-10-15-recognition-existing-gpu-baseline.json').read_text())
    files = json.loads((OUT / '2026-10-15-recognition-candidate-file-integrity-after-baseline.json').read_text())
    cleanup = json.loads((OUT / '2026-10-15-recognition-candidate-staging-cleanup.json').read_text())
    backend = (OUT / '2026-10-15-recognition-compat-full-backend.log').read_text(encoding='utf-8')
    checks = {phase: receipt['passed'] for phase, receipt in receipts.items()}
    checks.update(original_whisper_hashes_preserved=original == conversion['source'],
                  converted_model_hashes_verified=True, package_payload_and_state_preserved=files['passed'],
                  backend_regressions_passed=bool(re.search(r'Ran 807 tests.*?\nOK', backend, re.S)),
                  owned_staging_removed=cleanup['removed'] and not Path(cleanup['path']).exists())
    checks['existing_gpu_baseline_compared'] = baseline['completed'] and baseline['worker_released'] and baseline['workspace_removed']
    # The first failed conversion owns only its marker; retain its failure
    # receipt/log, remove that empty failed output container after checking it.
    failed = ROOT / 'models/whisper/ct2-turbo-candidate'
    if failed.exists():
        assert failed.resolve().is_relative_to((ROOT / 'models/whisper').resolve())
        assert (failed / '.owner').read_text() == 'reflow.recognition.conversion.2026-10-15'
        assert sorted(path.name for path in failed.iterdir()) == ['.owner']
        shutil.rmtree(failed)
    source_names = ['core/stt/stt_handler.py', 'core/recognition_compat.py', 'core/run_stt.py',
                    'core/providers/stt/whisper_local.py', 'dev/convert_existing_whisper_candidate.py',
                    'dev/evaluate_recognition_candidate.py', 'dev/test_recognition_compat.py',
                    'dev/build_desktop_candidate.py', 'dev/verify_desktop_candidate_files.py',
                    'dev/clean_recognition_candidate_artifacts.py', 'dev/finalize_recognition_candidate.py',
                    'dev/compare_recognition_existing_baseline.py']
    sources = {name: sha(ROOT / name) for name in source_names}
    lock = OUT / '2026-10-15-recognition-candidate-lock-review.json'
    profile = dict(profile='recognition-candidate', status='candidate-partial-acceptance-hindi-auto-failed', python='3.13.16',
                   device='cpu', production_default=False, release_eligible=False,
                   dependency_lock_sha256=sha(lock), compatibility_adapter_sha256=sources['core/recognition_compat.py'],
                   handler_sha256=sources['core/stt/stt_handler.py'], worker_sha256=sources['core/run_stt.py'],
                   converted_model_manifest='../../docs/validation/2026-10-15-recognition-model-conversion-compat.json',
                   converted_model_manifest_sha256=sha(OUT / '2026-10-15-recognition-model-conversion-compat.json'),
                   real_cpu_inference_verified=all(receipt['passed'] for receipt in receipts.values()),
                   hindi_auto_detection_verified=auto_hindi['passed'],
                   hindi_explicit_hint_verified=receipts['native-hindi-hinted']['passed'],
                   per_feature_production_routing_integrated=False)
    assert all(checks.values()), checks
    (PROFILE / 'profile.json').write_text(json.dumps(profile, indent=2))
    result = dict(passed=auto_hindi['passed'], technical_checks_passed=all(checks.values()), checks=checks,
                  hindi_auto_detection_passed=auto_hindi['passed'], packages=24, payload_files_verified=files['payload_files_checked'],
                  backend_tests=807, phase_checks={phase: len(receipt['checks']) for phase, receipt in receipts.items()},
                  runtime_bytes=sum(path.stat().st_size for path in PROFILE.rglob('*') if path.is_file()),
                  converted_model_bytes=conversion['converted_bytes'], staging_bytes_removed=cleanup['bytes'],
                  source_sha256=sources, converted_model_files=conversion['files'],
                  hindi_hinted_word_error_rate=receipts['native-hindi-hinted']['hindi_word_error_rate'],
                  existing_gpu_baseline_language=baseline['transcription']['language'],
                  existing_gpu_baseline_language_probability=baseline['transcription']['language_probability'],
                  notice_packages_without_files=files['notice_packages_without_files'],
                  worker_selection_test_scope='Process-local existing REFLOW_WORKER_PYTHON override; no production per-feature selection/default change',
                  release_ready=False, default_switched=False, model_downloaded=False)
    (OUT / '2026-10-15-recognition-candidate-acceptance.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
