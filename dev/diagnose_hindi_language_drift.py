"""One greedy-generation control for reported foreign speech in a Hindi raw take."""
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
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.loudness import measure_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    coverage = json.loads((ROOT / 'docs/validation/2026-10-04-hindi-coverage.json').read_text(encoding='utf-8'))
    case = next(row for row in coverage['cases'] if row['voice'] == 'abhishek' and row['label'] == 'negation')
    source = Path(coverage['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    reference = source / 'abhishek-reference.wav'
    original_raw = source / case['raw_file']
    if digest(reference) != case['reference_sha256'] or digest(original_raw) != case['raw_sha256']:
        raise ValueError('Original retained source changed')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-greedy-' + uuid.uuid4().hex[:8])
    report = dict(offline=True, production_changed=False, language_quality_accepted=False,
                  mechanical_checks_pass=False, language='hi', text=case['text'], seed=1234,
                  do_sample=False, num_beams=1, temperature_call_argument=.90,
                  temperature_active=False, reference_sha256=digest(reference),
                  rejected_raw_sha256=digest(original_raw), rejected_raw_seconds=case['raw_seconds'])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            shutil.copy2(reference, work / 'reference.wav')
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            tokenizer = engine.tts.synthesizer.tts_model.tokenizer
            tokens = tokenizer.encode(case['text'], 'hi')
            unknown = tokenizer.tokenizer.token_to_id('[UNK]')
            report.update(token_count=len(tokens), unknown_tokens=tokens.count(unknown),
                          token_roundtrip=tokenizer.decode(tokens),
                          first_token=tokenizer.tokenizer.id_to_token(tokens[0]),
                          writer_rate=engine.tts.synthesizer.output_sample_rate)
            random.seed(1234)
            np.random.seed(1234)
            torch.manual_seed(1234)
            raw = work / 'greedy-raw.wav'
            before = time.monotonic()
            engine.tts.tts_to_file(text=case['text'], file_path=str(raw), speaker_wav=str(reference),
                language='hi', split_sentences=True, temperature=.90, speed=1.0,
                do_sample=False, num_beams=1, **generation_kwargs())
            report['synthesis_seconds'] = round(time.monotonic()-before, 3)
            audio = load_speech_audio(raw)
            if audio.frame_rate != 24000 or audio.channels != 1:
                raise RuntimeError('Expected native mono output')
            measured = measure_loudness(raw)
            if not all(math.isfinite(measured[key]) for key in ('input_i', 'input_tp')):
                raise RuntimeError('Cannot measure generated waveform')
            gain = min(-18.0-measured['input_i'], -1.55-measured['input_tp'])
            listening = work / 'greedy-listening.wav'
            audio.apply_gain(gain).export(listening, format='wav').close()
            final_level = measure_loudness(listening)
            if len(load_speech_audio(listening)) != len(audio) or final_level['input_tp'] > -1.2:
                raise RuntimeError('Listening control changed timing or exceeded peak tolerance')
            for path in (raw, listening):
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                            check=True, timeout=60)
            if digest(reference) != report['reference_sha256'] or digest(original_raw) != report['rejected_raw_sha256']:
                raise RuntimeError('Retained original changed')
            report.update(raw_seconds=len(audio)/1000, raw_sha256=digest(raw), listening_gain_db=gain,
                          final_loudness=final_level, mechanical_checks_pass=True)
            job.publish(work, destination)
            report['directory'] = str(destination)
            print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-hindi-greedy.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
