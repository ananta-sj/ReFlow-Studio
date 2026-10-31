"""Finalize bounded desktop acceptance without asserting full-app release."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PROFILE = ROOT / 'runtime_profiles/desktop-candidate'


def main():
    receipts = {phase: json.loads((OUT / f'2026-10-14-desktop-candidate-{phase}.json').read_text())
                for phase in ['backend', 'native', 'native-controls-ready', 'speech']}
    files = json.loads((OUT / '2026-10-14-desktop-candidate-file-integrity-final.json').read_text())
    cleanup = json.loads((OUT / '2026-10-14-desktop-candidate-staging-cleanup.json').read_text())
    suite = (OUT / '2026-10-14-desktop-candidate-desktop-suite.log').read_text(encoding='utf-8')
    broad = (OUT / '2026-10-14-desktop-candidate-full-backend.log').read_text(encoding='utf-8')
    checks = {phase + '_acceptance': receipt['passed'] for phase, receipt in receipts.items()}
    checks.update(installed_payload_and_preservation=files['passed'],
                  scoped_desktop_suite=bool(re.search(r'Ran 438 tests.*?\nOK', suite, re.S)),
                  installer_staging_removed=cleanup['removed'] and not Path(cleanup['path']).exists(),
                  broad_failures_retained='FAILED (failures=1, errors=12)' in broad)
    lock = OUT / '2026-10-13-desktop-candidate-lock-review.json'
    profile = dict(profile='desktop-candidate', status='desktop-candidate-validated' if all(checks.values()) else 'candidate-failed-acceptance',
                   python='3.13.16', production_default=False, release_eligible=False,
                   dependency_lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),
                   desktop_backend_verified=receipts['backend']['passed'],
                   native_webview2_verified=receipts['native-controls-ready']['passed'],
                   isolated_xtts_parent_verified=receipts['speech']['passed'],
                   full_app_runtime_migrated=False, clean_machine_verified=False,
                   validation_receipt='../../docs/validation/2026-10-14-desktop-candidate-acceptance.json')
    (PROFILE / 'profile.json').write_text(json.dumps(profile, indent=2))
    result = dict(passed=all(checks.values()), checks=checks,
                  approval_scope='Separate Windows desktop candidate with bounded deep acceptance; current defaults preserved',
                  scoped_desktop_suite_tests=438, broad_suite_tests_reported=518,
                  broad_suite_failures=1, broad_suite_errors=12, broad_suite_passed=False,
                  phase_check_counts={phase: len(receipt['checks']) for phase, receipt in receipts.items()},
                  installed_payload_files_verified=files['payload_files_checked'], packages=31,
                  notices_collected_for_packages=files['notice_packages_with_files'],
                  candidate_bytes=sum(path.stat().st_size for path in PROFILE.rglob('*') if path.is_file()),
                  removed_staging_bytes=cleanup['bytes'], release_ready=False, default_switched=False,
                  acceptance_scope='Native hidden-window DOM/bridge and selected CPU speech tests on this existing Windows machine; no full-video or clean-machine release acceptance')
    (OUT / '2026-10-14-desktop-candidate-acceptance.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
