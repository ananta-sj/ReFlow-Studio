"""Authorized temporary local writer/reviewer trial; always remove owned runtime/models."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')
import requests

MODEL = 'qwen3:4b-instruct-2507-q4_K_M'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def safe_owned(path, marker):
    path = path.absolute()
    if path.resolve() != path or not path.is_relative_to((ROOT / 'temp').resolve()) or not path.name.startswith('ollama-eval-'):
        raise RuntimeError('Refusing cleanup outside the owned evaluation directory')
    if (path / 'EVALUATION_OWNER').read_text(encoding='utf-8') != marker:
        raise RuntimeError('Evaluation ownership marker changed')
    for directory, dirs, files in os.walk(path, followlinks=False):
        for entry in [Path(directory), *(Path(directory)/name for name in dirs+files)]:
            if entry.is_symlink() or getattr(entry.lstat(),'st_file_attributes',0)&0x400:
                raise RuntimeError('Refusing evaluation cleanup through reparse points')
    return path


def main():
    from core.render_context import RenderContext, bind_job, _stop_process
    from core.model_registry import ModelRegistry
    from core.providers.resolve import resolve_tts
    from core.providers.dialogue_chat import DialogueChatProvider
    from core.dialogue_supervision import supervise
    home = Path.home()
    external = [home/'.ollama',home/'AppData/Local/Ollama',home/'AppData/Local/Programs/Ollama']
    before_external = {str(path):path.exists() for path in external}
    baseline = {name:sha(ROOT/name) for name in ('models.json','settings.json','graph.json','ui_preferences.json','hardware_profile.json')}
    owned = Path(tempfile.mkdtemp(prefix='ollama-eval-',dir=ROOT/'temp')).resolve()
    marker = owned.name
    (owned/'EVALUATION_OWNER').write_text(marker,encoding='utf-8')
    evidence = ROOT/'docs/validation'/('2026-10-12-'+marker)
    evidence.mkdir()
    report = dict(completed=False,model=MODEL,temporary_root=str(owned),evidence_folder=str(evidence),
        prior_external_ollama_paths=before_external,global_install=False,paid_calls=False,
        settings_modified=False,human_meaning_accepted=False,cases=[])
    receipt = evidence.with_suffix('.json')
    server = None
    server_log = None
    job = None
    started = time.monotonic()

    def save():
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

    save()
    try:
        release = requests.get('https://api.github.com/repos/ollama/ollama/releases/latest',timeout=30)
        release.raise_for_status()
        info = release.json()
        asset = next(item for item in info['assets'] if item['name']=='ollama-windows-amd64.zip')
        report['release'] = dict(version=info['tag_name'],url=asset['browser_download_url'],bytes=asset['size'],digest=asset.get('digest'))
        save()
        print('Downloading standalone Ollama',info['tag_name'],'bytes',asset['size'],flush=True)
        archive = owned/'ollama.zip'
        count = 0
        last = time.monotonic()
        with requests.get(asset['browser_download_url'],stream=True,timeout=(30,90)) as response:
            response.raise_for_status()
            with archive.open('wb') as target:
                for chunk in response.iter_content(1024*1024):
                    target.write(chunk); count+=len(chunk)
                    if time.monotonic()-last>10:
                        print('Runtime download',count,'/',asset['size'],flush=True); last=time.monotonic()
        if count!=asset['size']:
            raise RuntimeError('Standalone download size mismatch')
        report['archive_sha256'] = sha(archive)
        if asset.get('digest') and asset['digest']!='sha256:'+report['archive_sha256']:
            raise RuntimeError('Standalone release checksum mismatch')
        runtime = owned/'runtime'; runtime.mkdir()
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                target=(runtime/member.filename).resolve()
                if not target.is_relative_to(runtime.resolve()) or '\\' in member.filename or ':' in member.filename:
                    raise RuntimeError('Unsafe standalone archive member')
            package.extractall(runtime)
        executable=runtime/'ollama.exe'
        if not executable.is_file():
            raise RuntimeError('Standalone CLI not found')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0)); port=listener.getsockname()[1]
        base='http://127.0.0.1:'+str(port)
        isolated_home=owned/'home'; isolated_home.mkdir()
        temp=owned/'scratch'; temp.mkdir()
        env={**os.environ,'USERPROFILE':str(isolated_home),'HOME':str(isolated_home),
            'HOMEDRIVE':isolated_home.drive,'HOMEPATH':str(isolated_home)[len(isolated_home.drive):],
            'LOCALAPPDATA':str(owned/'local'),'APPDATA':str(owned/'roaming'),'TEMP':str(temp),'TMP':str(temp),
            'OLLAMA_MODELS':str(owned/'models'),'OLLAMA_HOST':base,'OLLAMA_NO_CLOUD':'1',
            'OLLAMA_CONTEXT_LENGTH':'4096','OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1',
            'OLLAMA_KEEP_ALIVE':'5m','OLLAMA_NOPRUNE':'1','CUDA_CACHE_PATH':str(owned/'cuda-cache')}
        server_log=(owned/'server.log').open('wb')
        server=subprocess.Popen([str(executable),'serve'],cwd=owned,env=env,
            stdout=server_log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        report.update(server_pid=server.pid,endpoint=base)
        deadline=time.monotonic()+90
        while True:
            if server.poll() is not None:
                raise RuntimeError('Owned server exited during startup')
            try:
                version=requests.get(base+'/api/version',timeout=2)
                version.raise_for_status(); report['server_version']=version.json(); break
            except requests.RequestException:
                if time.monotonic()>deadline: raise RuntimeError('Owned server startup timeout')
                time.sleep(.5)
        print('Pulling temporary model',MODEL,flush=True)
        deadline=time.monotonic()+1200; last=0
        with requests.post(base+'/api/pull',json={'model':MODEL,'stream':True},stream=True,timeout=(10,90)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if time.monotonic()>deadline: raise RuntimeError('Temporary model pull timeout')
                if not line: continue
                status=json.loads(line)
                if status.get('error'): raise RuntimeError(status['error'])
                if time.monotonic()-last>10 or status.get('status')=='success':
                    print('Model pull',status.get('status'),status.get('completed'),status.get('total'),flush=True);last=time.monotonic()
            if status.get('status')!='success': raise RuntimeError('Model pull did not complete')
        tags=requests.get(base+'/api/tags',timeout=10).json()
        entry=next(item for item in tags['models'] if item['name']==MODEL)
        if not entry['digest'].startswith('0edcdef34593'):
            raise RuntimeError('Approved model tag identity changed; evaluation stopped')
        report['model_identity']=entry
        job=RenderContext(owned/'scratch')
        connection=dict(id='temporary-evaluation',label='Temporary Qwen3 writer/reviewer',endpoint=base+'/v1',
            model=MODEL,credential_ref=None,local=True)
        writer=DialogueChatProvider(connection); reviewer=DialogueChatProvider(connection)
        registry=ModelRegistry().snapshot()
        # Start with complete real source/translation evidence, then retain the
        # prior cropped overflow as an explicitly incomplete-context case.
        full=next((ROOT/'docs/validation/2026-10-09-pipeline-foundation-full-known-91f5371e/run_records').glob('*/manifest.json'))
        original=read(full); artifact=next(item for item in original['cue_artifacts'] if item['phase']=='speech-input')
        if sha(artifact['path'])!=artifact['sha256']: raise RuntimeError('Complete cue evidence changed')
        cues=read(artifact['path'])['segments']
        selected=[dict(label='complete-opening',cue=cues[0],available=cues[1]['start']-cues[0]['start']),
            dict(label='complete-establishing-shot',cue=cues[2],available=cues[3]['start']-cues[2]['start'])]
        dense=read(ROOT/'docs/validation/2026-10-12-dense-options-072f2715.json')
        selected.append(dict(label='cropped-overflow-context-incomplete',cue=dict(source_text=dense['source_text'],
            text=dense['translated_text']),available=8))
        with bind_job(job):
            speech=resolve_tts(registry,'cpu')
            for case in selected:
                before=time.monotonic(); print('Evaluating',case['label'],flush=True)
                try:
                    result=supervise(speech,writer,reviewer,case['cue']['source_text'],case['cue']['text'],case['available'])
                    report['cases'].append(dict(label=case['label'],elapsed_seconds=round(time.monotonic()-before,3),result=result))
                except Exception as error:
                    report['cases'].append(dict(label=case['label'],elapsed_seconds=round(time.monotonic()-before,3),
                        error_type=type(error).__name__,error=str(error)))
                save()
                print('Recorded',case['label'],flush=True)
        report['loaded_models']=requests.get(base+'/api/ps',timeout=10).json()
        report['completed']=all('result' in item for item in report['cases'])
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error));print(type(error).__name__,str(error),flush=True)
    finally:
        if job is not None:
            job.cleanup()
        if server is not None:
            _stop_process(server)
            report['server_exit_code']=server.returncode
        if server_log is not None: server_log.close()
        if (owned/'server.log').exists():
            # Diagnostics only: never retain runtime binaries, models or keys.
            with (owned/'server.log').open('rb') as stream:
                stream.seek(0,2);stream.seek(max(0,stream.tell()-100000))
                (evidence/'server-tail.log').write_bytes(stream.read())
        report['removed_bytes']=sum(path.stat().st_size for path in owned.rglob('*') if path.is_file())
        target=safe_owned(owned,marker)
        shutil.rmtree(target)
        report.update(temporary_runtime_models_removed=not owned.exists(),
            external_ollama_paths_unchanged=before_external=={str(path):path.exists() for path in external},
            saved_state_unchanged=baseline=={name:sha(ROOT/name) for name in baseline},
            elapsed_seconds=round(time.monotonic()-started,3))
        save();print('REPORT',receipt,'cleanup=',report['temporary_runtime_models_removed'],flush=True)
    return 0 if report['completed'] and report['temporary_runtime_models_removed'] and report['saved_state_unchanged'] else 1


if __name__=='__main__':
    raise SystemExit(main())
