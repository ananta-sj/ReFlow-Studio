"""Offline CUDA inference in a job-owned process, one model family at a time."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]

def stopping_criteria_base(stage):
    if stage in ('speech','translation'):
        from transformers import StoppingCriteria
        return StoppingCriteria
    if stage in ('recognition','separate'):return object
    raise ValueError('Unknown CUDA stage')


def session(params):
    import faulthandler
    faulthandler.dump_traceback_later(120, repeat=True)
    from core.cuda_runtime import validate
    from core.render_context import RenderContext, bind_job
    from core import generation_control

    folder = Path(params['session_dir']).resolve()
    if not folder.is_relative_to((ROOT/'temp/jobs').resolve()):
        raise ValueError('Unsafe CUDA worker directory')
    stage = params['stage']
    route = validate(stage, candidate=params.get('candidate') is True)
    if Path(sys.executable).resolve() != Path(route['executable']).resolve():
        raise RuntimeError('CUDA worker started in the wrong interpreter')
    os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        OMP_NUM_THREADS='2', HF_HOME=str(folder/'hf'), TORCH_HOME=str(folder/'torch'),
        TTS_HOME=str(folder/'tts'), NUMBA_CACHE_DIR=str(folder/'numba'),
        MPLCONFIGDIR=str(folder/'matplotlib'))
    dll_handles = []
    if os.name == 'nt':
        native_paths = []
        for directory in (Path(route['profile'])/'Lib/site-packages/torch/lib',
                          ROOT/'runtime_profiles/indicf5-gpu-evaluation/Lib/site-packages/torch/lib',
                          ROOT/'ffmpeg/shared_libs'):
            if directory.is_dir():
                dll_handles.append(os.add_dll_directory(str(directory)))
                native_paths.append(str(directory))
        # CTranslate2 uses LoadLibrary rather than Python's extension loader.
        # It therefore also needs the native CUDA directories on PATH.
        os.environ['PATH'] = os.pathsep.join(native_paths+[os.environ.get('PATH', '')])
    def offline(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('CUDA model workers run offline')
    sys.addaudithook(offline)
    import torch
    print('CUDA worker: PyTorch loaded', flush=True)
    StoppingCriteria=stopping_criteria_base(stage)
    if stage in ('speech','translation'):
        print('CUDA worker: Transformers loaded', flush=True)
    if torch.__version__ != '2.14.1+cu130' or not torch.cuda.is_available():
        raise RuntimeError('The selected CUDA engine could not use the NVIDIA GPU')
    torch.set_num_threads(2)
    free, _ = torch.cuda.mem_get_info(0)
    needed = 3072 if stage == 'translation' else 2048
    if free < needed*1024**2:
        raise RuntimeError(f'RTX has {free//1024**2} MB free; {stage} needs at least {needed} MB. '
                           'Close other GPU applications and Retry.')
    job = RenderContext(folder)
    original = generation_control.generation_kwargs
    class Stop(StoppingCriteria):
        def __call__(self, *args, **kwargs):
            if (folder/'stop').exists():
                job.request_stop()
            job.check()
            return False
        def __deepcopy__(self, memo):
            return self
    def controlled():
        values = original()
        values.setdefault('stopping_criteria', []).append(Stop())
        return values
    generation_control.generation_kwargs = controlled
    model = None
    try:
        if stage == 'speech':
            from core.cuda_xtts_compat import activate
            activate()
            from core.tts.tts_handler import TTSHandler
            model = TTSHandler(device='cuda:0', model_path=params['model_path'])
            if not model.use_gpu or next(model.tts.synthesizer.tts_model.parameters()).device.type != 'cuda':
                raise RuntimeError('XTTS did not load onto the selected GPU')
        elif stage == 'translation':
            from core.providers.translation.nllb_local import NLLBLocalProvider
            model = NLLBLocalProvider(params['model_path'], device='cuda:0')
            model._ensure_loaded()
            if next(model._model.parameters()).device.type != 'cuda':
                raise RuntimeError('NLLB did not load onto the selected GPU')
        elif stage == 'recognition':
            from core.recognition_compat import apply
            apply()
            from faster_whisper import WhisperModel
            from core.stt.stt_handler import STTHandler
            model = STTHandler.__new__(STTHandler)
            model.device, model.compute_type, model.model_size = 'cuda', 'float16', params['model_path']
            model.model = WhisperModel(params['model_path'], device='cuda', compute_type='float16',
                local_files_only=True, download_root=str(ROOT/'models/whisper/cache'))
            if model.model.model.device != 'cuda':
                raise RuntimeError('Whisper did not load onto the selected GPU')
        (folder/'model-ready').write_text(json.dumps(dict(stage=stage, device='cuda:0',
            gpu=torch.cuda.get_device_name(0))), encoding='utf-8')
        faulthandler.cancel_dump_traceback_later()
        last = 0
        with bind_job(job):
            while not (folder/'stop').exists():
                for request in sorted(folder.glob('call-????????.json')):
                    number = int(request.stem[5:])
                    if number <= last:
                        continue
                    result = dict(ok=False, worker_pid=os.getpid(), device='cuda:0', stage=stage,
                                  gpu_name=torch.cuda.get_device_name(0))
                    try:
                        from core.worker_json import read_json
                        call = read_json(request,job.check)
                        torch.cuda.reset_peak_memory_stats()
                        if stage == 'speech':
                            output = Path(call['output_path']).resolve()
                            if not output.is_relative_to(folder.parent) or output.suffix.lower() != '.wav':
                                raise ValueError('Unsafe GPU speech output')
                            model.generate_audio(call['text'], str(output), call['language'],
                                call['reference_audio'], alternate_take=call.get('alternate_take') is True,
                                max_seconds=call.get('max_seconds'))
                            result['output_path'] = str(output)
                        elif stage == 'translation':
                            result['translation'] = model.translate(call['text'], call['target'],
                                                                    source_language=call['source'])
                        elif stage == 'recognition':
                            result['transcriptions'] = [model._transcribe(path, call['source_language'],
                                vad_filter=not call.get('takes', False)).to_payload() for path in call['audio_paths']]
                        else:
                            result.update(separate(call, params['model_path'], folder.parent, torch))
                        result.update(ok=True, peak_gpu_mb=round(torch.cuda.max_memory_allocated()/1024**2, 1)
                                      if stage != 'recognition' else None)
                        if stage == 'recognition':
                            result['backend_device'] = model.model.model.device
                    except Exception as error:
                        from core.speech_generation_budget import SpeechGenerationLimitExceeded
                        if isinstance(error,SpeechGenerationLimitExceeded):
                            result.update(ok=True,speech_limit=str(error))
                        else:
                            result['error'] = traceback.format_exc()[-6000:]
                    pending = request.with_suffix('.response.tmp')
                    pending.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
                    from core.worker_json import replace
                    replace(pending,request.with_suffix('.response.json'),job.check)
                    last = number
                time.sleep(.05)
    finally:
        generation_control.generation_kwargs = original
        model = None
        job.cleanup()


def separate(call, repository, workspace, torch):
    import random
    from fractions import Fraction
    import numpy as np
    from demucs.htdemucs import HTDemucs
    from demucs.separate import main
    from core.audio_separator import DEMUCS_SHA256
    from core.runtime_integrity import sha
    repository = Path(repository)
    if sha(repository/'955717e8-8726e21a.th') != DEMUCS_SHA256:
        raise ValueError('Separation weights changed')
    config = repository/'htdemucs.yaml'
    expected = "models: ['955717e8']\n"
    if not config.exists():
        config.write_text(expected, encoding='utf-8')
    elif config.read_text(encoding='utf-8').strip() != expected.strip():
        raise ValueError('Separation model recipe changed')
    output = Path(call['output_path']).resolve()
    if not output.is_relative_to(workspace) or output == workspace:
        raise ValueError('Unsafe separation output')
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '1'
    allowed = [HTDemucs, Fraction, np.dtype, type(np.dtype(np.float64)),
               type(np.dtype(np.float32)), (np.core.multiarray.scalar, 'numpy.core.multiarray.scalar')]
    with torch.serialization.safe_globals(allowed):
        main(['--two-stems=vocals', '-n', 'htdemucs', '--repo', str(repository),
              '--device', 'cuda:0', '--out', str(output), call['audio_path']])
    target = output/'htdemucs'/Path(call['audio_path']).stem
    return dict(vocals=str(target/'vocals.wav'), background=str(target/'no_vocals.wav'))


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request.get('operation') != 'cuda_session':
        raise ValueError('Invalid CUDA operation')
    session(request['params'])
