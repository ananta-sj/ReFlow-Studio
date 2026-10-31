"""Offline, stage-owned NLLB CPU session with decoder cancellation checks."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def session(params):
    folder = Path(params['session_dir']).resolve()
    if not folder.is_relative_to((ROOT/'temp/jobs').resolve()):
        raise ValueError('Unsafe NLLB session directory')
    os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      OMP_NUM_THREADS='2', HF_HOME=str(folder/'hf'))
    def offline(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('NLLB worker forbids network operations')
    sys.addaudithook(offline)
    from core.nllb_runtime import validate
    route = validate()
    if Path(sys.executable).resolve() != Path(route['executable']).resolve():
        raise RuntimeError('NLLB worker started in the wrong runtime')
    import torch
    from transformers import StoppingCriteria
    from core.providers.translation.nllb_local import NLLBLocalProvider
    from core import generation_control
    from core.render_context import RenderContext, bind_job
    torch.set_num_threads(2)
    job = RenderContext(folder)
    class Stop(StoppingCriteria):
        def __call__(self, *args, **kwargs):
            (folder/'token-boundary').touch(exist_ok=True)
            if (folder/'stop').exists():
                job.request_stop()
            job.check()
            return False
        def __deepcopy__(self, memo):
            return self
    original = generation_control.generation_kwargs
    def controlled():
        result = original()
        result.setdefault('stopping_criteria', []).append(Stop())
        return result
    generation_control.generation_kwargs = controlled
    provider = NLLBLocalProvider(params['model_path'], device='cpu')
    last = 0
    try:
        provider._ensure_loaded()
        (folder/'model-ready').write_text(json.dumps(dict(worker_pid=os.getpid(), model_loads=1)))
        with bind_job(job):
            while not (folder/'stop').exists():
                for request in sorted(folder.glob('call-????????.json')):
                    sequence = int(request.stem[5:])
                    if sequence <= last:
                        continue
                    response = dict(ok=False, worker_pid=os.getpid(), model_loads=1, sequence=sequence)
                    try:
                        call = json.loads(request.read_text(encoding='utf-8'))
                        translated = provider.translate(call['text'], call['target'], source_language=call['source'])
                        response.update(ok=True, translation=translated)
                    except Exception:
                        response['error'] = traceback.format_exc()[-6000:]
                    pending = request.with_suffix('.response.tmp')
                    pending.write_text(json.dumps(response, ensure_ascii=False), encoding='utf-8')
                    os.replace(pending, request.with_suffix('.response.json'))
                    last = sequence
                time.sleep(.05)
    finally:
        provider.release()
        job.cleanup()


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request.get('operation') != 'nllb_session':
        raise ValueError('Unsupported NLLB operation')
    session(request['params'])
