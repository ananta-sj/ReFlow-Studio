"""Longer Hindi listening checks against the preferred pace; no default changes."""
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
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.loudness import measure_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler

    reference = ROOT / 'docs/validation/2026-10-04-voice-quality-b6905bf2/reference.wav'
    load_speech_audio(reference)
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-long-hindi-' + uuid.uuid4().hex[:8])
    started = time.monotonic()
    # The preferred short clip had 1.1x first, then 1.22x, plus an ending edit.
    # Compare its general pace only; do not invent final-word boundaries.
    pace = 1.1 * 1.22
    report = dict(engine='xtts', offline=True, device='cpu', seed=1234,
                  reference=str(reference), revision=RECOVERY_SOURCES['xtts']['revision'],
                  tempo=pace, final_word_edit=False, production_defaults_changed=False,
                  execution_completed=False, human_quality_accepted=False, cases=[])
    texts = [
        ('quality', 'आज हम इस वीडियो की आवाज़ और अनुवाद की गुणवत्ता जाँच रहे हैं। हर शब्द साफ़ सुनाई देना चाहिए।'),
        ('meeting', 'कृपया दरवाज़ा खुला रखें। बैठक कल सुबह नौ बजे शुरू होगी, और सभी लोगों का समय पर पहुँचना ज़रूरी है।'),
    ]
    try:
        with bind_job(job):
            folder = job.workspace / 'review'
            folder.mkdir()
            shutil.copy2(reference, folder / 'reference.wav')
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name, text in texts:
                job.check()
                random.seed(report['seed'])
                np.random.seed(report['seed'])
                torch.manual_seed(report['seed'])
                before = time.monotonic()
                raw, mastered, listening = (folder / (name + suffix) for suffix in
                                            ('-raw.wav', '-original-pace.wav', '-preferred-pace.wav'))
                engine.generate_audio(text, str(raw), language='hi', reference_audio=str(reference))
                shutil.copy2(raw, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                original = load_speech_audio(mastered)
                adjusted = pipeline.speed_change(original, pace)
                if abs(len(adjusted) - len(original) / pace) > 100 or adjusted.max == 0:
                    raise RuntimeError('Longer passage failed duration/content validation')
                adjusted.export(listening, format='wav').close()
                load_speech_audio(listening)
                row = dict(name=name, text=text, raw_duration_ms=len(load_speech_audio(raw)),
                           preferred_duration_ms=len(adjusted),
                           measurement=measure_loudness(listening),
                           elapsed_seconds=round(time.monotonic() - before, 3))
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            job.publish(folder, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),
                      elapsed_seconds=round(time.monotonic() - started, 3))
        (ROOT / 'docs/validation/2026-10-04-long-hindi-voice.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
