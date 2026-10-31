"""Verify helper/lock acceptance, bind evidence and preserve original state."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    from core.xtts_runtime import validate
    helper_dir = OUT / '2026-10-13-proxy-tools-helper'
    helper = json.loads((helper_dir / 'receipt.json').read_text())
    lock_path = OUT / '2026-10-13-desktop-candidate-lock-review.json'
    lock = json.loads(lock_path.read_text())
    scan = json.loads((OUT / '2026-10-13-desktop-resolved-lock-advisories.json').read_text())
    baseline = json.loads((OUT / '2026-10-13-desktop-runtime-boundary-integrity.json').read_text())
    states = json.loads((OUT / '2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assets = json.loads((OUT / '2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    bootstrap = json.loads((OUT / '2026-10-13-desktop-runtime-plan-integrity.json').read_text())['bootstrap']
    wheel = helper_dir / helper['wheel']
    with zipfile.ZipFile(wheel) as package:
        notices = [name for name in package.namelist() if name.endswith('/LICENSE.upstream.txt')]
        notice_matches = len(notices) == 1 and hashlib.sha256(package.read(notices[0])).hexdigest() == helper['upstream_notice_sha256']
    checks = dict(helper_build_and_python313_smoke_passed=helper['build_passed'] and helper['python313_smoke_passed'],
                  helper_and_lock_hashes_agree=sha(wheel) == helper['wheel_sha256'] == lock['approved_helper_sha256'],
                  upstream_notice_retained=notice_matches,
                  build_workspace_removed=helper['temporary_workspace_removed'] and not any((ROOT / 'temp').glob('proxy-approved-*')),
                  target_closure_valid=lock['metadata_closure_valid'] and not lock['issues'] and all(edge['satisfied'] for edge in lock['edges']),
                  final_advisory_query_no_current_matches=scan['complete'] and scan['match_count'] == 0 and scan['packages'] == len(lock['packages']),
                  original_sources_preserved=all(sha(ROOT / name) == value for name, value in baseline['source_sha256'].items()),
                  original_state_preserved=all(sha(ROOT / name) == row['current'].lower() for name, row in states.items()),
                  original_xtts_assets_preserved=all(sha(ROOT / name) == value for name, value in assets.items()),
                  original_bootstrap_preserved=all(sha(ROOT / 'runtime_profiles/xtts-security-candidate' / name) == row['sha256'] for name, row in bootstrap.items()),
                  original_isolated_runtime_identity_preserved=validate()['identity'] == baseline['xtts_runtime_identity'],
                  ollama_trial_absent=not (ROOT / 'temp/ollama-eval-c_lslq8w').exists())
    files = ['dev/build_approved_proxy_helper.py', 'dev/prepare_desktop_runtime_lock.py',
             'dev/check_desktop_candidate_lock.py', 'dev/audit_desktop_dependency_projection.py',
             'dev/verify_desktop_helper_lock_completion.py']
    result = dict(passed=all(checks.values()), checks=checks, package_count=len(lock['packages']),
                  active_dependency_links=len(lock['edges']), artifact_bytes=lock['artifact_download_bytes'],
                  helper_bytes=helper['wheel_bytes'], helper_sha256=helper['wheel_sha256'],
                  lock_sha256=sha(lock_path), source_sha256={name: sha(ROOT / name) for name in files},
                  runtime_installed=False, install_authorized=False, release_ready=False,
                  helper_distribution_notice_review_complete=False)
    (OUT / '2026-10-13-desktop-helper-lock-integrity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
