"""Bind this iteration's test evidence to source and protected user state."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    from core.xtts_runtime import validate
    log = (OUT / '2026-10-13-desktop-runtime-boundary-backend.log').read_text(encoding='utf-8')
    test_run = re.search(r'Ran (\d+) tests.*?\nOK', log, re.S)
    receipts = [json.loads(line.split('=', 1)[1]) for line in log.splitlines()
                if line.startswith('BOUNDARY_RECEIPT=')]
    states = json.loads((OUT / '2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assets = json.loads((OUT / '2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    previous = json.loads((OUT / '2026-10-13-xtts-selection-portable-integrity.json').read_text())
    state_checks = {name: sha(ROOT / name) == data['current'].lower() for name, data in states.items()}
    asset_checks = {name: sha(ROOT / name) == expected for name, expected in assets.items()}
    identity = validate()['identity']
    names = ['config.py', 'core/hardware_monitor.py', 'core/pipeline.py', 'core/runtime_checks.py',
             'core/integrity.py', 'bridge/api.py', 'dev/test_desktop_runtime_boundary.py',
             'dev/verify_desktop_runtime_boundary.py']
    checks = dict(backend_passed=bool(test_run),
                  missing_and_broken_import_probes_passed={r['mode'] for r in receipts} == {'missing', 'broken'},
                  original_state_preserved=all(state_checks.values()),
                  original_xtts_assets_preserved=all(asset_checks.values()),
                  xtts_runtime_identity_preserved=identity == '85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163',
                  ollama_trial_absent=not (ROOT / 'temp/ollama-eval-c_lslq8w').exists())
    # The previous portable is intentionally retained as its own tested snapshot.
    stale = [name for name, value in previous['source_sha256'].items() if sha(ROOT / name) != value]
    report = dict(passed=all(checks.values()), checks=checks,
                  backend_tests=int(test_run.group(1)) if test_run else None,
                  probes=receipts, protected_state=state_checks, protected_xtts_assets=asset_checks,
                  source_sha256={name: sha(ROOT / name) for name in names},
                  xtts_runtime_identity=identity, previous_portable_source_differences=stale,
                  packages_installed=False, native_window_tested=False, release_ready=False,
                  scope='Existing Windows interpreter with unavailable AI imports; not a clean desktop runtime installation')
    (OUT / '2026-10-13-desktop-runtime-boundary-integrity.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
