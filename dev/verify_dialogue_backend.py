"""Record complete backend validation and saved-state/source integrity."""
from pathlib import Path
import hashlib,json,os,sys,time,unittest,argparse
from datetime import date
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]
TEMP=ROOT/'temp/tests-dialogue-2026-10-09';TEMP.mkdir(parents=True,exist_ok=True)
os.environ.update(TEMP=str(TEMP),TMP=str(TEMP),PYTHONIOENCODING='utf-8')
# Setting the environment here only affects future children, not Python's
# already-open Windows streams. Match main.py for standalone validation.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--label',choices=['dialogue','hybrid','assisted-review','engine-readiness','runtime-probe','windows-publication','optional-readiness','optional-workflow','stage-recovery','resource-routing','ui-walkthrough','preference-graph','control-paths','native-recovery','graph-controls','durable-queue','live-workflow','windows-release'],default='dialogue')
parser.add_argument('--date',type=date.fromisoformat,default=date(2026,10,9))
arguments=parser.parse_args();label=arguments.label
files=['core/dialogue_connections.py','core/providers/dialogue_chat.py','core/dialogue_supervision.py','core/settings.py','frontend/src/pages/Settings.tsx','core/dialogue_adaptation.py','core/pipeline.py','core/pipeline_contracts.py','core/run_manifest.py','core/indictrans2_worker.py','core/providers/translation/indictrans2_local.py','core/feature_session.py','core/cue_review.py','bridge/api.py','frontend/src/lib/api.ts','frontend/src/components/shared/CueReviewPanel.tsx']
state={name:sha(ROOT/name) for name in ('models.json','settings.json','ui_preferences.json','hardware_profile.json','graph.json')}
files.extend(['core/engine_readiness.py', 'frontend/src/pages/Dashboard.tsx'])
files.extend(['core/runtime_probe.py', 'core/runtime_probe_worker.py'])
files.append('core/render_context.py')
files.append('core/runtime_probe_contract.py')
files.append('core/python_runtime.py')
files.append('dev/verify_dialogue_backend.py')
files.append('dev/test_architecture_contracts.py')
files.append('dev/test_resource_routing.py')
files.append('dev/test_persistence_safety.py')
files.extend(['frontend/src/App.tsx', 'frontend/src/lib/use-confirm.tsx',
              'dev/verify_recovery_frontend.cjs', 'dev/run_control_walkthrough.py'])
files.extend(['dev/verify_graph_controls.cjs', 'frontend/src/lib/render-params.ts'])
files.extend(['core/ui_preferences.py', 'dev/test_ui_preferences.py', 'frontend/src/main.tsx',
              'frontend/src/lib/preference-storage.ts', 'frontend/src/lib/graph-config.ts'])
files.extend('frontend/src/lib/'+name+'.ts' for name in ('use-render-config', 'use-experience',
              'use-theme', 'use-accent-color', 'use-help-tooltips', 'use-tour'))
files.extend(['core/stage_checkpoints.py', 'core/transcription.py'])
files.extend(['core/parallel_policy.py', 'core/hardware_monitor.py', 'frontend/src/lib/eta.ts', 'frontend/src/pages/Nodes.tsx'])
files.extend(['core/queue_manager.py', 'core/render_state.py', 'dev/test_durable_queue.py', 'dev/verify_worker_recovery.py'])
files.extend(['core/run_demucs.py', 'core/audio_separator.py', 'dev/verify_live_workflow_recovery.py',
              'dev/verify_live_workflow_output.py', 'dev/verify_demucs_repeatability.py'])
files.extend(['core/application_lock.py', 'main.py', 'README.txt', 'packaging/build_portable.py'])
code={name:sha(ROOT/name) for name in files}
modules=['dev.'+p.stem for p in sorted((ROOT/'dev').glob('test_*.py'))]
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in modules)
started=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(suite)
receipt=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),modules=modules,elapsed_seconds=time.monotonic()-started,saved_state_unchanged=state=={name:sha(ROOT/name) for name in state},source_unchanged=code=={name:sha(ROOT/name) for name in code},source_sha256=code)
receipt['passed']=result.wasSuccessful() and receipt['saved_state_unchanged'] and receipt['source_unchanged']
path=ROOT/('docs/validation/'+arguments.date.isoformat()+'-'+label+'-backend-complete.json')
path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('RECEIPT',path,'passed=',receipt['passed'],flush=True)
raise SystemExit(0 if receipt['passed'] else 1)
