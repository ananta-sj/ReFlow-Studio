"""Native-rate listening comparison and seeded reference controls; offline."""
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
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'


def main():
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.cue_review import digest
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler
    native = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    baseline = json.loads((ROOT / 'docs/validation/2026-10-04-real-video-dub.json').read_text(encoding='utf-8'))
    native_dir, baseline_dir = Path(native['review_directory']), Path(baseline['directory'])
    for source in (native_dir, baseline_dir):
        if not source.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Diagnostic source outside validation storage')
    job = RenderContext(ROOT / 'temp')
    destination = ROOT / 'docs/validation' / ('2026-10-04-xtts-timing-' + uuid.uuid4().hex[:8])
    report = dict(offline=True, human_quality_accepted=False, seed=7, generation_temperature=.75,
                  tempo=1.342, source_words_confirmed=False, cases=[], listening_controls=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            for name in ('sujata', 'abhishek'):
                raw = load_speech_audio(native_dir / (name + '-raw.wav'))
                if raw.frame_rate != 22050:
                    raise ValueError('Comparison requires the known mislabeled decoder samples')
                # Relabel unchanged decoder samples; resampling would preserve
                # the incorrect pitch and duration rather than repair them.
                corrected = raw._spawn(raw.raw_data, overrides={'frame_rate': 24000})
                path = work / (name + '-native-rate-mastered.wav')
                corrected.export(path, format='wav').close()
                AudioEngineer().master_voice_segment(str(path))
                clip = pipeline.speed_change(load_speech_audio(path), 1.342)
                clip.export(work / (name + '-native-rate.wav'), format='wav').close()
                report['listening_controls'].append(dict(name=name, original_raw_seconds=len(raw)/1000,
                    native_raw_seconds=len(corrected)/1000, native_final_seconds=len(clip)/1000,
                    decoder_pcm_unchanged=raw.raw_data == corrected.raw_data, new_inference=False))
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            report['loaded_decoder_rate'] = engine.tts.synthesizer.tts_model.hifigan_decoder.output_sample_rate
            report['writer_rate'] = engine.tts.synthesizer.output_sample_rate
            text = baseline['translated_cues'][1]['text']
            report['text'] = text
            for label, reference in (
                ('clean-1', baseline_dir / 'clean_reference.wav'),
                ('clean-repeat', baseline_dir / 'clean_reference.wav'),
                ('unprocessed', native_dir / 'abhishek-reference.wav'),
            ):
                random.seed(7)
                np.random.seed(7)
                torch.manual_seed(7)
                raw_path = work / (label + '-raw.wav')
                before = time.monotonic()
                engine.generate_audio(text, str(raw_path), language='hi', reference_audio=str(reference))
                mastered = work / (label + '-mastered.wav')
                shutil.copy2(raw_path, mastered)
                AudioEngineer().master_voice_segment(str(mastered))
                clip = pipeline.speed_change(load_speech_audio(mastered), 1.342)
                clip.export(work / (label + '.wav'), format='wav').close()
                row = dict(name=label, reference_sha256=digest(reference), raw_sha256=digest(raw_path),
                    raw_seconds=len(load_speech_audio(raw_path))/1000, final_seconds=len(clip)/1000,
                    fits_2_6_seconds=len(clip) <= 2600, elapsed_seconds=round(time.monotonic()-before, 3))
                report['cases'].append(row)
                print(json.dumps(row), flush=True)
            report['seeded_repeat_identical'] = report['cases'][0]['raw_sha256'] == report['cases'][1]['raw_sha256']
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-04-xtts-timing.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
