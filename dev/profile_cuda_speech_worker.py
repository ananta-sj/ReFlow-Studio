"""Instrument the existing worker without changing decoding or package files."""
import json
from pathlib import Path
import sys
import time
from functools import wraps

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
request = json.loads(Path(sys.argv[1]).read_text())
folder = Path(request['params']['session_dir'])
from core import cuda_xtts_compat
activate = cuda_xtts_compat.activate


def instrument():
    activate()
    import torch
    from core.tts.tts_handler import TTSHandler
    initialize, generate = TTSHandler.__init__, TTSHandler.generate_audio
    def timed(name, function, stats):
        @wraps(function)
        def wrapped(*args, **kwargs):
            torch.cuda.synchronize()
            started = time.perf_counter()
            result = function(*args, **kwargs)
            torch.cuda.synchronize()
            stats.append(dict(phase=name, seconds=time.perf_counter()-started,
                              shape=list(result.shape) if hasattr(result, 'shape') else None))
            return result
        return wrapped
    def init(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        self.profile = []
        self.steps = []
        self.profile_call = 0
        model = self.tts.synthesizer.tts_model
        model.get_conditioning_latents = timed('conditioning', model.get_conditioning_latents, self.profile)
        model.gpt.generate = timed('autoregressive', model.gpt.generate, self.profile)
        model.gpt.forward = timed('latents', model.gpt.forward, self.profile)
        model.hifigan_decoder.forward = timed('vocoder', model.hifigan_decoder.forward, self.profile)
        def step(module, args, kwargs):
            value = kwargs.get('input_ids', args[0] if args else None)
            self.steps.append(dict(tokens=value.shape[-1] if value is not None else None,
                                   has_cache=kwargs.get('past_key_values') is not None))
        model.gpt.gpt_inference.register_forward_pre_hook(step, with_kwargs=True)
    def run(self, *args, **kwargs):
        self.profile.clear(); self.steps.clear()
        modes = request['params'].get('profile_modes', [])
        mode = modes[self.profile_call] if self.profile_call < len(modes) else 'baseline'
        self.profile_call += 1
        try:
            if mode == 'baseline':
                return generate(self, *args, **kwargs)
            with torch.backends.cudnn.flags(enabled=mode!='native', benchmark=False, deterministic=False):
                with torch.autocast('cuda', dtype=torch.float16, enabled=mode=='amp'):
                    return generate(self, *args, **kwargs)
        finally:
            with (folder/'timings.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(mode=mode, phases=self.profile, steps=self.steps,
                    parameters_device=str(next(self.tts.synthesizer.tts_model.parameters()).device)))+'\n')
    TTSHandler.__init__, TTSHandler.generate_audio = init, run


cuda_xtts_compat.activate = instrument
from core.cuda_worker import session
session(request['params'])
