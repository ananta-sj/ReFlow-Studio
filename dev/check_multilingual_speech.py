"""Generate short offline listening samples with existing XTTS assets only.

Signal checks establish usable audio and normalization, not pronunciation or
human approval. No settings, model files or installed packages are changed.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]

CASES = {
    'en': 'Good morning. Welcome to our studio.',
    'es': 'Buenos días. Bienvenidos a nuestro estudio.',
    'fr': 'Bonjour. Bienvenue dans notre studio.',
    'de': 'Guten Morgen. Willkommen in unserem Studio.',
    'it': 'Buongiorno. Benvenuti nel nostro studio.',
    'pt': 'Bom dia. Bem-vindos ao nosso estúdio.',
    'pl': 'Dzień dobry. Witamy w naszym studiu.',
    'tr': 'Günaydın. Stüdyomuza hoş geldiniz.',
    'ru': 'Доброе утро. Добро пожаловать в нашу студию.',
    'nl': 'Goedemorgen. Welkom in onze studio.',
    'cs': 'Dobré ráno. Vítejte v našem studiu.',
    'ar': 'صباح الخير. مرحباً بكم في الاستوديو.',
    'zh-cn': '早上好。欢迎来到我们的工作室。',
    'hu': 'Jó reggelt. Üdvözöljük a stúdiónkban.',
    'ko': '좋은 아침입니다. 저희 스튜디오에 오신 것을 환영합니다.',
    'ja': 'おはようございます。私たちのスタジオへようこそ。',
    'hi': 'सुप्रभात। हमारे स्टूडियो में आपका स्वागत है।',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--greedy', action='store_true', help='Compare deterministic decoding without changing production defaults')
    parser.add_argument('--continuous', action='store_true', help='Compare generation without splitting short sentences')
    parser.add_argument('--label', default='')
    parser.add_argument('languages', nargs='*')
    args = parser.parse_args()
    if any(language not in CASES for language in args.languages):
        parser.error('Choose supported XTTS language codes: ' + ', '.join(CASES))
    if args.label and (not args.label.replace('-', '').isalnum() or not args.label.isascii()):
        raise ValueError('Use an ASCII alphanumeric comparison label')
    cases = {language: CASES[language] for language in args.languages} if args.languages else CASES
    from core.render_context import RenderContext, bind_job, run_process
    from core.speech_language import DEFAULT_XTTS_LANGUAGES, require_xtts_language
    from core.audio_utils import load_speech_audio
    from core.loudness import normalize_voice_loudness, measure_loudness
    model = ROOT / 'models/xtts/default'
    # Refuse a missing installation before any engine recovery path is reached.
    for name in ('config.json', 'model.pth', 'vocab.json', 'speakers_xtts.pth'):
        if not (model / name).is_file():
            raise RuntimeError('Missing existing XTTS file: ' + name)
    assert set(CASES) == DEFAULT_XTTS_LANGUAGES
    for language in CASES:
        require_xtts_language(language, model)
    destination = ROOT / ('docs/validation/2026-10-30-multilingual-speech' + ('-greedy' if args.greedy else '') + ('-continuous' if args.continuous else '') + ('-' + args.label if args.label else ''))
    destination.mkdir(exist_ok=False)
    job = RenderContext(ROOT / 'temp')
    report = dict(passed=False, cases=[], human_quality_accepted=False,
                  pronunciation_verified=False, packages_installed=False, greedy_comparison=args.greedy,
                  continuous_comparison=args.continuous)
    start = time.monotonic()
    try:
        with bind_job(job):
            os.environ.update(
                REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                HF_HOME=str(job.workspace / 'hf'), TORCH_HOME=str(job.workspace / 'torch'),
                MPLCONFIGDIR=str(job.workspace / 'matplotlib'),
                PATH=str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''),
                OMP_NUM_THREADS='2',
            )
            def offline(event, args):
                if event in {'socket.connect', 'socket.getaddrinfo'}:
                    raise RuntimeError('This speech check is offline')
            sys.addaudithook(offline)
            reference = job.workspace / 'reference.wav'
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '6', '-vn', '-ar', '24000', '-ac', '1', str(reference)], check=True, timeout=60)
            import torch
            torch.set_num_threads(2)
            from core.tts.tts_handler import TTSHandler
            engine = TTSHandler(device='cpu', model_path=str(model))
            if args.greedy or args.continuous:
                original = engine.tts.tts_to_file
                def greedy(**kwargs):
                    if args.greedy:
                        kwargs.update(do_sample=False, num_beams=1)
                    if args.continuous:
                        kwargs['split_sentences'] = False
                    return original(**kwargs)
                engine.tts.tts_to_file = greedy
            for language, text in cases.items():
                row = dict(language=language, text=text, passed=False)
                report['cases'].append(row)
                try:
                    torch.manual_seed(1234)
                    raw = job.workspace / (language + '-raw.wav')
                    engine.generate_audio(text, str(raw), language, str(reference))
                    before = load_speech_audio(raw)
                    output = destination / (language + '.wav')
                    shutil.copyfile(raw, output)
                    row['normalization'] = normalize_voice_loudness(output)
                    after = load_speech_audio(output)
                    peak = measure_loudness(output)['input_tp']
                    if abs(len(after) - len(before)) > 20 or peak > -1.2:
                        raise RuntimeError('Speech timeline or peak validation failed')
                    row.update(passed=True, duration_ms=len(after), sample_rate=after.frame_rate,
                               true_peak_db=peak, sha256=hashlib.sha256(output.read_bytes()).hexdigest())
                except Exception as error:
                    row['error'] = str(error)
                print(json.dumps(row, ensure_ascii=True), flush=True)
            report['passed'] = all(row['passed'] for row in report['cases'])
    finally:
        job.cleanup()
        report.update(elapsed_seconds=round(time.monotonic()-start, 3), workspace_removed=not job.workspace.exists())
        (destination / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
