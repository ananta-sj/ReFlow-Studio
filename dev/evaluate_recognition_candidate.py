"""Actual offline recognition runtime and desktop-to-worker acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
CODE = r'''
import hashlib,importlib,importlib.metadata as metadata,importlib.util,json,os,re,sys,time,threading
from pathlib import Path
root,scratch,phase=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',OMP_NUM_THREADS='4')
os.environ.update(TEMP=str(scratch),TMP=str(scratch),HF_HOME=str(scratch/'hf-cache'))
import socket
def denied(*args,**kwargs):raise RuntimeError('Recognition acceptance blocks network access')
class OfflineSocket(socket.socket):connect=connect_ex=bind=sendto=denied
socket.socket=OfflineSocket;socket.getaddrinfo=socket.create_connection=denied
model=root/'models/whisper/ct2-turbo-candidate-compat/model'
audio=root/'docs/validation/2026-10-14-desktop-candidate-speech.wav'
report=dict(passed=False,phase=phase,checks={},model_downloaded=False)
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
def normalized(text):return re.findall(r'\w+',text.casefold())
def words(result):return ' '.join(row['text'].strip() for row in result)
try:
    if phase.startswith('native'):
        from packaging.utils import canonicalize_name
        lock=json.loads((root/'docs/validation/2026-10-15-recognition-candidate-lock-review.json').read_text())
        installed={}
        for dist in metadata.distributions():
            name=canonicalize_name(dist.metadata['Name'])
            check('unique_'+name,name not in installed);installed[name]=dist.version
        check('exact_package_closure',installed=={row['name']:row['version'] for row in lock['packages']})
        check('no_torch_or_transformers',importlib.util.find_spec('torch') is None and importlib.util.find_spec('transformers') is None)
        for name in ['faster_whisper','ctranslate2','av','onnxruntime','numpy','tokenizers']:
            module=importlib.import_module(name)
            check('native_origin_'+name,Path(module.__file__).resolve().is_relative_to(root/'runtime_profiles/recognition-candidate'))
        from stt.stt_handler import STTHandler
        result=STTHandler(model_size=str(model)).transcribe(str(audio))
        report['transcript']=result.to_payload()
        check('english_words_exact',normalized(words(result))==normalized('Good morning. This is the portable speech test.'))
        check('language_english',result.language=='en' and result.language_probability>.8)
        check('time_bounds',all(0<=row['start']<row['end']<=15 for row in result))
        # VAD must return no invented speech for a real silent WAV.
        import wave
        silence=scratch/'silence.wav'
        with wave.open(str(silence),'wb') as output:
            output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(b'\x00\x00'*16000*3)
        empty=STTHandler(model_size=str(model)).transcribe(str(silence))
        check('silence_no_hallucinated_cues',len(empty)==0)
        if phase=='native-media':
            import struct
            from faster_whisper.audio import decode_audio
            payload=bytearray(audio.read_bytes())
            info=b'INFO'+b'INAM'+struct.pack('<I',4)+bytes([255,254,0,0])
            payload.extend(b'LIST'+struct.pack('<I',len(info))+info)
            struct.pack_into('<I',payload,4,len(payload)-8)
            tagged=scratch/'invalid-metadata.wav';tagged.write_bytes(payload)
            import numpy as np
            check('invalid_metadata_audio_preserved',np.array_equal(decode_audio(str(audio)),decode_audio(str(tagged))))
            corrupt=scratch/'corrupt.wav';corrupt.write_bytes(b'not a media file')
            try:decode_audio(str(corrupt))
            except Exception:check('corrupt_media_rejected',True)
            else:check('corrupt_media_rejected',False)
        if phase in {'native-hindi','native-hindi-hinted'}:
            profile_path=root/'models/indicf5/references/abhishek/profile.json'
            reference=json.loads(profile_path.read_text(encoding='utf-8'))
            reference_audio=profile_path.parent/reference['reference_audio']
            check('hindi_reference_hash',hashlib.sha256(reference_audio.read_bytes()).hexdigest()==reference['reference_sha256'])
            if phase=='native-hindi-hinted':
                from faster_whisper import WhisperModel
                hinted=WhisperModel(str(model),device='cpu',compute_type='int8',local_files_only=True)
                segments,info=hinted.transcribe(str(reference_audio),language='hi',beam_size=5,vad_filter=True)
                from core.transcription import TranscriptionResult
                hindi=TranscriptionResult([dict(start=s.start,end=s.end,text=s.text) for s in segments],info.language,info.language_probability)
            else:
                hindi=STTHandler(model_size=str(model)).transcribe(str(reference_audio))
            report['hindi_transcript']=hindi.to_payload()
            report['hindi_reference_text']=reference['reference_text']
            check('hindi_detected',hindi.language=='hi' and hindi.language_probability>.8)
            check('hindi_nonempty',len(hindi)>0 and bool(words(hindi).strip()))
            import unicodedata
            def tokens(text):
                text=unicodedata.normalize('NFC',text).casefold()
                return ''.join(' ' if unicodedata.category(c).startswith('P') else c for c in text).split()
            expected,actual=tokens(reference['reference_text']),tokens(words(hindi))
            previous=list(range(len(actual)+1))
            for i,a in enumerate(expected,1):
                current=[i]
                for j,b in enumerate(actual,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(a!=b)))
                previous=current
            report['hindi_word_error_rate']=previous[-1]/max(1,len(expected))
            report['hindi_accuracy_is_diagnostic_not_release_gate']=True
    else:
        os.environ['REFLOW_WORKER_PYTHON']=str(root/'runtime_profiles/recognition-candidate/python.exe')
        from core.providers.stt.whisper_local import WhisperLocalProvider
        from core.render_context import RenderContext,bind_job,RenderCancelled
        provider=WhisperLocalProvider(str(model));job=RenderContext(scratch)
        try:
            with bind_job(job):result=provider.transcribe(str(audio))
            check('real_provider_words',normalized(words(result))==normalized('Good morning. This is the portable speech test.'))
            check('worker_metadata_survives_json',result.language=='en' and result.language_probability>.8)
            check('worker_unregistered_after_success',not job.processes)
            try:
                with bind_job(job):provider.transcribe(str(scratch/'missing.wav'))
            except RuntimeError as error:check('missing_media_surfaces_worker_error','Transcription worker failed' in str(error))
            else:check('missing_media_surfaces_worker_error',False)
            outcomes=[]
            def run():
                try:
                    with bind_job(job):provider.transcribe(str(audio))
                except RenderCancelled:outcomes.append('cancelled')
                except BaseException as error:outcomes.append(repr(error))
                else:outcomes.append('unexpected_success')
            thread=threading.Thread(target=run);thread.start();deadline=time.monotonic()+30;children=[]
            while thread.is_alive() and time.monotonic()<deadline:
                with job.lock:children=list(job.processes)
                if children:break
                time.sleep(.02)
            check('owned_worker_observed',bool(children))
            started=time.monotonic();job.request_stop();thread.join(30)
            report['cancel_seconds']=round(time.monotonic()-started,3)
            check('worker_cancelled',not thread.is_alive() and outcomes==['cancelled'])
            check('owned_worker_exited',all(child.poll() is not None for child in children))
        finally:
            job.cleanup();check('job_workspace_removed',not job.workspace.exists())
        check('desktop_parent_without_torch',importlib.util.find_spec('torch') is None)
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (root/f'docs/validation/2026-10-15-recognition-candidate-{phase}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
raise SystemExit(not report['passed'])
'''


def main():
    phase = sys.argv[1]
    assert phase in {'native', 'native-compat', 'native-media', 'native-hindi', 'native-hindi-hinted', 'provider'}
    profile = 'recognition-candidate' if phase.startswith('native') else 'desktop-candidate'
    with tempfile.TemporaryDirectory(prefix='recognition-acceptance-', dir=ROOT / 'temp') as scratch:
        with (OUT / f'2026-10-15-recognition-candidate-{phase}.log').open('wb') as log:
            result = subprocess.run([str(ROOT / 'runtime_profiles' / profile / 'python.exe'), '-B', '-X', 'utf8', '-c',
                                     CODE, str(ROOT), scratch, phase], stdout=log, stderr=subprocess.STDOUT,
                                    timeout=360, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print(phase, 'exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
