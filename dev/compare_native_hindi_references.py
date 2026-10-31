"""User-provided Hindi reference controls; preserve originals and defaults."""
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
    from core.generation_control import generation_kwargs
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-long-hindi-delivery.json').read_text(encoding='utf-8'))
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-native-hindi-' + uuid.uuid4().hex[:8])
    report = dict(execution_completed=False, human_quality_accepted=False, production_defaults_changed=False,
                  offline=True, device='cpu', text=prior['text'], seed=1234, temperature=.90,
                  tempo=1.342, split_sentences=True, references=[], cases=[])
    started = time.monotonic()
    sources = [('sujata', Path('C:/Users/19shr/Downloads/Hindi_F_Sujata.mp3')),
               ('abhishek', Path('C:/Users/19shr/Downloads/HIN_M_AbhishekS.mp3'))]
    try:
        with bind_job(job):
            work = job.workspace / 'references'
            work.mkdir()
            for name, source in sources:
                original_hash = digest(source)
                shutil.copy2(source, work / (name + '-source.mp3'))
                clip = load_speech_audio(work / (name + '-source.mp3'))
                reference = work / (name + '-reference.wav')
                clip.set_channels(1).set_frame_rate(24000).export(reference, format='wav').close()
                row = dict(name=name, source=str(source), source_sha256=original_hash,
                           source_seconds=len(clip)/1000, reference_seconds=len(load_speech_audio(reference))/1000,
                           reference_sha256=digest(reference), complete_recording=True,
                           silence_trimmed=False, eq=False, normalization=False)
                report['references'].append(row)
            before = time.monotonic()
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['model_load_seconds'] = round(time.monotonic()-before, 3)
            report['engine_sentences'] = engine.tts.synthesizer.split_into_sentences(report['text'])
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name, source in sources:
                job.check()
                random.seed(report['seed'])
                np.random.seed(report['seed'])
                torch.manual_seed(report['seed'])
                raw, mastered, listening = [work / (name + suffix) for suffix in ('-raw.wav', '-mastered.wav', '.wav')]
                before = time.monotonic()
                engine.tts.tts_to_file(text=report['text'], file_path=str(raw),
                    speaker_wav=str(work / (name + '-reference.wav')), language='hi',
                    split_sentences=True, temperature=.90, speed=1.0, **generation_kwargs())
                synthesis = time.monotonic()-before
                shutil.copy2(raw, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                adjusted = pipeline.speed_change(load_speech_audio(mastered), report['tempo'])
                adjusted.export(listening, format='wav').close()
                row = dict(name=name, raw_seconds=len(load_speech_audio(raw))/1000,
                           final_seconds=len(load_speech_audio(listening))/1000,
                           synthesis_seconds=round(synthesis, 3), raw_sha256=digest(raw))
                report['cases'].append(row)
                print(json.dumps(row), flush=True)
            for reference, (_, source) in zip(report['references'], sources):
                if digest(source) != reference['source_sha256']:
                    raise RuntimeError('Original user reference changed during comparison')
            job.publish(work, destination)
            report.update(execution_completed=True, review_directory=str(destination), original_files_unchanged=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-started, 3), workspace_removed=not job.workspace.exists())
        (ROOT / 'docs/validation/2026-10-04-native-hindi.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
