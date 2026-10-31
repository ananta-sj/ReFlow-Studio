"""Real desktop controls with disposable state and no render/model execution.

The only dialog modification is its initial folder. Close the test window to
publish the bridge observations; fixtures are retained for inspection.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PYTHONIOENCODING'] = 'utf-8'
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')
parser = argparse.ArgumentParser()
parser.add_argument('--recovery', action='store_true')
parser.add_argument('--graph', action='store_true')
args = parser.parse_args()
fixture = Path(tempfile.mkdtemp(prefix='native-controls-', dir=ROOT / 'temp')).resolve()
assert fixture.is_relative_to((ROOT / 'temp').resolve())
inputs = fixture / 'inputs'
inputs.mkdir()
source = inputs / 'SOURCE_FIXTURE.mp4'
ffmpeg = ROOT / 'ffmpeg/bin/ffmpeg.exe'
os.environ['PATH'] = str(ffmpeg.parent) + os.pathsep + os.environ['PATH']
subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                '-i', 'color=c=blue:s=320x180:r=25', '-t', '1', '-an',
                '-c:v', 'mpeg4', str(source)], check=True, timeout=30)

# Import config first to retain existing portable DLL handles, then redirect
# storage before modules capture their settings/registry/recovery paths.
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

observations = []
class GuardedBridge(PythonBridge):
    def set_node_enabled(self, node_id, enabled):
        if args.graph and node_id == 'separate':
            observations.append({'action': 'graph_save_rejection', 'node_id': node_id, 'enabled': enabled})
            return {'ok': False, 'message': 'QA fixture: graph publication rejected.'}
        result = super().set_node_enabled(node_id, enabled)
        observations.append({'action': 'set_node_enabled', 'node_id': node_id,
            'enabled': enabled, 'result': result})
        return result

    def estimate_job_all_devices(self, video_path, stage_flags):
        result = super().estimate_job_all_devices(video_path, stage_flags)
        observations.append({'action': 'estimate_all_devices', 'flags': stage_flags,
            'cast': self.get_cast_list(), 'result': result})
        return result

    def browse_video(self):
        result = webview.windows[0].create_file_dialog(webview.FileDialog.OPEN,
            directory=str(inputs), allow_multiple=True,
            file_types=('Video Files (*.mp4;*.mov;*.avi;*.mkv)',))
        paths = list(result) if result else []
        observations.append({'action': 'browse_video', 'result': paths})
        return paths

    def _start_worker(self, input_path, params, template_id, queue_item_id):
        observations.append({'action': 'render_start_guard', 'input_path': input_path,
            'params': params, 'template_id': template_id, 'queue_item_id': queue_item_id})
        return {'ok': False, 'message': 'QA fixture: model execution is disabled.'}

bridge = GuardedBridge()
if args.graph:
    actors = []
    for name in ('A', 'B'):
        checkpoint = fixture / ('ACTOR_' + name + '_FIXTURE.pth')
        checkpoint.write_bytes(b'QA fixture, not model weights')
        actors.append(bridge.registry.add('voice', 'local_file', 'QA actor '+name+' (fixture)',
            local_path=str(checkpoint), status='installed', request_preset='rvc',
            meta={'qa_fixture': True, 'file_size_bytes': checkpoint.stat().st_size}))
    bridge.settings.update({'onboarding_complete': True})
    bridge._ui_preferences.update({'reflow.tourComplete': 'true',
        'reflow-experience-level': 'advanced', 'reflow.renderConfig': json.dumps({
            'lang': 'hi', 'sourceLanguage': 'en', 'voice': actors[0]['id'], 'keepBg': False})})
    bridge.add_queue_drafts([str(source)])
if args.recovery:
    bridge.settings.update({'onboarding_complete': True})
    bridge._ui_preferences.update({'reflow.tourComplete': 'true'})
    render_state.mark_started(str(source), {'voice': 'CLONED_USER', 'lang': 'hi'}, 'video_dub')
window = webview.create_window('Reflow control walkthrough',
    url=(ROOT / 'frontend/dist/index.html').as_uri(), js_api=bridge,
    width=1200, height=800, min_size=(1200, 700), frameless=True, easy_drag=False)
print('FIXTURE', fixture, flush=True)
try:
    webview.start()
finally:
    receipt = {'fixture': str(fixture), 'source': str(source),
        'recovery_fixture': args.recovery, 'graph_fixture': args.graph, 'observations': observations,
        'graph': bridge.get_graph_definition(), 'cast': bridge.get_cast_list(),
        'session': bridge.get_session_state(),
        'interrupted_record': render_state.get_interrupted(),
        'ui_preferences': bridge.get_ui_preferences(),
        'model_execution_permitted': False}
    (fixture / 'observations.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('RECEIPT', fixture / 'observations.json', flush=True)
