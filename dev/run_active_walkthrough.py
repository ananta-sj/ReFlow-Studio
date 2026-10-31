"""Exercise real desktop/bridge worker lifecycle with a synthetic gated payload.

Only _run_render_inner substitutes work; control overrides record real results.
No inference, downloads or provider calls.
Owned release-N.flag files let the operator inspect each phase without timing races.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PYTHONIOENCODING'] = 'utf-8'
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')
parser = argparse.ArgumentParser()
parser.add_argument('--restored', action='store_true')
parser.add_argument('--fixture', type=Path)
parser.add_argument('--phase', choices=('initial', 'resume', 'default'), default='default')
args = parser.parse_args()
fresh = args.fixture is None
fixture = (Path(tempfile.mkdtemp(prefix='native-active-', dir=ROOT / 'temp')) if fresh else args.fixture).resolve()
assert fixture.is_relative_to((ROOT / 'temp').resolve())
if fresh:
    (fixture / 'QA_FIXTURE').write_text('Synthetic worker only', encoding='utf-8')
assert (fixture / 'QA_FIXTURE').read_text(encoding='utf-8') == 'Synthetic worker only'
inputs = fixture / 'inputs'
inputs.mkdir(exist_ok=True)
source = inputs / 'ONE_FIXTURE.mp4'
ffmpeg = ROOT / 'ffmpeg/bin/ffmpeg.exe'
os.environ['PATH'] = str(ffmpeg.parent) + os.pathsep + os.environ['PATH']
if fresh:
    subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
        '-i', 'color=c=blue:s=320x180:r=25', '-t', '1', '-an', '-c:v', 'mpeg4',
        str(source)], check=True, timeout=30)
second = inputs / 'TWO_FIXTURE.mp4'
if fresh:
    shutil.copyfile(source, second)
    if args.restored:
        for name in ('THREE_FAIL_FIXTURE.mp4', 'FOUR_FIXTURE.mp4'):
            shutil.copyfile(source, inputs / name)
import config
config.BASE_DIR = str(fixture)
for name, folder in [('TEMP_PATH', 'temp'), ('OUTPUT_PATH', 'outputs'),
                     ('MODELS_PATH', 'models'), ('MODELS_DIR', 'models')]:
    target = fixture / folder
    target.mkdir(exist_ok=True)
    setattr(config, name, str(target))
import webview
from bridge.api import PythonBridge
from core import render_state
from core.render_context import current_job, check_cancelled
from core.queue_manager import QueueManager

observations = []
receipt_lock = threading.RLock()

def record(action, **details):
    with receipt_lock:
        observations.append({'action': action, **details})
        (fixture / 'worker-events.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')

class SyntheticBridge(PythonBridge):
    def resume_interrupted_render(self, token):
        result = super().resume_interrupted_render(token)
        record('recovery_resume', token=token, result=result)
        return result

    def resume_queue_batch(self):
        result = super().resume_queue_batch()
        record('batch_resume', result=result)
        return result

    def set_queue_paused(self, paused):
        result = super().set_queue_paused(paused)
        record('pause_requested', paused=paused, result=result)
        return result

    def _emit_render(self, event, payload):
        record('render_event', event=event, payload=payload)
        return super()._emit_render(event, payload)

    def _run_render_inner(self, input_path, params, template_id='video_dub'):
        # The real outer worker owns context, marker, queue, cancellation,
        # completion and cleanup. No ReflowPipeline or engine is initialized.
        index = 1 + sum(item['action'] == 'payload_started' for item in observations)
        job = current_job()
        assert job is not None
        record('payload_started', index=index, input_path=input_path, params=params,
            template_id=template_id, workspace=str(job.workspace))
        self._emit_render('render_started', {'inputPath': input_path})
        self._emit_render('stage', {'stageId': 'stt'})
        self._emit_render('progress', {'percent': 25, 'status': 'QA worker waiting; no model execution'})
        deadline = time.monotonic() + 600
        release = fixture / f'release-{index}.flag'
        while not release.exists() and not job.cancelled.is_set():
            if time.monotonic() >= deadline:
                raise RuntimeError('QA release gate timed out')
            job.cancelled.wait(.05)
        if job.cancelled.is_set():
            record('cancellation_observed', index=index)
            # Keep the real worker alive long enough to inspect the stopping UI.
            while not (fixture / f'cancel-exit-{index}.flag').exists():
                if time.monotonic() >= deadline:
                    break
                time.sleep(.05)
            check_cancelled()
        if args.restored and Path(input_path).name == 'THREE_FAIL_FIXTURE.mp4':
            record('payload_failed', index=index)
            raise RuntimeError('QA middle job failure; no model execution')
        self._emit_render('stage', {'stageId': 'output'})
        check_cancelled()
        output = fixture / 'outputs' / f'QA_OUTPUT_{index}.mp4'
        shutil.copyfile(input_path, output)
        self._emit_render('progress', {'percent': 100, 'status': 'QA synthetic video copied'})
        record('payload_completed', index=index, output=str(output))
        return str(output)

if fresh and args.restored:
    saved_queue = QueueManager(str(fixture / 'queue_state.json'))
    for path in (source, second, inputs / 'THREE_FAIL_FIXTURE.mp4', inputs / 'FOUR_FIXTURE.mp4'):
        saved_queue.add_item(str(path))
    first = saved_queue.prepare_batch({'lang': 'hi', 'source_language': 'en',
        'voice': 'CLONED_USER', 'cast_list': ['CLONED_USER'], 'keep_bg': False,
        'device_id': 'cpu', 'parallel_workers': 2, 'include_subtitles': True}, 'video_dub')
    render_state.mark_started(first.input_path, first.params, first.template_id, queue_item_id=first.id)
bridge = SyntheticBridge()
bridge.settings.update({'onboarding_complete': True, 'auto_cleanup_temp': False})
bridge._ui_preferences.update({'reflow.tourComplete': 'true',
    'reflow-experience-level': 'advanced', 'reflow.renderConfig': json.dumps({
        'lang': 'hi', 'sourceLanguage': 'en', 'voice': 'CLONED_USER', 'keepBg': False})})
if fresh and not args.restored:
    bridge.add_queue_drafts([str(source), str(second)])
record('boot_snapshot', session=bridge.get_session_state(), interrupted=bridge.get_interrupted_render())
window = webview.create_window('Reflow restored batch walkthrough' if args.restored else 'Reflow active worker walkthrough',
    url=(ROOT / 'frontend/dist/index.html').as_uri(), js_api=bridge,
    width=1200, height=800, min_size=(1200, 700), frameless=True, easy_drag=False)
print('FIXTURE', fixture, flush=True)
try:
    webview.start()
finally:
    # Closing a QA window cannot leave its synthetic worker gated indefinitely.
    if bridge._render_thread and bridge._render_thread.is_alive():
        bridge.stop_render()
        for index in range(1, 10):
            (fixture / f'cancel-exit-{index}.flag').touch()
        bridge._render_thread.join(5)
    receipt = {'fixture': str(fixture), 'observations': observations,
        'session': bridge.get_session_state(),
        'interrupted_record': render_state.get_interrupted(),
        'ui_preferences': bridge.get_ui_preferences(), 'model_execution_permitted': False,
        'worker_alive': bool(bridge._render_thread and bridge._render_thread.is_alive())}
    name = 'observations.json' if args.phase == 'default' else 'observations-' + args.phase + '.json'
    (fixture / name).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('RECEIPT', fixture / name, flush=True)
