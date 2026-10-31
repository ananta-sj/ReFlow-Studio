"""Isolated XTTS worker using Reflow's existing persistent session protocol.

Keeps model lifetime and all caches
inside a job owned by the caller; remote/model downloads are forbidden.
"""
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'core')]

def session(params):
    folder=Path(params['session_dir']).resolve()
    if not folder.is_relative_to((ROOT/'temp').resolve()):raise ValueError('Unsafe XTTS session directory')
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',REFLOW_OFFLINE='1',OMP_NUM_THREADS='2',
        HF_HOME=str(folder/'hf'),TORCH_HOME=str(folder/'torch'),TTS_HOME=str(folder/'tts'),
        NUMBA_CACHE_DIR=str(folder/'numba'),MPLCONFIGDIR=str(folder/'matplotlib'))
    def deny_network(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
            raise RuntimeError('Offline XTTS candidate worker forbids network operations')
    sys.addaudithook(deny_network)
    from core.render_context import RenderContext,RenderCancelled,bind_job
    import torch
    from transformers import StoppingCriteria
    if Path(sys.executable).resolve().parent.name=='xtts-security-candidate':
        from core.xtts_compat import activate
        activate()
    from core.tts.tts_handler import TTSHandler
    from core import generation_control
    torch.set_num_threads(2)
    job=RenderContext(folder)
    original=generation_control.generation_kwargs
    class Stop(StoppingCriteria):
        def __call__(self,*args,**kwargs):
            (folder/'token-boundary').touch(exist_ok=True)
            if (folder/'stop').exists():job.request_stop()
            job.check()
            return False
        def __deepcopy__(self,memo):return self
    def controlled_generation():
        values=original();values.setdefault('stopping_criteria',[]).append(Stop())
        return values
    generation_control.generation_kwargs=controlled_generation
    model=None;last=0
    try:
        model=TTSHandler(device='cpu',model_path=params['model_path'])
        (folder/'model-ready').write_text(json.dumps(dict(worker_pid=os.getpid(),model_loads=1)),encoding='utf-8')
        while not (folder/'stop').exists():
            for request in sorted(folder.glob('call-????????.json')):
                number=int(request.stem[5:])
                if number<=last:continue
                response=dict(ok=False,worker_pid=os.getpid(),model_loads=1,sequence=number)
                try:
                    call=json.loads(request.read_text(encoding='utf-8'))
                    text=call['text'];output=Path(call['output_path']).resolve()
                    if not isinstance(text,str) or not 0<len(text)<=4000:raise ValueError('Invalid XTTS speech text')
                    if not output.is_relative_to(folder.parent) or output.suffix.lower()!='.wav':raise ValueError('Unsafe XTTS output destination')
                    (folder/'token-boundary').unlink(missing_ok=True)
                    with bind_job(job):model.generate_audio(text,str(output),call['language'],call['reference_audio'])
                    response.update(ok=True,output_path=str(output),model_identity=id(model.tts.synthesizer.tts_model))
                except RenderCancelled:
                    response.update(error='XTTS candidate speech cancelled',cancelled=True)
                except Exception:
                    response['error']=traceback.format_exc()[-6000:]
                pending=request.with_suffix('.response.tmp')
                pending.write_text(json.dumps(response,allow_nan=False),encoding='utf-8')
                os.replace(pending,request.with_suffix('.response.json'))
                last=number
            time.sleep(.05)
    finally:
        generation_control.generation_kwargs=original
        job.cleanup()
        model=None

def main():
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request['operation']!='xtts_session':raise ValueError('Unsupported evaluation operation')
    session(request['params'])

if __name__=='__main__':main()
