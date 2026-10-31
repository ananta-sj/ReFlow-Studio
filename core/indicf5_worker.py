"""Dedicated IndicF5 runtime worker; no generic F5 or remote model execution."""
import gc
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for flag in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[flag] = '1'


def session(params):
    import importlib.metadata
    import numpy as np
    import soundfile as sf
    import torch
    from safetensors.torch import load_file
    from vocos import Vocos
    from f5_tts.model import DiT
    from f5_tts.infer.utils_infer import load_model, infer_batch_process
    from core.providers.tts.indicf5_local import digest, load_reference_profile
    from core.loudness import measure_loudness
    from core.render_context import run_process
    from core.indicf5_duration import sentence_hops,validate_minimum_sentence_seconds,segment_text
    if importlib.metadata.version('f5-tts') != '0.1.0':
        raise ValueError('IndicF5 requires its isolated f5-tts 0.1.0 runtime.')
    device = params['device']
    if str(device).startswith('cuda'):
        if not torch.cuda.is_available() or torch.__version__ != '2.9.1+cu128':
            raise ValueError('Verified IndicF5 CUDA execution is unavailable.')
        if Path(sys.executable).parent / 'Lib/site-packages' not in Path(torch.__file__).resolve().parents:
            raise ValueError('IndicF5 CUDA torch resolved outside its isolated runtime.')
    elif device != 'cpu' or torch.__version__ != '2.9.1+cpu':
        raise ValueError('Unsupported IndicF5 CPU runtime/device.')
    torch.set_num_threads(2)
    torch.manual_seed(1234)
    model = load_model(DiT, dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                       vocab_file=params['vocab_path'], device=device)
    vocoder = Vocos.from_hparams(str(ROOT / 'core/indicf5_vocos.yaml'))
    state = load_file(params['checkpoint_path'], device='cpu')
    model_prefix, vocoder_prefix = 'ema_model._orig_mod.', 'vocoder._orig_mod.'
    speech = {key[len(model_prefix):]: value for key, value in state.items() if key.startswith(model_prefix)}
    voice = {key[len(vocoder_prefix):]: value for key, value in state.items() if key.startswith(vocoder_prefix)}
    if len(speech) != 364 or len(voice) != 83 or len(state) != 447:
        raise ValueError('IndicF5 checkpoint tensor identities/counts differ.')
    model.load_state_dict(speech, strict=True)
    vocoder.load_state_dict(voice, strict=True)
    del state, speech, voice
    gc.collect()
    model.eval()
    vocoder.to(device).eval()
    if vocoder.head.istft.padding != 'center' or vocoder.head.istft.hop_length != 256:
        raise ValueError('Unsupported IndicF5 vocoder timing convention.')
    folder = Path(params['session_dir'])
    print(json.dumps({'engine':'indicf5','stage':'model-ready','device':device}), flush=True)
    last = 0
    def check_stop(*_):
        if (folder / 'stop').exists():
            raise RuntimeError('IndicF5 speech session stopped.')
    hook = model.transformer.register_forward_pre_hook(check_stop)
    try:
        while not (folder / 'stop').exists():
            for request_path in sorted(folder.glob('call-????????.json')):
                sequence = int(request_path.stem[5:])
                if sequence <= last:
                    continue
                response = dict(ok=False, worker_pid=os.getpid(), sequence=sequence, engine='indicf5')
                try:
                    call = json.loads(request_path.read_text(encoding='utf-8'))
                    duration_floor=validate_minimum_sentence_seconds(call.get('minimum_sentence_seconds'))
                    print(json.dumps({'engine':'indicf5','stage':'generating','sequence':sequence}), flush=True)
                    profile = load_reference_profile(call['profile']['profile_path'])
                    if profile != call['profile']:
                        raise ValueError('Reference profile changed after speech request.')
                    text = call['text'].strip()
                    if not text or len(text) > 4000 or any(c not in model.vocab_char_map for c in text+profile['reference_text']):
                        raise ValueError('Blank, excessive or unsupported IndicF5 speech/reference text.')
                    continuous=call.get('continuous_utterance',False)
                    sentences=segment_text(text,continuous)
                    samples, rate = sf.read(profile['reference_audio'], dtype='float32', always_2d=True)
                    if rate != 24000 or samples.shape[1] != 1 or not np.isfinite(samples).all() or not np.max(np.abs(samples)):
                        raise ValueError('Confirmed IndicF5 reference must be finite nonzero mono 24 kHz audio.')
                    parts, details = [], []
                    with tempfile.TemporaryDirectory(prefix='indicf5-call-', dir=folder) as work:
                        for index, sentence in enumerate(sentences):
                            check_stop()
                            hops = sentence_hops(sentence,profile,rate,duration_floor)
                            total = len(samples)//256 + hops + 1
                            if total > 4096:
                                raise ValueError('IndicF5 sentence exceeds its model limit; split or shorten the sentence.')
                            torch.manual_seed(profile['seed'])
                            started = time.monotonic()
                            wave, output_rate, _ = infer_batch_process((torch.from_numpy(samples.T.copy()), rate),
                                profile['reference_text'], [sentence], model, vocoder, device=device,
                                nfe_step=profile['steps'], cfg_strength=profile['guidance'],
                                fix_duration=(total+1e-6)*256/rate)
                            if output_rate != rate or len(wave) != hops*256 or not np.isfinite(wave).all() or not np.max(np.abs(wave)):
                                raise ValueError('Invalid IndicF5 synthesized waveform/duration.')
                            raw = Path(work) / f'{index}-raw.wav'
                            listening = Path(work) / f'{index}-listening.wav'
                            sf.write(raw, wave, rate, subtype='FLOAT')
                            level = measure_loudness(raw)
                            if not math.isfinite(level['input_tp']):
                                raise ValueError('IndicF5 speech has no finite measured true peak.')
                            gain = -1.55-level['input_tp']
                            if math.isfinite(level['input_i']):
                                gain = min(gain, -18-level['input_i'])
                            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(raw),
                                '-af', f'volume={gain}dB', '-c:a', 'pcm_s16le', str(listening)], check=True, timeout=60)
                            pcm, output_rate = sf.read(listening, dtype='int16')
                            if output_rate != rate or len(pcm) != len(wave) or pcm.ndim != 1 or not np.max(np.abs(pcm.astype('int32'))):
                                raise ValueError('IndicF5 gain-only preparation changed format or removed speech.')
                            if index:
                                parts.append(np.zeros(round(profile['sentence_gap_seconds']*rate), dtype='int16'))
                            parts.append(pcm)
                            details.append(dict(text=sentence, frames=len(pcm), gain_db=gain,
                                synthesis_seconds=round(time.monotonic()-started, 3)))
                        if digest(profile['reference_audio']) != profile['reference_sha256']:
                            raise ValueError('Confirmed IndicF5 reference changed during synthesis.')
                        joined = np.concatenate(parts)
                        sf.write(call['output_path'], joined, rate, subtype='PCM_16')
                        decoded, output_rate = sf.read(call['output_path'], dtype='int16')
                        if output_rate != rate or not np.array_equal(decoded, joined):
                            raise ValueError('IndicF5 assembly altered speech samples.')
                        run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', call['output_path'],
                                     '-f', 'null', os.devnull], check=True, timeout=60)
                    response.update(ok=True, sentences=details, seconds=len(joined)/rate,
                        reference_sha256=profile['reference_sha256'], output_sha256=digest(call['output_path']),
                        minimum_sentence_seconds=duration_floor,continuous_utterance=continuous)
                except Exception:
                    response['error'] = traceback.format_exc()[-6000:]
                pending = request_path.with_suffix('.response.tmp')
                pending.write_text(json.dumps(response, ensure_ascii=False), encoding='utf-8')
                os.replace(pending, request_path.with_suffix('.response.json'))
                last = sequence
            time.sleep(.05)
    finally:
        hook.remove()


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request['operation'] != 'indicf5_session':
        raise ValueError('Unsupported IndicF5 operation.')
    session(request['params'])
