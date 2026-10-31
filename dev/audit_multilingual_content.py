"""Compare retained speech with the existing offline CPU Whisper turbo model.

This is an ASR diagnostic, not human acceptance. Run with the already installed
recognition-candidate Python. It never installs or downloads a model/package.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        next_row = [i]
        for j, right in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j-1] + (left != right)))
        row = next_row
    return row[-1]


def normalize(text):
    return ''.join(char if unicodedata.category(char)[0] in 'LNM' else ' '
                   for char in unicodedata.normalize('NFKC', text).casefold())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remaining', action='store_true')
    args = parser.parse_args()
    from core.recognition_runtime import validate
    runtime = validate()
    if Path(sys.executable).resolve() != Path(runtime['executable']).resolve():
        raise RuntimeError('Use the existing verified recognition-candidate interpreter')
    model = ROOT / 'models/whisper/ct2-turbo-candidate-compat/model'
    if not (model / 'model.bin').is_file():
        raise RuntimeError('The existing converted Whisper turbo model is unavailable')
    variants = ('-continuous-remaining',) if args.remaining else ('', '-greedy', '-continuous', '-continuous-additional')
    output = ROOT / ('docs/validation/2026-10-30-strong-multilingual-' + ('remaining-' if args.remaining else '') + 'content.json')
    if output.exists():
        raise RuntimeError('Refusing to overwrite an existing diagnostic receipt')
    started = time.monotonic()
    report = dict(completed=False, model='existing offline CPU Whisper turbo',
                  runtime_identity=runtime['identity'], human_quality_accepted=False,
                  model_downloaded=False, packages_installed=False, cases=[])
    try:
        with tempfile.TemporaryDirectory(prefix='multilingual-asr-', dir=ROOT / 'temp') as scratch:
            os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                              HF_HOME=str(Path(scratch) / 'hf'), TEMP=scratch, TMP=scratch,
                              OMP_NUM_THREADS='4', HF_HUB_DISABLE_TELEMETRY='1')
            def offline(event, args):
                if event in {'socket.connect', 'socket.getaddrinfo'}:
                    raise RuntimeError('Multilingual diagnostics forbid network access')
            sys.addaudithook(offline)
            from core.recognition_compat import apply
            apply()
            from faster_whisper import WhisperModel
            engine = WhisperModel(str(model), device='cpu', compute_type='int8',
                                  cpu_threads=2 if args.remaining else 4, local_files_only=True)
            for suffix in variants:
                folder = ROOT / ('docs/validation/2026-10-30-multilingual-speech' + suffix)
                previous = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
                for sample in previous['cases']:
                    language = sample['language']
                    path = folder / (language + '.wav')
                    if hashlib.sha256(path.read_bytes()).hexdigest() != sample['sha256']:
                        raise RuntimeError('Retained speech identity changed: ' + str(path))
                    segments, info = engine.transcribe(str(path), language='zh' if language == 'zh-cn' else language,
                                                      beam_size=5, vad_filter=False, condition_on_previous_text=False)
                    segments = list(segments)
                    text = ' '.join(segment.text.strip() for segment in segments)
                    expected, actual = normalize(sample['text']), normalize(text)
                    expected_chars, actual_chars = ''.join(expected.split()), ''.join(actual.split())
                    row = dict(variant=suffix or 'baseline', language=language, expected=sample['text'], recognized=text,
                               duration_ms=sample['duration_ms'], character_error_rate=distance(expected_chars, actual_chars)/max(1, len(expected_chars)),
                               word_error_rate=distance(expected.split(), actual.split())/max(1, len(expected.split())),
                               mean_segment_log_probability=sum(s.avg_logprob for s in segments)/max(1, len(segments)))
                    report['cases'].append(row)
                    print(json.dumps(row, ensure_ascii=True), flush=True)
            report['completed'] = True
            del engine
        report['workspace_removed'] = not Path(scratch).exists()
    except Exception as error:
        import traceback
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return not report['completed']


if __name__ == '__main__':
    raise SystemExit(main())
