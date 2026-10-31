"""Explicit F5 profile synthesis acceptance; no application registry changes."""
import json
import os
from pathlib import Path
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['HF_HOME'] = str(ROOT / 'models/f5/cache')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
from core.downloader import download_with_progress
from core.model_contract import local_contract
from core.optional_runtime import run_feature
from core.render_context import RenderContext, bind_job
from core.audio_utils import load_playable_audio


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--automatic-reference', action='store_true')
    args = parser.parse_args()
    revision = '84e5a410d9cead4de2f847e7c9369a6440bdfaca'
    destination = ROOT / 'models/f5/acceptance_v1'
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': 'f5', 'recipe': 'F5TTS_v1_Base', 'revision': revision,
              'device': 'cpu', 'acceptance': False, 'reference_transcription_tested': args.automatic_reference}
    try:
        with bind_job(job):
            if not destination.exists():
                for progress in download_with_progress('https://huggingface.co/SWivid/F5-TTS', str(destination),
                    allow_patterns=['F5TTS_v1_Base/model_1250000.safetensors', 'F5TTS_v1_Base/vocab.txt', 'LICENSE*', 'README.md'],
                    revision=revision):
                    if progress.get('phase') == 'done':
                        print(json.dumps(progress), flush=True)
            contract = local_contract('voice', str(destination), 'f5tts')
            output = job.workspace / 'synthesis.wav'
            reference = ROOT / 'runtime_profiles/f5/Lib/site-packages/f5_tts/infer/examples/basic/basic_ref_en.wav'
            run_feature('f5', 'f5_speech', {**contract, 'device': 'cpu', 'reference_audio': str(reference),
                'reference_text': '' if args.automatic_reference else 'Some call me nature, others call me mother nature.',
                'text': 'Good morning.' if args.automatic_reference else 'Reflow Studio is ready for its next verification.',
                'output_path': str(output)})
            clip = load_playable_audio(str(output))
            report.update({'duration_ms': len(clip), 'bytes': output.stat().st_size,
                           'acceptance': True, 'synthesis_quality_verified': False})
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        receipt = '2026-10-04-f5-automatic-reference.json' if args.automatic_reference else '2026-10-04-f5-engine.json'
        (ROOT / 'docs/validation' / receipt).write_text(json.dumps(report, indent=2), encoding='utf-8')
        job.cleanup()
    print(json.dumps(report))


if __name__ == '__main__':
    main()
