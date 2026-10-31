"""Final receipt/source/user-data audit. No UI, engines, downloads or API calls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PREFIX = '2026-10-12-live-workflow-'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


baseline = read(OUT / '2026-10-10-control-paths-state-integrity.json')
state = {name: {'sha256': sha(ROOT / name), 'unchanged': sha(ROOT / name).lower() == record['current'].lower()}
         for name, record in baseline['state'].items()}
backend = read(OUT / (PREFIX + 'backend-complete.json'))
run = read(OUT / (PREFIX + '0eeba52c.json'))
audit = read(OUT / (PREFIX + '0eeba52c-output-audit.json'))
human = read(OUT / (PREFIX + 'human-review.json'))
native = read(OUT / (PREFIX + 'native-integrity.json'))
repeat = read(OUT / '2026-10-12-demucs-repeatability-89153e25.json')
manifests = [read(Path(item['manifest_path'])) for item in run['passes']]
stems = [[artifact['sha256'] for operation in manifest['operations'] if operation['stage'] == 'separate'
          for artifact in operation['artifacts']] for manifest in manifests]
previous_video = ROOT / 'docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4'
checks = {
    'full_backend_suite_passed': backend['passed'] and backend['failures'] == backend['errors'] == 0,
    'backend_recorded_sources_match_delivered_code': all(sha(ROOT / name) == expected
        for name, expected in backend['source_sha256'].items()),
    'five_saved_state_files_unchanged': all(item['unchanged'] for item in state.values()),
    'previous_accepted_video_unchanged': sha(previous_video) == baseline['accepted_video_sha256'].lower(),
    'tested_source_video_unchanged': sha(Path(run['source'])) == run['source_sha256'],
    'native_dashboard_acceptance_passed': native['passed']
        and native['source_sha256'] == sha(ROOT / 'frontend/src/pages/Dashboard.tsx'),
    'real_repeatability_acceptance_passed': repeat['passed']
        and repeat['worker_sha256'] == sha(ROOT / 'core/run_demucs.py'),
    'separation_identical_across_cancel_restart': len(stems) == 2 and len(stems[0]) == 2 and stems[0] == stems[1],
    'independent_recovery_output_audit_passed': audit['passed'] and all(audit['checks'].values()),
    'human_review_matches_tested_output': sha(Path(audit['output'])) == audit['output_sha256'] == human['output_sha256'],
    'human_review_accepts_this_clip': human['human_delivery_accepted'] and human['human_speech_video_timing_accepted']
        and human['no_english_audible_reported'],
    'closed_workers_and_workspaces': all(item['workspace_removed'] and item['owned_processes_released']
        and item['speech_sessions_released'] for item in run['passes']),
    'original_driver_stem_lookup_failure_preserved': run['passed'] is False
        and len(run['passes'][1]['stems']) == 0 and len(audit['verified_stem_paths']) == 4,
}
result = dict(passed=all(checks.values()), checks=checks, state=state,
    backend_tests=backend['tests_run'], backend_modules=len(backend['modules']),
    backend_elapsed_seconds=backend['elapsed_seconds'], output_audit_checks=len(audit['checks']),
    native_checks=len(native['checks']), source_sha256=backend['source_sha256'],
    evidence_sha256={name:sha(OUT / (PREFIX + name + '.json')) for name in
        ('0eeba52c', '0eeba52c-output-audit', 'human-review', 'native-integrity', 'backend-complete')},
    human_accepted_output_sha256=human['output_sha256'], dependencies_added=False,
    new_models_downloaded=False, paid_calls=False, release_ready=False,
    dense_dialogue_automatic_fit_ready=False, native_real_model_crash_recovery_tested=False)
(OUT / (PREFIX + 'integrity.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({key:result[key] for key in ('passed', 'checks', 'backend_tests', 'backend_modules')}, indent=2))
assert result['passed'], 'Final live-workflow evidence audit failed'
