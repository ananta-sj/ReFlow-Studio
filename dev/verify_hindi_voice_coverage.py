"""Varied-text listening gate for accepted diagnostic Hindi voice profiles."""
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

PASSAGES = (
    ('question', 'क्या आप मेरी आवाज़ साफ़ सुन पा रहे हैं?'),
    ('negation', 'यह रिपोर्ट अभी पूरी नहीं हुई है।'),
    ('time-and-pause', 'कल सुबह दस बजे बैठक शुरू होगी, इसलिए कृपया समय पर पहुँचें।'),
)


def main():
    import numpy as np
    import torch
    from pydub import AudioSegment
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.generation_control import generation_kwargs
    from core.loudness import measure_loudness, normalize_voice_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    sujata = json.loads((ROOT / 'docs/validation/2026-10-04-sujata-reference.json').read_text(encoding='utf-8'))
    native = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    profiles = (
        ('sujata', Path(sujata['directory']) / 'clean-reference.wav', sujata['clean_reference_sha256']),
        ('abhishek', Path(native['review_directory']) / 'abhishek-reference.wav', native['references'][1]['reference_sha256']),
    )
    for name, reference, expected in profiles:
        if not reference.resolve().is_relative_to((ROOT / 'docs/validation').resolve()) or digest(reference) != expected:
            raise ValueError('Retained reference changed or outside validation storage: ' + name)
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-hindi-coverage-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, mechanical_checks_pass=False, human_quality_accepted=False,
                  production_changed=False, full_pipeline_test=False, offline=True, device='cpu',
                  seed=1234, temperature=.90, tempo=1.342, target_comparison_lufs=-16.5,
                  worker_count=1, cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            report['writer_rate'] = engine.tts.synthesizer.output_sample_rate
            if report['writer_rate'] != 24000:
                raise RuntimeError('Unexpected native checkpoint output rate')
            for name, reference, expected in profiles:
                shutil.copy2(reference, work / (name + '-reference.wav'))
                montage = None
                for index, (label, text) in enumerate(PASSAGES, 1):
                    job.check()
                    random.seed(1234)
                    np.random.seed(1234)
                    torch.manual_seed(1234)
                    stem = f'{name}-{index:02d}-{label}'
                    raw = work / (stem + '-raw.wav')
                    before = time.monotonic()
                    engine.tts.tts_to_file(text=text, file_path=str(raw), speaker_wav=str(reference),
                        language='hi', split_sentences=True, temperature=.90, speed=1.0, **generation_kwargs())
                    synthesis = time.monotonic()-before
                    audio = load_speech_audio(raw)
                    if audio.frame_rate != 24000 or audio.channels != 1:
                        raise RuntimeError('Generated waveform has unexpected format')
                    normalized = work / (stem + '-normalized.wav')
                    shutil.copy2(raw, normalized)
                    normalization = normalize_voice_loudness(normalized)
                    output = work / (stem + '.wav')
                    pipeline.speed_change(load_speech_audio(normalized), 1.342).export(output, format='wav').close()
                    measured = measure_loudness(output)
                    if not all(math.isfinite(measured[key]) for key in ('input_i', 'input_tp')):
                        raise RuntimeError('Cannot measure generated speech')
                    gain = min(-16.5-measured['input_i'], -1.55-measured['input_tp'])
                    load_speech_audio(output).apply_gain(gain).export(output, format='wav').close()
                    final = load_speech_audio(output)
                    level = measure_loudness(output)
                    if abs(len(final)-len(audio)/1.342) > 100 or level['input_tp'] > -1.2:
                        raise RuntimeError('Candidate timing or true peak check failed')
                    for path in (raw, normalized, output):
                        run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                                    check=True, timeout=60)
                    row = dict(voice=name, index=index, label=label, text=text, reference_sha256=expected,
                        raw_file=raw.name, raw_sha256=digest(raw), file=output.name, sha256=digest(output),
                        raw_seconds=len(audio)/1000, seconds=len(final)/1000, synthesis_seconds=round(synthesis, 3),
                        synthesis_real_time_factor=round(synthesis/(len(audio)/1000), 3),
                        normalization=normalization, comparison_gain_db=gain, final_loudness=level)
                    report['cases'].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                    if montage is None:
                        montage = final
                    else:
                        # Deliberate listening separators, not source-video cue timing.
                        gap = AudioSegment.silent(duration=900, frame_rate=24000).set_channels(1).set_sample_width(2)
                        montage += gap + final
                montage_path = work / (name + '-review.wav')
                montage.export(montage_path, format='wav').close()
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(montage_path), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                if digest(reference) != expected:
                    raise RuntimeError('Original reference changed')
            report.update(execution_completed=True, mechanical_checks_pass=True)
            (work / 'case-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-hindi-coverage.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
