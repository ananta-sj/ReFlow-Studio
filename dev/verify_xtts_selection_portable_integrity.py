"""Final evidence, copied recipe and protected original-state verification."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/validation'
TARGET=ROOT/'dist/portable-xtts-trial-2026-10-13'
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def main():
    from core.xtts_runtime import validate
    manifest=json.loads((OUT/'2026-10-13-xtts-portable-trial-manifest.json').read_text())
    live=json.loads((OUT/'2026-10-13-xtts-portable-trial-live.json').read_text())
    backend=(OUT/'2026-10-13-xtts-selection-backend-final-shutdown.log').read_text()
    build=(OUT/'2026-10-13-xtts-selection-frontend-build.log').read_text()
    copy_tests=(OUT/'2026-10-13-xtts-selection-packaging-copy-tests.log').read_text()
    state=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    before=json.loads((OUT/'2026-10-13-xtts-candidate-preservation-before.json').read_text())
    files=['core/settings.py','core/providers/resolve.py','core/pipeline.py','core/cue_review.py',
        'core/engine_readiness.py','bridge/api.py','frontend/src/lib/api.ts','frontend/src/pages/Settings.tsx',
        'core/providers/base.py','core/providers/tts/xtts_local.py','core/feature_session.py',
        'packaging/build_portable.py','core/xtts_runtime.py','core/xtts_worker.py','core/xtts_compat.py',
        'dev/test_xtts_portable_selection.py','dev/test_engine_readiness.py','dev/test_runtime_probe.py',
        'dev/test_feature_session.py','dev/refresh_xtts_portable_trial.py','dev/verify_xtts_portable_trial.py']
    packaged=[name for name in files if name.startswith(('core/','bridge/'))]
    packaged += [p.relative_to(ROOT).as_posix() for p in (ROOT/'frontend/dist').rglob('*') if p.is_file()]
    packaged += ['docs/validation/2026-10-13-xtts-security-cpu-lock-review.json',
        'runtime_profiles/xtts-security-candidate/profile.json','runtime_profiles/xtts-security-candidate/python313._pth']
    hashes={name:sha(ROOT/name) for name in files}
    copy_checks={name:(TARGET/name).is_file() and sha(TARGET/name)==sha(ROOT/name) for name in packaged}
    inventory_paths={item['path'] for item in manifest['files']}
    graph=json.loads((OUT/'2026-10-13-xtts-selection-graph-contracts.json').read_text())
    checks=dict(backend_passed=bool(re.search(r'Ran 790 tests.*?\nOK',backend,re.S)),
        final_copy_tests_passed=bool(re.search(r'Ran 11 tests.*?\nOK',copy_tests,re.S)),
        frontend_build_passed='built in' in build and 'error TS' not in build,
        graph_contracts_passed=graph['passed'],live_portable_passed=live['passed'],
        copied_recipe_current=all(copy_checks.values()),
        trial_identity_relocates=validate()['identity']==validate(TARGET)['identity'],
        no_personal_state_packaged=not set(state).intersection(inventory_paths),
        no_original_models_packaged=not any(p.startswith('models/') for p in inventory_paths),
        original_state_preserved=all(sha(ROOT/name)==row['current'].lower() for name,row in state.items()),
        original_xtts_assets_preserved=all(sha(ROOT/name)==value for name,value in before['assets'].items()),
        ollama_absent=not (ROOT/'temp/ollama-eval-c_lslq8w').exists())
    report=dict(passed=all(checks.values()),checks=checks,release_ready=False,default_switched=False,
        backend_full_run_tests=790,backend_distinct_tests=790,frontend_graph_checks=len(graph['checks']),
        assembly_copy_workers=manifest.get('copy_workers',1),future_copy_default_workers=4,
        bytes_by_component=manifest['bytes_by_component'],portable_total_bytes=sum(manifest['bytes_by_component'].values()),
        inventory_files=len(manifest['files']),source_sha256=hashes,copied_file_checks=copy_checks,
        evidence_scope='Windows portable relocation, saved selection, actual CPU speech and generation cancellation; no native UI or clean-machine acceptance')
    (OUT/'2026-10-13-xtts-selection-portable-integrity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return not report['passed']
if __name__=='__main__':raise SystemExit(main())
