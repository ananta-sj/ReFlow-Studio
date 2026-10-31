"""Check final durable-queue receipts and user-data integrity; no workers/models."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PREFIX = '2026-10-10-durable-queue-'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

baseline = read(OUT / '2026-10-10-control-paths-state-integrity.json')
state = {name: {'sha256': sha(ROOT / name), 'unchanged': sha(ROOT / name).lower() == record['current'].lower()}
         for name, record in baseline['state'].items()}
receipts = {name: read(OUT / (PREFIX + name + '.json')) for name in
            ('backend-complete', 'frontend', 'graph-contracts', 'recovery')}
checks = {name + '_passed': receipt['passed'] for name, receipt in receipts.items()}
checks['tested_sources_unchanged'] = all(sha(ROOT / name) == expected for receipt in receipts.values()
                                       for name, expected in receipt['source_sha256'].items())
checks['five_saved_state_files_unchanged'] = all(item['unchanged'] for item in state.values())
video = ROOT / 'docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4'
checks['accepted_video_unchanged'] = sha(video).lower() == baseline['accepted_video_sha256'].lower()
recovery = receipts['recovery']
fixture = Path(recovery['fixture'])
before = read(fixture / 'restored-queue.json')
current = read(fixture / 'resumed-current-session.json')
after = read(fixture / 'resumed-session.json')
checks['restored_jobs_paused'] = before['paused'] and not before['busy'] and [item['status'] for item in before['queue']] == ['queued'] * 3
checks['current_only_resumed'] = current['paused'] and [item['status'] for item in current['queue']] == ['completed', 'queued', 'queued']
checks['failure_advances_to_third'] = [item['status'] for item in after['queue']] == ['completed', 'failed', 'completed']
checks['ids_and_parameters_preserved'] = all([item[key] for item in before['queue']] == [item[key] for item in after['queue']] for key in ('id', 'params'))
checks['final_worker_idle_and_marker_cleared'] = not after['busy'] and not (fixture / 'render_state.json').exists()
checks['no_live_model_execution'] = recovery['model_execution_permitted'] is False
result = {'passed': all(checks.values()), 'checks': checks, 'state': state,
          'accepted_video_sha256': sha(video), 'backend_tests': receipts['backend-complete']['tests_run'],
          'backend_modules': len(receipts['backend-complete']['modules']),
          'frontend_checks': len(receipts['frontend']['checks']) + len(receipts['graph-contracts']['checks']),
          'new_native_walkthrough': False, 'stage_checkpoint_reuse_exercised': False,
          'live_model_calls': False, 'dependencies_added': False}
(OUT / (PREFIX + 'integrity.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert result['passed'], 'Final durable-queue evidence verification failed'
