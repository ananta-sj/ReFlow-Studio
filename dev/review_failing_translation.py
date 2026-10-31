"""Review one sentence with retained real models; never hard-code it into production."""
import argparse
import gc
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
import uuid
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ending-review', action='store_true')
    args = parser.parse_args()
    import numpy as np
    import torch
    from core.audio_utils import AudioEngineer, load_speech_audio
    from core.loudness import measure_loudness
    from core.model_assets import RECOVERY_SOURCES
    from core.pipeline import ReflowPipeline
    from core.providers.translation.nllb_local import NLLBLocalProvider
    from core.render_context import RenderContext, bind_job
    from core.tts.tts_handler import TTSHandler

    context = json.loads((ROOT / 'docs/validation/2026-10-04-failing-line-source-context.json').read_text(encoding='utf-8'))
    source_text = ' '.join(s['text'].strip() for s in context['segments'][:2])
    reference = ROOT / 'docs/validation/2026-10-04-voice-quality-b6905bf2/reference.wav'
    job = RenderContext(ROOT / 'temp')
    prefix = 'ending-review' if args.ending_review else 'line-review'
    destination = ROOT / 'docs/validation' / ('2026-10-04-' + prefix + '-' + uuid.uuid4().hex[:8])
    started = time.monotonic()
    report = dict(source_english=source_text, source_accuracy_human_verified=False,
                  proposed_hindi_human_verified=False, sentence_end=6.3, next_start=6.66,
                  original_failure_window=4.880, engine='xtts', seed=1234, offline=True,
                  production_translation_changed=False, execution_completed=False, cases=[])
    try:
        with bind_job(job):
            folder = job.workspace / 'review'
            folder.mkdir()
            if args.ending_review:
                cases = [('fresh-reading', 'जल्द ही खबरों की एक तय दृश्य शैली बनी, जिसे सब तुरंत पहचान लेते थे।',
                          'Same words with a different sampling seed; not a new production seed', 7),
                         ('simpler-ending', 'जल्द ही खबरों की एक तय दृश्य शैली बनी, जिसे हर कोई तुरंत पहचान सकता था।',
                          'Proposed simpler ending; meaning/naturalness require user review', 1234)]
                from core.loudness import normalize_voice_loudness
                previous = ROOT / 'docs/validation/2026-10-04-line-review-76b5fc7e/concise-review-raw.wav'
                diagnostic = folder / 'previous-generation-only.wav'
                shutil.copy2(previous, diagnostic)
                report['generation_only_normalization'] = normalize_voice_loudness(diagnostic)
            else:
                translator = NLLBLocalProvider(str(ROOT / RECOVERY_SOURCES['nllb']['folder']))
                generated = translator.translate(source_text, 'Hindi', source_language='en')
                del translator
                gc.collect()
                cases = [('context-nllb', generated, 'Machine translation of complete contextual sentence', 1234),
                         ('concise-review', 'जल्द ही खबरों की एक तय दृश्य शैली बनी, जिसे सब तुरंत पहचान लेते थे।',
                          'Proposed manual translation; meaning/naturalness require user review', 1234)]
            engine = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']))
            pipeline = ReflowPipeline.__new__(ReflowPipeline)
            pipeline.temp_dir = str(job.workspace)
            pipeline.registry = Mock()
            pipeline.registry.get_active.return_value = None
            pipeline.registry.list.return_value = []
            for name, text, status, seed in cases:
                random.seed(seed)
                np.random.seed(seed)
                torch.manual_seed(seed)
                before = time.monotonic()
                raw = folder / (name + '-raw.wav')
                engine.generate_audio(text, str(raw), language='hi', reference_audio=str(reference))
                row = dict(name=name, text=text, translation_status=status, seed=seed,
                           raw_duration_ms=len(load_speech_audio(raw)), fit_passed=False)
                def replay(request_text, path, language, reference_audio):
                    if request_text != text or language != 'hi':
                        raise RuntimeError('Replay differs from freshly generated speech')
                    shutil.copy2(raw, path)
                    return str(path)
                tts = Mock()
                tts.synthesize.side_effect = replay
                class ReviewEngineer(AudioEngineer):
                    def master_voice_segment(self, path):
                        self.measurement = super().master_voice_segment(path)
                        return self.measurement
                mastering = ReviewEngineer()
                try:
                    clip = pipeline._dub_segment(0, dict(start=0, end=6.3, text=text),
                        ['CLONED_USER'], 'hi', tts, {}, None, str(reference), 'cpu',
                        mastering, next_start=6.66)
                except RuntimeError as exc:
                    if 'cannot fit without cutting words' not in str(exc):
                        raise
                    row['fit_error'] = str(exc)
                else:
                    listening = folder / (name + '.wav')
                    clip.export(listening, format='wav').close()
                    row.update(fit_passed=True, duration_ms=len(clip),
                               measurement=measure_loudness(listening))
                row['mastering'] = getattr(mastering, 'measurement', None)
                row['elapsed_seconds'] = round(time.monotonic() - before, 3)
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            job.publish(folder, destination)
            report.update(execution_completed=True, review_directory=str(destination))
    except Exception as exc:
        report['error'] = str(exc)
        # Retain owned diagnostic raw files on failure, not personal/runtime data.
        if 'folder' in locals() and folder.is_dir() and not destination.exists():
            job.publish(folder, destination)
            report['failed_review_directory'] = str(destination)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),
                      elapsed_seconds=round(time.monotonic() - started, 3))
        receipt = 'robotic-ending-review' if args.ending_review else 'failing-line-review'
        (ROOT / ('docs/validation/2026-10-04-' + receipt + '.json')).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
