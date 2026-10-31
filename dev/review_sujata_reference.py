"""Fixed-sampling Sujata reference-preparation control; no production changes."""
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'


def main():
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.loudness import measure_loudness, normalize_voice_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    playback = json.loads((ROOT / 'docs/validation/2026-10-04-native-playback.json').read_text(encoding='utf-8'))
    source = Path(prior['review_directory']).resolve()
    old = Path(playback['directory']).resolve() / 'sujata-native.wav'
    for path in (source, old):
        if not path.is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Diagnostic source outside validation storage')
    reference = source / 'sujata-reference.wav'
    if digest(reference) != prior['references'][0]['reference_sha256']:
        raise ValueError('Retained reference changed')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-sujata-reference-' + uuid.uuid4().hex[:8])
    report = dict(offline=True, production_changed=False, human_quality_accepted=False,
                  distortion_cause_established=False, seed=1234, temperature=.90, tempo=1.342,
                  text=prior['text'], reference_sha256=digest(reference), baseline_sha256=digest(old))
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            clean = work / 'clean-reference.wav'
            AudioEngineer().clean_reference_audio(str(reference), str(clean))
            report.update(original_reference_seconds=len(load_speech_audio(reference))/1000,
                          clean_reference_seconds=len(load_speech_audio(clean))/1000,
                          clean_reference_sha256=digest(clean))
            shutil.copy2(old, work / 'earlier.wav')
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['writer_rate'] = engine.tts.synthesizer.output_sample_rate
            random.seed(1234)
            np.random.seed(1234)
            torch.manual_seed(1234)
            raw = work / 'candidate-raw.wav'
            before = time.monotonic()
            engine.tts.tts_to_file(text=report['text'], file_path=str(raw), speaker_wav=str(clean),
                language='hi', split_sentences=True, temperature=.90, speed=1.0, **generation_kwargs())
            report['synthesis_seconds'] = round(time.monotonic()-before, 3)
            audio = load_speech_audio(raw)
            samples = np.array(audio.get_array_of_samples(), dtype=np.int32)
            clipped = np.flatnonzero((samples >= 32767) | (samples <= -32768))
            report.update(raw_seconds=len(audio)/1000, raw_sha256=digest(raw),
                full_scale_samples=int(len(clipped)),
                first_full_scale_second=float(clipped[0]/audio.frame_rate) if len(clipped) else None)
            normalized = work / 'candidate-normalized.wav'
            shutil.copy2(raw, normalized)
            report['normalization'] = normalize_voice_loudness(normalized)
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            final = work / 'candidate.wav'
            pipeline.speed_change(load_speech_audio(normalized), 1.342).export(final, format='wav').close()
            before = measure_loudness(final)
            target = measure_loudness(old)
            if not all(math.isfinite(before[key]) for key in ('input_i', 'input_tp')):
                raise RuntimeError('Nonfinite candidate measurements')
            gain = min(target['input_i']-before['input_i'], -1.55-before['input_tp'])
            load_speech_audio(final).apply_gain(gain).export(final, format='wav').close()
            report.update(final_seconds=len(load_speech_audio(final))/1000,
                          final_loudness=measure_loudness(final), baseline_loudness=target, gain_db=gain)
            for path in (raw, normalized, final, clean):
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                            check=True, timeout=60)
            if abs(len(load_speech_audio(final))-len(audio)/1.342) > 100:
                raise RuntimeError('Candidate timeline changed unexpectedly')
            if report['final_loudness']['input_tp'] > -1.2:
                raise RuntimeError('Candidate true peak exceeds tolerance')
            if digest(reference) != report['reference_sha256'] or digest(old) != report['baseline_sha256']:
                raise RuntimeError('Retained original changed')
            job.publish(work, destination)
            report['directory'] = str(destination)
            print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-sujata-reference.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
