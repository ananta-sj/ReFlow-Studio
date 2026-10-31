"""Inspect existing listening samples with the existing local tiny ASR model.

ASR is diagnostic evidence, not a native-speaker pronunciation assessment.
"""
import json
import os
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--greedy', action='store_true')
    parser.add_argument('--continuous', action='store_true')
    parser.add_argument('--label', default='')
    parser.add_argument('languages', nargs='+')
    args = parser.parse_args()
    if args.label and (not args.label.replace('-', '').isalnum() or not args.label.isascii()):
        raise ValueError('Use an ASCII alphanumeric comparison label')
    folder = ROOT / ('docs/validation/2026-10-30-multilingual-speech' + ('-greedy' if args.greedy else '') + ('-continuous' if args.continuous else '') + ('-' + args.label if args.label else ''))
    model = ROOT / 'models/whisper/cache/models--Systran--faster-whisper-tiny/snapshots/d90ca5fe260221311c53c58e660288d3deb8d356'
    if not model.is_dir():
        raise RuntimeError('The existing offline tiny recognition model is unavailable')
    os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='2',
                      HF_HOME=str(ROOT / 'temp/speech-asr-hf'))
    from core.recognition_compat import apply
    apply()
    from faster_whisper import WhisperModel
    engine = WhisperModel(str(model), device='cpu', compute_type='int8', cpu_threads=2, local_files_only=True)
    rows = []
    for language in args.languages:
        if language not in {'de', 'pl', 'en', 'es', 'fr', 'it', 'pt', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi'}:
            raise ValueError('Unknown sample language')
        segments, _ = engine.transcribe(str(folder / (language + '.wav')), language='zh' if language == 'zh-cn' else language,
                                        beam_size=5, vad_filter=False)
        row = dict(language=language, text=' '.join(segment.text.strip() for segment in segments))
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
    (folder / 'asr-diagnostic.json').write_text(json.dumps(dict(human_quality_assessed=False, model='existing faster-whisper-tiny',
                                                              cases=rows), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
