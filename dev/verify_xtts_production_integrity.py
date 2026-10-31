"""Consolidate raw failures, exact reruns, final sources and protected state."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/validation'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def main():
    backend=json.loads((OUT/'2026-10-13-xtts-production-backend.json').read_text())
    provider=json.loads((OUT/'2026-10-13-xtts-production-provider.json').read_text())
    http=(OUT/'2026-10-13-xtts-production-http-permitted.log').read_text()
    focused=(OUT/'2026-10-13-xtts-production-final-focused.log').read_text()
    rerun=(OUT/'2026-10-13-xtts-production-environment-rerun.log').read_text()
    failures=[r['module'] for r in backend['modules'] if r['exit_code'] or not r['tests']]
    state=json.loads((OUT/'2026-10-10-control-paths-state-integrity.json').read_text())['state']
    before=json.loads((OUT/'2026-10-13-xtts-candidate-preservation-before.json').read_text())
    files=['core/xtts_compat.py','core/xtts_worker.py','core/xtts_runtime.py','core/providers/tts/xtts_local.py',
        'core/run_manifest.py','core/engine_readiness.py','dev/test_engine_readiness.py','dev/test_xtts_runtime_selection.py']
    checks=dict(real_provider=provider['passed'],
        raw_failures_accounted_for=set(failures)=={'dev.test_cue_review','dev.test_dialogue_connections','dev.test_engine_readiness','dev.test_http_media','dev.test_model_download','dev.test_pipeline_dryrun','dev.test_suite'},
        identical_http_rerun_passed=bool(re.search(r'Ran 9 tests.*?\nOK',http,re.S)),
        environment_rerun_passed=bool(re.search(r'Ran (\d+) tests.*?\nOK',rerun,re.S)),
        final_focused_passed=bool(re.search(r'Ran 47 tests.*?\nOK',focused,re.S)),
        state_preserved=all(sha(ROOT/name)==row['current'].lower() for name,row in state.items()),
        model_preserved=all(sha(ROOT/name)==value for name,value in before['assets'].items()),
        ollama_absent=not (ROOT/'temp/ollama-eval-c_lslq8w').exists())
    previous=json.loads((OUT/'2026-10-12-windows-release-backend-complete.json').read_text())['source_sha256']
    changes=[name for name,value in previous.items() if sha(ROOT/name)!=value.lower()]
    checks['baseline_source_changes_declared']=all(name in files for name in changes)
    checks['backend_source_snapshot_current']=all(sha(ROOT/name)==value for name,value in backend['source_sha256'].items())
    report=dict(passed=all(checks.values()),checks=checks,release_ready=False,default_switched=False,
        backend_raw_passed=backend['passed'],backend_raw_tests=backend['tests_run'],
        backend_raw_failed_modules=failures,accepted_distinct_backend_tests=backend['tests_run']+3,
        focused_tests=47,focus_overlap_not_added_to_total=True,
        prior_baseline_changed_sources=changes,source_sha256={name:sha(ROOT/name) for name in files},
        provider_recipe_sha256={name:sha(ROOT/name) for name in ['core/xtts_compat.py','core/xtts_worker.py']},
        excluded_non_test_scripts=['dev.test_model_download','dev.test_pipeline_dryrun'],
        limitations=['Permitted reruns replace blocked local-socket, credential and offline-environment results; the raw report remains failed.',
            'Two standalone scripts expose zero unittest cases and are excluded from acceptance; no download or state-mutating script was executed.',
            'Three readiness tests were added after the full run; the final focused rerun covers them.',
            'Provider live trial preceded deterministic model-stat ordering and readiness exception cleanup; final focused tests cover those final source versions.',
            'No native UI or complete video acceptance for this opt-in route.'])
    (OUT/'2026-10-13-xtts-production-integrity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return not report['passed']
if __name__=='__main__':raise SystemExit(main())
