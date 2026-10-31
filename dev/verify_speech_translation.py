"""Real short CPU acceptance of the existing default speech/translation engines."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
from core.render_context import RenderContext, bind_job, run_process
from core.model_assets import ensure_assets, RECOVERY_SOURCES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['xtts', 'm2m100', 'nllb'])
    args = parser.parse_args()
    job = RenderContext(ROOT / 'temp')
    report = {'engine': args.engine, 'device': 'cpu', 'acceptance': False,
              'quality_reviewed': False, 'revision': RECOVERY_SOURCES[args.engine]['revision']}
    started = time.monotonic()
    try:
        with bind_job(job):
            ensure_assets(args.engine)
            model_path = str(ROOT / RECOVERY_SOURCES[args.engine]['folder'])
            if args.engine == 'xtts':
                from core.tts.tts_handler import TTSHandler
                from core.audio_utils import load_playable_audio
                reference = job.workspace / 'reference.wav'
                run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                             '-t', '6', '-vn', '-ac', '1', '-ar', '24000', str(reference)], check=True, timeout=60)
                output = job.workspace / 'synthesis.wav'
                TTSHandler(device='cpu', model_path=model_path, language='en').generate_audio(
                    'Reflow Studio is ready for another test.', str(output), 'en', str(reference))
                clip = load_playable_audio(str(output))
                report.update(duration_ms=len(clip), bytes=output.stat().st_size)
            else:
                if args.engine == 'm2m100':
                    from core.llm_translator import LLMTranslator
                    engine = LLMTranslator.__new__(LLMTranslator)
                    engine.init_m2m100()
                else:
                    from core.providers.translation.nllb_local import NLLBLocalProvider
                    engine = NLLBLocalProvider(model_path, device='cpu')
                text = engine.translate('Good morning. This is a short test.', 'Hindi', source_language='en')
                if not text.strip() or not any('\u0900' <= char <= '\u097f' for char in text):
                    raise RuntimeError('Translation did not produce nonempty Hindi-script output')
                report['translation'] = text
            report['acceptance'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / f'docs/validation/2026-10-04-{args.engine}-engine.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
