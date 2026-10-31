"""Local trained IndicF5 CPU smoke, documented prompt, no production integration."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'runtime_profiles/indicf5-evaluation'
sys.path.insert(0, str(ROOT))
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['WANDB_MODE'] = 'disabled'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MPLCONFIGDIR'] = str(ROOT / 'temp/indicf5-matplotlib')


def main():
    if Path(sys.executable).resolve().parent != PROFILE.resolve():
        raise ValueError('Use isolated evaluation Python')
    import torch
    import numpy as np
    import soundfile as sf
    from safetensors.torch import load_file
    from vocos import Vocos
    from f5_tts.model import DiT
    from f5_tts.infer.utils_infer import load_model, infer_batch_process
    from core.loudness import measure_loudness
    from core.render_context import RenderContext, bind_job, run_process
    assets = ROOT / 'models/indicf5/evaluation/assets'
    checkpoint = assets / 'model.safetensors'
    if checkpoint.stat().st_size != 1402789408:
        raise ValueError('Checkpoint size differs from pinned official metadata')
    reference = assets / 'prompts/PAN_F_HAPPY_00001.wav'
    reference_text = 'ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ  ਹਨ।'
    text = 'मेरे पास यह रिपोर्ट है।'
    config = next((ROOT / 'models/f5/cache/models--charactr--vocos-mel-24khz/snapshots').glob('*/config.yaml'))
    report = dict(human_quality_accepted=False, production_changed=False, offline=True, device='cpu',
                  reference_kind='official documented Punjabi female prompt, not Sujata or Abhishek',
                  reference_text=reference_text, text=text, native_generation_speed=1.0, nfe_step=32,
                  compiled_model_used=False, trained_weights_strictly_loaded=False)
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-06-indicf5-smoke-' + uuid.uuid4().hex[:8])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            torch.set_num_threads(2)
            torch.manual_seed(1234)
            report['diagnostic_noise_seed'] = 1234
            model = load_model(DiT, dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                               vocab_file=str(assets / 'checkpoints/vocab.txt'), device='cpu')
            vocoder = Vocos.from_hparams(str(config))
            state = load_file(str(checkpoint), device='cpu')
            prefixes = {'model': 'ema_model._orig_mod.', 'vocoder': 'vocoder._orig_mod.'}
            model_state = {key[len(prefixes['model']):]: value for key, value in state.items() if key.startswith(prefixes['model'])}
            vocoder_state = {key[len(prefixes['vocoder']):]: value for key, value in state.items() if key.startswith(prefixes['vocoder'])}
            if len(model_state) + len(vocoder_state) != len(state) or not model_state or not vocoder_state:
                raise ValueError('Unknown or empty checkpoint tensor namespaces')
            model.load_state_dict(model_state, strict=True)
            vocoder.load_state_dict(vocoder_state, strict=True)
            report.update(trained_weights_strictly_loaded=True, model_tensors=len(model_state),
                          vocoder_tensors=len(vocoder_state))
            del state, model_state, vocoder_state
            model.eval()
            vocoder.eval()
            print(json.dumps({'stage': 'trained-weights-loaded', **{k: report[k] for k in ('model_tensors', 'vocoder_tensors')}}), flush=True)
            unknown = sorted(set(char for char in text if char not in model.vocab_char_map))
            report['target_characters_outside_vocab'] = unknown
            if unknown:
                raise ValueError('Target Hindi characters absent from IndicF5 vocabulary')
            audio, rate = sf.read(reference, dtype='float32', always_2d=True)
            report['reference_seconds'] = len(audio)/rate
            calls = 0
            def progress(module, args):
                nonlocal calls
                job.check()
                calls += 1
                if calls % 8 == 0:
                    print(json.dumps({'diffusion_forward_calls': calls}), flush=True)
            hook = model.transformer.register_forward_pre_hook(progress)
            before = time.monotonic()
            try:
                wave, output_rate, _ = infer_batch_process((torch.from_numpy(audio.T.copy()), rate), reference_text,
                    [text], model, vocoder, device='cpu', nfe_step=32, speed=1.0)
            finally:
                hook.remove()
            if output_rate != 24000 or not np.isfinite(wave).all() or np.max(np.abs(wave)) == 0:
                raise ValueError('Invalid generated waveform')
            raw = work / 'indicf5-raw.wav'
            sf.write(raw, wave, output_rate, subtype='FLOAT')
            level = measure_loudness(raw)
            gain = min(-18.0-level['input_i'], -1.55-level['input_tp'])
            listening = work / 'indicf5-listening.wav'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(raw), '-af', f'volume={gain}dB',
                         '-c:a', 'pcm_s16le', str(listening)], check=True, timeout=60)
            for path in (raw, listening):
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull], check=True, timeout=60)
            if sf.info(raw).frames != sf.info(listening).frames:
                raise ValueError('Gain-only listening copy changed duration')
            report.update(seconds=len(wave)/output_rate, synthesis_seconds=round(time.monotonic()-before, 3),
                          listening_gain_db=gain, listening_loudness=measure_loudness(listening), full_decode_pass=True)
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        receipt = ROOT / 'docs/validation' / ('2026-10-06-indicf5-smoke-' + uuid.uuid4().hex[:8] + '.json')
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
