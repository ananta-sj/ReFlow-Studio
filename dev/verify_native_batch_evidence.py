"""Verify recorded native batch acceptance without starting engines or UI."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PREFIX = '2026-10-10-native-batch-'
FIXTURE = ROOT / 'temp/native-active-18k60c0l'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


initial = read(FIXTURE / 'observations-initial.json')
resume = read(FIXTURE / 'observations-resume.json')
for phase, receipt in [('initial', initial), ('resume', resume)]:
    (OUT / (PREFIX + phase + '-bridge.json')).write_text(
        json.dumps(receipt, indent=2), encoding='utf-8')
observations = resume['observations']
boot = observations[0]
before = boot['session']['queue']
after = resume['session']['queue']


def actions(name):
    return [item for item in observations if item['action'] == name]


def document(step, notes):
    tree = next(item['tree'] for item in notes if item['step'] == step)
    return tree.split('Document text: ```', 1)[-1]


notes = read(OUT / (PREFIX + 'resume-ui.json'))
initial_notes = read(OUT / (PREFIX + 'initial-ui.json'))
starts = actions('payload_started')
events = [item['event'] for item in actions('render_event')]
pause = actions('pause_requested')
batch = actions('batch_resume')
recovery = actions('recovery_resume')
checks = {
    'initial_launch_idle_paused': initial['session']['paused'] and not initial['session']['busy']
        and not initial['worker_alive'] and len(initial['session']['queue']) == 4
        and all(item['status'] == 'queued' for item in initial['session']['queue']),
    'initial_launch_started_no_payload': not any(item['action'] == 'payload_started'
        for item in initial['observations']),
    'dismissal_preserved_recovery_record': initial['interrupted_record'] == boot['interrupted'],
    'relaunch_idle_paused': boot['session']['paused'] and not boot['session']['busy'],
    'one_token_bound_recovery_accepted': len(recovery) == 1 and recovery[0]['result']['ok']
        and recovery[0]['token'] == boot['interrupted']['recovery_token']
        and boot['interrupted']['queue_item_id'] == before[0]['id'],
    'two_explicit_batch_resumes_accepted': len(batch) == 2 and all(item['result']['ok'] for item in batch),
    'pause_after_current_accepted': len(pause) == 1 and pause[0]['paused'] and pause[0]['result']['ok'],
    'each_payload_started_once_in_order': [item['index'] for item in starts] == [1, 2, 3, 4]
        and [item['input_path'] for item in starts] == [item['input_path'] for item in before],
    'three_outputs_one_deliberate_failure': [item['index'] for item in actions('payload_completed')] == [1, 2, 4]
        and [item['index'] for item in actions('payload_failed')] == [3],
    'terminal_events_correct': events.count('render_finished') == 3 and events.count('render_error') == 1
        and events.count('render_started') == 4 and 'render_stopped' not in events,
    'final_statuses_correct': [item['status'] for item in after] == ['completed', 'completed', 'failed', 'completed'],
    'original_ids_and_parameters_preserved': all([item[key] for item in before] == [item[key] for item in after]
        for key in ('id', 'params', 'template_id', 'input_path')) and len({item['id'] for item in after}) == 4,
    'accepted_workers_preserved_despite_future_defaults': all(item['params'] == before[index]['params']
        and item['params']['parallel_workers'] == 2 for index, item in enumerate(starts))
        and json.loads(resume['ui_preferences']['reflow.renderConfig'])['parallelWorkers'] == 1,
    'final_idle_and_recovery_cleared': not resume['session']['busy'] and not resume['worker_alive']
        and resume['interrupted_record'] is None and not (FIXTURE / 'render_state.json').exists(),
    'persisted_queue_matches_final_receipt': read(FIXTURE / 'queue_state.json')['items'] == after,
    'successful_outputs_match_synthetic_inputs': all(sha(Path(item['output_path'])) == sha(Path(item['input_path']))
        for item in after if item['status'] == 'completed'),
    'failed_job_has_error_and_no_output': after[2]['output_path'] is None
        and after[2]['error'] == 'QA middle job failure; no model execution',
    'native_initial_queue_paused': 'Batch paused' in document('initial_assets_settled', initial_notes)
        and document('initial_assets_settled', initial_notes).count('Waiting') == 4,
    'native_current_only_resume': 'Batch paused' in document('current_completed_paused', notes)
        and document('current_completed_paused', notes).count('Waiting') == 3,
    'native_pause_completed_second': 'Batch paused' in document('second_completed_paused', notes)
        and document('second_completed_paused', notes).count('Completed') == 2
        and document('second_completed_paused', notes).count('Waiting') == 2,
    'native_failure_advanced': 'Failed' in document('failure_advanced_to_fourth', notes)
        and 'Rendering · 25%' in document('failure_advanced_to_fourth', notes),
    'native_final_ready': 'Ready' in document('final_ready', notes)
        and document('final_ready', notes).count('Completed') == 3
        and 'Failed' in document('final_ready', notes) and 'Waiting' not in document('final_ready', notes),
    'no_live_models': initial['model_execution_permitted'] is False and resume['model_execution_permitted'] is False,
}
baseline = read(OUT / '2026-10-10-control-paths-state-integrity.json')
state = {name: {'sha256': sha(ROOT / name), 'unchanged': sha(ROOT / name).lower() == record['current'].lower()}
         for name, record in baseline['state'].items()}
checks['five_saved_state_files_unchanged'] = all(item['unchanged'] for item in state.values())
video = ROOT / 'docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4'
checks['accepted_video_unchanged'] = sha(video).lower() == baseline['accepted_video_sha256'].lower()
previous = [read(OUT / ('2026-10-10-durable-queue-' + name + '.json'))
            for name in ('backend-complete', 'frontend', 'graph-contracts', 'recovery')]
checks['previous_tested_sources_unchanged'] = all(sha(ROOT / name) == expected
    for receipt in previous for name, expected in receipt['source_sha256'].items())
result = {'passed': all(checks.values()), 'checks': checks, 'state': state,
    'fixture': str(FIXTURE), 'accepted_video_sha256': sha(video),
    'current_evidence_sha256': {name: sha(OUT / (PREFIX + name + '.json'))
        for name in ('initial-ui', 'resume-ui', 'initial-bridge', 'resume-bridge')},
    'helper_sha256': sha(ROOT / 'dev/run_active_walkthrough.py'),
    'historical_backend_tests': previous[0]['tests_run'], 'full_suite_rerun': False,
    'native_process_crash_exercised': False, 'stage_checkpoint_reuse_exercised': False,
    'live_model_calls': False, 'dependencies_added': False}
(OUT / (PREFIX + 'integrity.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert result['passed'], 'Native batch evidence validation failed'
