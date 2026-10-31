"""Close out NLLB integration with exact source/state/model evidence."""
import base64
import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/validation'
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    from core.nllb_runtime import validate
    from core.xtts_runtime import validate as package_runtime
    from core.runtime_integrity import sha, safe_path
    route = validate()
    assert package_runtime()['identity'] == '85a69c83e2310e8e53303987947f2313cb4c6aa70627eeccae3b85b564fd8163'
    real = json.loads((OUT/'2026-10-16-nllb-routing-real-corrected.json').read_text())
    native = json.loads((OUT/'2026-10-16-nllb-routing-native.json').read_text())
    assert real['passed'] and real['runtime']['identity'] == route['identity'] and native['passed']
    logs = {'backend': ('2026-10-16-nllb-routing-full-backend.log', 846),
            'desktop_focused': ('2026-10-16-nllb-routing-focused.log', 76)}
    for name, count in logs.values():
        assert re.search(rf'Ran {count} tests.*?\nOK', (OUT/name).read_text(encoding='utf-8'), re.S)
    state = json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assert all(sha(ROOT/name) == row['current'].lower() for name, row in state.items())
    xtts = json.loads((OUT/'2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    assert all(sha(ROOT/name) == value for name, value in xtts.items())
    feasibility = json.loads((OUT/'2026-10-16-nllb-existing-runtime-feasibility.json').read_text())
    assert all(sha(ROOT/'models/translation/nllb_600M'/name) == value for name, value in feasibility['model_sha256'].items())
    recovery = json.loads((ROOT/'core/recovery_sources.json').read_text())['m2m100']
    checked_m2m = []
    for row in recovery['files']:
        if row['sha256']:
            path = ROOT/recovery['folder']/row['name']
            assert sha(path) == row['sha256']
            checked_m2m.append(row['name'])
    site = Path(route['profile'])/'Lib/site-packages'
    distributions = list(site.glob('*.dist-info/RECORD'))
    checked = 0
    for record in distributions:
        for name, checksum, size in csv.reader(record.read_text(encoding='utf-8').splitlines()):
            parts = Path(name).parts
            if not name.endswith('.py') or not checksum or '..' in parts or Path(name).is_absolute():
                continue
            path = safe_path(site/name)
            actual = base64.urlsafe_b64encode(bytes.fromhex(sha(path))).decode().rstrip('=')
            assert checksum == 'sha256='+actual and path.stat().st_size == int(size), name
            checked += 1
    assert len(distributions) == 99 and checked > 1000
    sources = ['core/providers/translation/nllb_local.py', 'core/nllb_runtime.py', 'core/nllb_worker.py',
               'core/nllb_runtime_manifest.json', 'core/providers/resolve.py', 'core/settings.py',
               'core/pipeline.py', 'core/cue_review.py', 'core/runtime_checks.py', 'core/engine_readiness.py',
               'core/runtime_probe_contract.py', 'core/runtime_probe_worker.py', 'bridge/api.py',
               'frontend/src/pages/Settings.tsx', 'frontend/src/lib/api.ts', 'dev/test_nllb_runtime.py',
               'dev/evaluate_nllb_existing_runtime.py', 'dev/evaluate_nllb_routing.py',
               'dev/evaluate_nllb_settings_native.py', 'dev/prepare_nllb_routing_recipe.py',
               'dev/finalize_nllb_routing.py']
    # Existing optional profile already closes over the runtime/lock. No build
    # or binary copy is needed to establish these required files exist.
    required = ['core/nllb_worker.py', 'core/nllb_runtime_manifest.json',
                'runtime_profiles/xtts-security-candidate/python.exe',
                'runtime_profiles/xtts-security-candidate/profile.json',
                'docs/validation/2026-10-13-xtts-security-cpu-lock-review.json']
    assert all((ROOT/name).is_file() for name in required)
    assert not (ROOT/'temp/ollama-eval-c_lslq8w').exists()
    result = dict(passed=True, release_ready=False, defaults_changed=False, packages_added=False,
        models_downloaded=False, runtime_identity=route['identity'], underlying_runtime_identity=package_runtime()['identity'],
        real_checks=len(real['checks']), native_checks=len(native['checks']),
        tests={key: dict(log=name, count=count) for key, (name, count) in logs.items()}, test_counts_overlap=True,
        protected_state_and_xtts_assets_preserved=True, original_nllb_files_preserved=True,
        m2m100_canonical_hashes_verified=checked_m2m, installed_distributions=99,
        installed_python_source_records_verified=checked, native_binaries_reaudited=False,
        semantic_quality_approved=False, nllb_explicit_worker_integrated=True, m2m100_migrated=False,
        portable_required_files_checked=required, portable_copy_created=False,
        source_sha256={name: sha(ROOT/name) for name in sources},
        frontend_dist_sha256={str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT/'frontend/dist').rglob('*')) if path.is_file()},
        remaining=['M2M100 SentencePiece-compatible separate runtime proposal and approval',
                   'Long/multilingual semantic quality', 'Other engine migrations and full release gates'])
    (OUT/'2026-10-16-nllb-routing-acceptance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
