"""Greedy raw-speech coverage on the two remaining rejected passages per voice."""
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
    from pydub import AudioSegment
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.loudness import measure_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-hindi-coverage.json').read_text(encoding='utf-8'))
    source = Path(prior['directory']).resolve()
    if not source.is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-greedy-coverage-' + uuid.uuid4().hex[:8])
    report = dict(mechanical_checks_pass=False, human_quality_accepted=False, production_changed=False,
        offline=True, device='cpu', do_sample=False, num_beams=1, seed=1234, temperature_active=False,
        temperature_call_argument=.90, tempo_processing=False, normalization=False, cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            tokenizer = engine.tts.synthesizer.tts_model.tokenizer
            for voice in ('sujata', 'abhishek'):
                montage = None
                reference = source / (voice + '-reference.wav')
                for label in ('question', 'time-and-pause'):
                    case = next(row for row in prior['cases'] if row['voice'] == voice and row['label'] == label)
                    if digest(reference) != case['reference_sha256']:
                        raise ValueError('Retained reference changed')
                    tokens = tokenizer.encode(case['text'], 'hi')
                    row = dict(voice=voice, label=label, text=case['text'], reference_sha256=digest(reference),
                        first_token=tokenizer.tokenizer.id_to_token(tokens[0]), token_roundtrip=tokenizer.decode(tokens),
                        unknown_tokens=tokens.count(tokenizer.tokenizer.token_to_id('[UNK]')),
                        previous_sampled_raw_seconds=case['raw_seconds'])
                    random.seed(1234)
                    np.random.seed(1234)
                    torch.manual_seed(1234)
                    raw = work / f'{voice}-{label}-raw.wav'
                    before = time.monotonic()
                    engine.tts.tts_to_file(text=case['text'], file_path=str(raw), speaker_wav=str(reference),
                        language='hi', split_sentences=True, temperature=.90, speed=1.0,
                        do_sample=False, num_beams=1, **generation_kwargs())
                    row['synthesis_seconds'] = round(time.monotonic()-before, 3)
                    audio = load_speech_audio(raw)
                    if audio.frame_rate != 24000 or audio.channels != 1:
                        raise RuntimeError('Unexpected decoder output format')
                    level = measure_loudness(raw)
                    if not all(math.isfinite(level[key]) for key in ('input_i', 'input_tp')):
                        raise RuntimeError('Cannot measure generated waveform')
                    gain = min(-18.0-level['input_i'], -1.55-level['input_tp'])
                    listening = work / f'{voice}-{label}.wav'
                    audio.apply_gain(gain).export(listening, format='wav').close()
                    final = load_speech_audio(listening)
                    final_level = measure_loudness(listening)
                    if len(final) != len(audio) or final_level['input_tp'] > -1.2:
                        raise RuntimeError('Listening control altered timing or exceeded peak tolerance')
                    for path in (raw, listening):
                        run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                                    check=True, timeout=60)
                    row.update(seconds=len(audio)/1000, raw_sha256=digest(raw), file=listening.name,
                               sha256=digest(listening), gain_db=gain, loudness=final_level)
                    report['cases'].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                    if montage is None:
                        montage = final
                    else:
                        gap = AudioSegment.silent(duration=900, frame_rate=24000).set_sample_width(2).set_channels(1)
                        montage += gap + final
                shutil.copy2(reference, work / (voice + '-reference.wav'))
                review = work / (voice + '-review.wav')
                montage.export(review, format='wav').close()
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(review), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                if digest(reference) != case['reference_sha256']:
                    raise RuntimeError('Original reference changed')
            report['mechanical_checks_pass'] = True
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
