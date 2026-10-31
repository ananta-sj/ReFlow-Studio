"""Crash and restart a disposable real bridge worker; synthetic payload only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
parser = argparse.ArgumentParser()
parser.add_argument('--child', choices=('crash', 'resume'))
parser.add_argument('--fixture')
parser.add_argument('--batch', action='store_true')
args = parser.parse_args()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if args.child:
    fixture = Path(args.fixture).resolve()
    assert fixture.is_relative_to((ROOT / 'temp').resolve())
    assert (fixture / 'QA_FIXTURE').read_text() == 'Synthetic recovery worker'
    import config
    config.BASE_DIR = str(fixture)
    config.TEMP_PATH = str(fixture / 'temp')
    import bridge.api as api
    from core import render_state
    from core.queue_manager import QueueManager
    api.push.emit = lambda *args: None  # Headless delivery, real session state.
    class SyntheticBridge(api.PythonBridge):
        def _run_render_inner(self, input_path, params, template_id='video_dub'):
            self._emit_render('render_started', {'inputPath': input_path})
            self._emit_render('progress', {'percent': 25, 'status': 'QA synthetic payload'})
            if args.child == 'crash':
                # Abrupt process exit skips the outer worker's finally block.
                marker = render_state.get_interrupted()
                assert marker is not None
                (fixture / 'crash-record.json').write_text(json.dumps(marker), encoding='utf-8')
                os._exit(73)
            if args.batch and Path(input_path).name == 'FAIL_FIXTURE.bin':
                raise RuntimeError('QA synthetic failure')
            output = fixture / ('QA_OUTPUT_' + Path(input_path).name if args.batch else 'QA_OUTPUT.bin')
            shutil.copyfile(input_path, output)
            return str(output)
    bridge = SyntheticBridge.__new__(SyntheticBridge)
    bridge._render_lock = threading.RLock()
    bridge._render_thread = None
    bridge._render_busy = False
    bridge._render_killed = False
    bridge._active_job = None
    bridge._current_queue_item = None
    bridge._persistence_warnings = []
    bridge._persistence_warning_lock = threading.Lock()
    bridge.queue_manager = QueueManager(str(fixture / 'queue_state.json')) if args.batch else QueueManager()
    bridge.settings = {'auto_cleanup_temp': False}
    if args.child == 'crash':
        input_path, params, template = str(fixture / 'SOURCE_FIXTURE.bin'), {'lang': 'hi', 'voice': 'CLONED_USER'}, 'video_dub'
        if args.batch:
            bridge.add_queue_drafts([str(fixture / name) for name in ('SOURCE_FIXTURE.bin', 'FAIL_FIXTURE.bin', 'THIRD_FIXTURE.bin')])
            assert bridge.start_queue_batch({'lang': 'hi', 'nested': {'test': 'frozen'}})['ok']
    else:
        offer = bridge.get_interrupted_render()
        assert offer is not None
        (fixture / 'restart-offer.json').write_text(json.dumps(offer), encoding='utf-8')
        input_path, params, template = offer['input_path'], offer['params'], offer['template_id']
        if args.batch:
            before = bridge.get_session_state()
            assert before['paused'] and not before['busy']
            assert [item['status'] for item in before['queue']] == ['queued'] * 3
            (fixture / 'restored-queue.json').write_text(json.dumps(before), encoding='utf-8')
    if args.child == 'resume':
        assert bridge.resume_interrupted_render(offer['recovery_token'])['ok']
    elif not args.batch:
        assert bridge.start_render(input_path, params, template)['ok']
    bridge._render_thread.join(10)
    assert not bridge._render_thread.is_alive()
    if args.child == 'resume':
        session = bridge.get_session_state()
        assert session['render']['status'] == 'finished' and not session['busy']
        assert bridge.get_interrupted_render() is None
        if args.batch:
            assert session['paused'] and [item['status'] for item in session['queue']] == ['completed', 'queued', 'queued']
            (fixture / 'resumed-current-session.json').write_text(json.dumps(session), encoding='utf-8')
            assert bridge.resume_queue_batch()['ok']
            bridge._render_thread.join(10)
            assert not bridge._render_thread.is_alive()
            session = bridge.get_session_state()
            assert [item['status'] for item in session['queue']] == ['completed', 'failed', 'completed']
            assert session['queue'][1]['error'] == 'QA synthetic failure'
        (fixture / 'resumed-session.json').write_text(json.dumps(session), encoding='utf-8')
    raise SystemExit(0)

fixture = Path(tempfile.mkdtemp(prefix='worker-recovery-', dir=ROOT / 'temp')).resolve()
(fixture / 'QA_FIXTURE').write_text('Synthetic recovery worker')
(fixture / 'SOURCE_FIXTURE.bin').write_bytes(b'QA payload, not dubbed media')
if args.batch:
    (fixture / 'FAIL_FIXTURE.bin').write_bytes(b'QA failed payload')
    (fixture / 'THIRD_FIXTURE.bin').write_bytes(b'QA third payload')
state = {name: sha(ROOT / name) for name in ('models.json', 'settings.json', 'graph.json', 'hardware_profile.json', 'ui_preferences.json')}
sources = {name: sha(ROOT / name) for name in ('bridge/api.py', 'core/queue_manager.py', 'core/render_state.py', 'core/render_context.py', 'dev/verify_worker_recovery.py')}
phases = []
for mode, expected in [('crash', 73), ('resume', 0)]:
    command = [sys.executable, '-B', str(Path(__file__).resolve()), '--child', mode, '--fixture', str(fixture)]
    if args.batch:
        command.append('--batch')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
    (fixture / (mode + '.log')).write_bytes(result.stdout + result.stderr)
    assert result.returncode == expected, (mode, result.returncode, result.stderr.decode('utf-8', errors='replace'))
    phases.append({'phase': mode, 'exit_code': result.returncode})
    if mode == 'crash':
        assert (fixture / 'render_state.json').is_file()
crashed = json.loads((fixture / 'crash-record.json').read_text(encoding='utf-8'))
offer = json.loads((fixture / 'restart-offer.json').read_text(encoding='utf-8'))
assert crashed == offer
assert not (fixture / 'render_state.json').exists()
assert sha(fixture / 'SOURCE_FIXTURE.bin') == sha(fixture / ('QA_OUTPUT_SOURCE_FIXTURE.bin' if args.batch else 'QA_OUTPUT.bin'))
receipt = {'passed': True, 'fixture': str(fixture), 'phases': phases,
    'offer_preserved_across_process_restart': True, 'marker_cleared_after_completion': True,
    'synthetic_output_matches_input': True, 'model_execution_permitted': False,
    'stage_checkpoint_reuse_exercised': False,
    'saved_state_unchanged': state == {name: sha(ROOT / name) for name in state},
    'source_unchanged': sources == {name: sha(ROOT / name) for name in sources}, 'source_sha256': sources}
assert receipt['saved_state_unchanged'] and receipt['source_unchanged']
if args.batch:
    before = json.loads((fixture / 'restored-queue.json').read_text())
    after = json.loads((fixture / 'resumed-session.json').read_text())
    assert [item['id'] for item in before['queue']] == [item['id'] for item in after['queue']]
    assert [item['params'] for item in before['queue']] == [item['params'] for item in after['queue']]
    receipt.update(batch_restored_paused=True, job_ids_and_parameters_retained=True,
                   final_statuses=[item['status'] for item in after['queue']], resumed_current_only_before_batch_resume=True)
prefix = 'durable-queue' if args.batch else 'active-worker'
(ROOT / ('docs/validation/2026-10-10-' + prefix + '-recovery.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
