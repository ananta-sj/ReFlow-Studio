"""Real offline hint checks through existing desktop/provider/worker paths."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
import hashlib,importlib.util,json,os,socket,sys
from pathlib import Path
root,scratch,route=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                  HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',
                  TEMP=str(scratch),TMP=str(scratch),PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
def denied(*args,**kwargs):raise RuntimeError('Recognition evaluation blocks external network access')
socket.create_connection=socket.getaddrinfo=denied
from core.render_context import RenderContext,bind_job
profile_path=root/'models/indicf5/references/abhishek/profile.json'
reference=json.loads(profile_path.read_text(encoding='utf-8'))
audio=profile_path.parent/reference['reference_audio']
report=dict(passed=False,route=route,checks={},model_downloaded=False,defaults_changed=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
job=RenderContext(scratch)
try:
    check('reference_identity',hashlib.sha256(audio.read_bytes()).hexdigest()==reference['reference_sha256'])
    if route=='cpu':
        os.environ['REFLOW_WORKER_PYTHON']=str(root/'runtime_profiles/recognition-candidate/python.exe')
        from core.providers.stt.whisper_local import WhisperLocalProvider
        provider=WhisperLocalProvider(str(root/'models/whisper/ct2-turbo-candidate-compat/model'))
    else:
        from core.providers.stt.whisper_turbo_local import WhisperTurboLocalProvider
        provider=WhisperTurboLocalProvider(str(root/'models/f5/reference-asr'))
    with bind_job(job):result=provider.transcribe(str(audio),source_language='Hindi')
    report['transcription']=result.to_payload()
    text=' '.join(cue['text'] for cue in result)
    check('hindi_label',result.language=='hi')
    check('hint_not_detection',result.language_origin=='hint' and result.language_probability is None)
    check('devanagari_present',any('\u0900'<=c<='\u097f' for c in text))
    check('no_urdu_script',not any('\u0600'<=c<='\u06ff' for c in text))
    check('nonempty_timed_speech',bool(result) and all(0<=cue['start']<cue['end'] for cue in result))
    check('owned_workers_released',not job.processes and (route=='cpu' or provider.worker_released))
    if route=='gpu':
        report['independent_block_detection']=[{k:row[k] for k in ['language','probability'] if k in row}
                                                for row in provider.last_result['blocks']]
    check('desktop_parent_without_torch',importlib.util.find_spec('torch') is None)
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    job.cleanup()
    check('job_workspace_removed',not job.workspace.exists())
    report['passed']=all(report['checks'].values()) and 'error' not in report
    (root/f'docs/validation/2026-10-15-recognition-language-{route}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
'''


def main():
    route = sys.argv[1]
    assert route in {'cpu', 'gpu'}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='recognition-language-', dir=ROOT/'temp') as scratch:
        with (ROOT/f'docs/validation/2026-10-15-recognition-language-{route}.log').open('wb') as log:
            result = subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'), '-B', '-X', 'utf8',
                                     '-c', CODE, str(ROOT), scratch, route], env=env,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=360,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print(route, 'exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
