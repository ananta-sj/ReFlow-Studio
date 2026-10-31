"""Failed-listening follow-up: known reference, seeds, language and raw controls."""
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-speech-diagnosis-' + uuid.uuid4().hex[:8])
    receipt = ROOT / 'docs/validation/2026-10-04-speech-diagnosis.json'
    report = dict(execution_completed=False, human_quality_accepted=False, offline=True,
                  production_defaults_changed=False, reference_scope='Reference used in earlier user-approved longer Hindi samples; not independently certified clean',
                  device='cpu', temperature=.75, split_sentences=True, cases=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'diagnosis'
            work.mkdir()
            reference = ROOT / 'docs/validation/2026-10-04-voice-quality-b6905bf2/reference.wav'
            report['reference_sha256'] = digest(reference)
            report['reference_seconds'] = len(load_speech_audio(reference))/1000
            shutil.copy2(reference, work / 'reference.wav')
            model = ROOT / RECOVERY_SOURCES['xtts']['folder']
            report['model_revision'] = RECOVERY_SOURCES['xtts']['revision']
            report['model_files'] = {name: digest(model / name) for name in ('config.json', 'vocab.json')}
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(model))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            tokenizer = engine.tts.synthesizer.tts_model.tokenizer
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name, language, text, seed in [
                ('hindi-1234', 'hi', 'मेरे पास यह रिपोर्ट है।', 1234),
                ('hindi-7', 'hi', 'मेरे पास यह रिपोर्ट है।', 7),
                ('english-1234', 'en', 'I have this report.', 1234),
            ]:
                job.check()
                tokens = tokenizer.encode(text, language)
                unk = tokenizer.tokenizer.token_to_id('[UNK]')
                row = dict(name=name, language=language, text=text, seed=seed,
                           token_count=len(tokens), unknown_tokens=tokens.count(unk),
                           decoded_text=tokenizer.decode(tokens))
                print('Text check: ' + json.dumps(row, ensure_ascii=False), flush=True)
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                raw, mastered, listening = [work / (name + suffix) for suffix in ('-raw.wav', '-mastered.wav', '.wav')]
                before = time.monotonic()
                engine.generate_audio(text, str(raw), language=language, reference_audio=str(work / 'reference.wav'))
                row['synthesis_seconds'] = round(time.monotonic()-before, 3)
                shutil.copy2(raw, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                pace = 1.342 if language == 'hi' else 1.0
                clip = pipeline.speed_change(load_speech_audio(mastered), pace)
                clip.export(listening, format='wav').close()
                row.update(raw_seconds=len(load_speech_audio(raw))/1000,
                           final_seconds=len(load_speech_audio(listening))/1000,
                           raw_sha256=digest(raw), tempo=pace)
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            job.publish(work, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
