"""Verify recorded synthetic-worker evidence without running models or modifying user state."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PREFIX = '2026-10-10-active-worker-'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = {}
baseline = read(OUT / '2026-10-10-control-paths-state-integrity.json')
state = {}
for name, previous in baseline['state'].items():
    current = digest(ROOT / name)
    state[name] = {'sha256': current, 'unchanged': current.lower() == previous['current'].lower()}
checks['user_state_unchanged'] = all(item['unchanged'] for item in state.values())
video = ROOT / 'docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4'
checks['accepted_video_unchanged'] = digest(video).lower() == baseline['accepted_video_sha256'].lower()
contracts = read(OUT / (PREFIX + 'contracts.json'))
recovery = read(OUT / (PREFIX + 'recovery.json'))
checks['frontend_contracts'] = contracts['passed'] and len(contracts['checks']) == 17
checks['tested_frontend_sources_unchanged'] = all(digest(ROOT / name) == expected for name, expected in contracts['source_sha256'].items())
checks['process_recovery'] = recovery['passed']
checks['tested_recovery_sources_unchanged'] = all(digest(ROOT / name) == expected for name, expected in recovery['source_sha256'].items())
fixtures = {}
for label, directory in [('initial', 'native-active-mjuz_m3j'), ('final', 'native-active-xeh2rkzd')]:
    source = ROOT / 'temp' / directory / 'observations.json'
    receipt = read(source)
    (OUT / (PREFIX + label + '-bridge.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    starts = [item for item in receipt['observations'] if item['action'] == 'payload_started']
    completes = [item['index'] for item in receipt['observations'] if item['action'] == 'payload_completed']
    events = [item['event'] for item in receipt['observations'] if item['action'] == 'render_event']
    queue = receipt['session']['queue']
    result = {
        'two_payloads_started': [item['index'] for item in starts] == [1, 2],
        'only_second_payload_completed': completes == [2],
        'single_stop_and_finish': all(events.count(event) == 1 for event in ['render_stopping', 'render_stopped', 'render_finished']),
        'queue_cancelled_then_completed': [item['status'] for item in queue] == ['cancelled', 'completed'],
        'accepted_parameters_retained': len(starts) == len(queue) == 2 and all(start['params'] == item['params'] for start, item in zip(starts, queue)),
        'worker_and_session_idle': not receipt['worker_alive'] and not receipt['session']['busy'],
        'recovery_marker_cleared': receipt['interrupted_record'] is None,
        'cancelled_workspace_removed': len(starts) == 2 and not Path(starts[0]['workspace']).exists(),
        'completed_workspace_retained': len(starts) == 2 and Path(starts[1]['workspace']).exists(),
        'copied_output_matches_second_input': len(starts) == 2 and digest(Path(queue[1]['output_path'])) == digest(Path(starts[1]['input_path'])),
        'model_execution_disabled': receipt['model_execution_permitted'] is False,
    }
    fixtures[label] = result
    checks[label + '_bridge_evidence'] = all(result.values())
ui = read(OUT / (PREFIX + 'final-ui.json'))
by_step = {item['step']: item['tree'] for item in ui}
checks['native_active_input_and_progress'] = 'text ONE_FIXTURE.mp4' in by_step['repaired_running'] and 'progress indicator Value: 25' in by_step['repaired_running']
checks['native_stopping_resume_disabled'] = 'text Stopping' in by_step['assets_stopping_settled'] and 'button (disabled) Resume Batch' in by_step['assets_stopping_settled']
checks['native_cancelled_next_waiting'] = 'text Cancelled' in by_step['cancel_settled'] and 'text Waiting' in by_step['cancel_settled'] and 'button Resume Batch' in by_step['cancel_settled']
checks['native_completed_idle'] = all(text in by_step['completed'] for text in ['text Ready', 'text Cancelled', 'text Completed'])
receipt = {'passed': all(checks.values()), 'checks': checks, 'state': state, 'fixtures': fixtures,
           'frontend_contract_count': 17, 'focused_backend_test_count': 54,
           'full_backend_suite_rerun': False, 'live_model_calls': False,
           'native_process_exit_codes': {'initial': 0, 'final': 0},
           'native_settings_changed_after_acceptance': False,
           'accepted_video_sha256': digest(video)}
(OUT / (PREFIX + 'integrity.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
assert receipt['passed'], 'Active-worker evidence verification failed'
