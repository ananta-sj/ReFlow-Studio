"""Bind this release pass to source, protected state and retained audit evidence."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    backend = read('2026-10-12-windows-release-backend-complete.json')
    baseline = read('2026-10-10-control-paths-state-integrity.json')
    state = {name: sha(ROOT/name)==item['current'].lower() for name,item in baseline['state'].items()}
    code = {name: sha(ROOT/name)==value for name,value in backend['source_sha256'].items()}
    old = read('2026-10-12-frontend-lock-before-security-update.json')['packages']
    new = json.loads((ROOT/'frontend/package-lock.json').read_text(encoding='utf-8'))['packages']
    changes = {name:dict(before=old.get(name,{}).get('version'),after=new.get(name,{}).get('version'))
               for name in old.keys()|new.keys() if old.get(name,{}).get('version')!=new.get(name,{}).get('version')}
    checks = dict(backend_suite_passed=backend['passed'] and backend['tests_run']==766,
        tested_production_sources_unchanged=all(code.values()),protected_app_state_unchanged=all(state.values()),
        temporary_ollama_cleanup_passed=read('2026-10-12-ollama-eval-c_lslq8w-cleanup.json')['passed'],
        relocated_candidate_core_passed=read('2026-10-12-windows-portable-candidate-audit.json')['passed'],
        full_npm_audit_clean=read('2026-10-12-frontend-full-audit-after-update.json')['metadata']['vulnerabilities']['total']==0,
        only_two_expected_frontend_versions_changed=set(changes)=={'node_modules/nanoid','node_modules/source-map-js'},
        root_frontend_package_unchanged=(ROOT/'frontend/package.json').read_bytes()==(OUT/'2026-10-12-frontend-package-before-security-update.json').read_bytes(),
        f5_runtime_recheck_passed=read('2026-10-12-f5-runtime-probe-after-copy.json')['status']=='passed',
        actual_xtts_cancellation_passed=read('2026-10-12-xtts-live-cancellation.json')['acceptance'])
    frontend = {}
    for name in ('resource','preference','graph','recovery','dashboard'):
        data = read('2026-10-12-release-'+name+'-contracts-after-update.log')
        frontend[name]=dict(checks=len(data['checks']),passed=all(item['passed'] for item in data['checks']))
    checks['all_47_frontend_contracts_passed']=sum(item['checks'] for item in frontend.values())==47 and all(item['passed'] for item in frontend.values())
    candidate=ROOT/'dist/windows-release-candidate-2026-10-12'
    assets={path.relative_to(ROOT/'frontend/dist').as_posix():sha(path) for path in (ROOT/'frontend/dist').rglob('*') if path.is_file()}
    checks['current_built_frontend_in_candidate']=all((candidate/'frontend/dist'/name).is_file() and sha(candidate/'frontend/dist'/name)==digest for name,digest in assets.items())
    review=read('2026-10-12-live-workflow-human-review.json')
    checks['accepted_short_video_unchanged']=sha(Path(review['output']))==review['output_sha256']
    original=OUT/'2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4'
    checks['previous_accepted_video_unchanged']=sha(original)=='0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2'
    helpers=('dev/verify_windows_portable_candidate.py','dev/audit_release_dependencies.py',
             'dev/test_application_lock.py','dev/cleanup_temporary_ollama.py','dev/verify_windows_release_evidence.py')
    for name in helpers:
        ast.parse((ROOT/name).read_text(encoding='utf-8-sig'),filename=name)
    checks['new_verification_helpers_parse']=True
    result=dict(passed=all(checks.values()),release_ready=False,checks=checks,
        state=state,tested_sources=code,frontend=frontend,dependency_changes=changes,
        helper_sha256={name:sha(ROOT/name) for name in helpers},
        open_release_gates=['Core dependency consistency and fresh runtime repair approval',
            'Turnkey Hindi runtime/model/reference setup','Representative full workflow and native model-running crash recovery',
            'Model/download/resource/optional-route acceptance per release matrix',
            'Clean-machine Windows validation','Owner licensing decision and exact third-party distribution preparation'])
    destination=OUT/'2026-10-12-windows-release-integrity.json'
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],release_ready=False,checks=checks),indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
