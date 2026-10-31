"""Offline M2M100 CPU worker reusing the existing translation policy guards."""
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
    if not folder.is_relative_to((ROOT/'temp/jobs').resolve()):raise ValueError('Unsafe M2M100 workspace')
    os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                      HF_HOME=str(folder/'hf'),OMP_NUM_THREADS='2')
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
            raise RuntimeError('Offline M2M100 worker forbids networking')
    sys.addaudithook(offline)
    from core.m2m100_runtime import validate,model_contract
    route=validate();contract=model_contract(verify_weights=True)
    if Path(sys.executable).resolve()!=Path(route['executable']).resolve() or params['model_path']!=contract['model_path']:
        raise RuntimeError('M2M100 runtime/model contract mismatch')
    import torch
    from transformers import M2M100Tokenizer,M2M100ForConditionalGeneration,StoppingCriteria
    from core.llm_translator import LLMTranslator
    from core.render_context import RenderContext,bind_job
    from core import generation_control
    torch.set_num_threads(2)
    job=RenderContext(folder)
    class Stop(StoppingCriteria):
        def __call__(self,*args,**kwargs):
            (folder/'token-boundary').touch(exist_ok=True)
            if (folder/'stop').exists():job.request_stop()
            job.check();return False
        def __deepcopy__(self,memo):return self
    original=generation_control.generation_kwargs
    def controlled():
        values=original();values.setdefault('stopping_criteria',[]).append(Stop());return values
    generation_control.generation_kwargs=controlled
    translator=LLMTranslator.__new__(LLMTranslator)
    translator.mode='uninitialized';translator.device='cpu';translator.model_name='facebook/m2m100_418M'
    last=0
    try:
        translator.tokenizer=M2M100Tokenizer.from_pretrained(contract['model_path'],local_files_only=True)
        translator.model=M2M100ForConditionalGeneration.from_pretrained(contract['model_path'],
            local_files_only=True,weights_only=True).to('cpu').eval()
        translator.mode='m2m100'
        (folder/'model-ready').write_text(json.dumps(dict(worker_pid=os.getpid(),model_loads=1)))
        with bind_job(job):
            while not (folder/'stop').exists():
                for request in sorted(folder.glob('call-????????.json')):
                    sequence=int(request.stem[5:])
                    if sequence<=last:continue
                    result=dict(ok=False,worker_pid=os.getpid(),model_loads=1,sequence=sequence,model_revision=contract['revision'])
                    try:
                        call=json.loads(request.read_text(encoding='utf-8'))
                        output=translator.translate(call['text'],call['target'],source_language=call['source'])
                        result.update(ok=True,translation=output)
                    except Exception:result['error']=traceback.format_exc()[-6000:]
                    pending=request.with_suffix('.response.tmp')
                    pending.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                    os.replace(pending,request.with_suffix('.response.json'));last=sequence
                time.sleep(.05)
    finally:
        translator.release();job.cleanup()


if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request.get('operation')!='m2m100_session':raise ValueError('Unsupported M2M100 operation')
    session(request['params'])
