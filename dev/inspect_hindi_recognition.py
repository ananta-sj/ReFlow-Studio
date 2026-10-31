"""Offline diagnostic recognition, not an automatic speech acceptance gate."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
for key in ('REFLOW_OFFLINE', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    os.environ[key] = '1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipts', nargs='+', default=['routing', 'punctuation'])
    parser.add_argument('--run-label', default='controls')
    args = parser.parse_args()
    for label in [*args.receipts, args.run_label]:
        if not label or not all(char.isalnum() or char == '-' for char in label):
            parser.error('Receipt and run labels must be alphanumeric or hyphenated')
    from faster_whisper import WhisperModel
    model_path = next((ROOT / 'models/whisper').rglob('model.bin')).parent
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8', local_files_only=True, cpu_threads=2)
    started = time.monotonic()
    report = dict(model_path=str(model_path), diagnostic_only=True, human_quality_accepted=False, cases=[])
    for receipt_name in args.receipts:
        source = json.loads((ROOT / f'docs/validation/2026-10-06-{receipt_name}.json').read_text(encoding='utf-8'))
        directory = Path(source['directory']).resolve()
        if not directory.is_relative_to((ROOT / 'docs/validation').resolve()):
            raise ValueError('Input outside retained evidence')
        for row in source['cases']:
            audio = directory / (row['label'] + '-raw.wav')
            case = dict(label=row['label'], intended_text=row['text'], source=str(audio), modes=[])
            for language in (None, 'hi'):
                segments, info = model.transcribe(str(audio), language=language, beam_size=5,
                                                  vad_filter=False, temperature=0, condition_on_previous_text=False)
                recognized = [dict(text=seg.text, start=seg.start, end=seg.end,
                                   avg_logprob=seg.avg_logprob, no_speech_prob=seg.no_speech_prob)
                              for seg in segments]
                case['modes'].append(dict(requested_language=language, reported_language=info.language,
                                          language_probability=info.language_probability, segments=recognized))
            report['cases'].append(case)
            print(json.dumps(case, ensure_ascii=False), flush=True)
    report['elapsed_seconds'] = round(time.monotonic()-started, 3)
    (ROOT / f'docs/validation/2026-10-06-recognition-{args.run_label}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
