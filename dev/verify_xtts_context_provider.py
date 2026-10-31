"""Actual current-provider short-cue checks; existing runtimes/models only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime', choices=('legacy', 'isolated'))
    parser.add_argument('--label', default='')
    args = parser.parse_args()
    if args.label and (not args.label.replace('-', '').isalnum() or not args.label.isascii()):
        raise ValueError('Use an ASCII alphanumeric label')
    folder = ROOT / ('docs/validation/2026-10-30-context-provider-' + args.runtime + ('-' + args.label if args.label else ''))
    folder.mkdir(exist_ok=False)
    from core.render_context import RenderContext, bind_job, run_process
    from core.providers.tts.xtts_local import XTTSLocalProvider
    from core.audio_utils import load_speech_audio
    from core.loudness import normalize_voice_loudness
    job = RenderContext(ROOT / 'temp')
    report = dict(passed=False, runtime=args.runtime, packages_installed=False,
                  model_downloaded=False, human_quality_accepted=False, cases=[])
    sources = ['core/tts/tts_handler.py', 'core/xtts_text.py', 'core/providers/tts/xtts_local.py']
    report['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    try:
        with bind_job(job):
            os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                              HF_HOME=str(job.workspace / 'hf'), MPLCONFIGDIR=str(job.workspace / 'mpl'),
                              OMP_NUM_THREADS='2', PATH=str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', ''))
            reference = job.workspace / 'reference.wav'
            run_process(['ffmpeg', '-v', 'error', '-y', '-ss', '2', '-i', str(ROOT / 'Sample/2.mp4'),
                         '-t', '6', '-vn', '-ar', '24000', '-ac', '1', str(reference)], check=True, timeout=60)
            provider = XTTSLocalProvider(device='cpu', model_path=str(ROOT / 'models/xtts/default'), runtime=args.runtime)
            first_pid = None
            for language, text in (('de', 'Guten Morgen. Willkommen in unserem Studio.'),
                                   ('ko', '좋은 아침입니다. 저희 스튜디오에 오신 것을 환영합니다.')):
                if args.runtime == 'legacy':
                    import torch
                    torch.set_num_threads(2)
                    torch.manual_seed(1234)
                output = job.workspace / (language + '.wav')
                provider.synthesize(text, str(output), language, str(reference))
                clip = load_speech_audio(output)
                row = dict(language=language, text=text, duration_ms=len(clip), sample_rate=clip.frame_rate)
                if args.runtime == 'legacy':
                    # Observe the policy on the loaded production model, rather
                    # than replacing the engine's generation function.
                    from core.xtts_text import should_split_sentences
                    row['split_sentences'] = should_split_sentences(text, language, provider._handler.tts.synthesizer.tts_model)
                    if row['split_sentences']:
                        raise RuntimeError('The production short-cue policy was not selected')
                else:
                    row['worker_pid'] = provider.last_result['worker_pid']
                    row['model_loads'] = provider.last_result['model_loads']
                    if first_pid is None:
                        first_pid = row['worker_pid']
                    if row['worker_pid'] != first_pid or row['model_loads'] != 1:
                        raise RuntimeError('The isolated provider did not reuse its loaded model')
                row['normalization'] = normalize_voice_loudness(output)
                if abs(len(load_speech_audio(output)) - len(clip)) > 20:
                    raise RuntimeError('Normalization changed speech timing')
                retained = folder / (language + '.wav')
                shutil.copy2(output, retained)
                row['sha256'] = hashlib.sha256(retained.read_bytes()).hexdigest()
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=True), flush=True)
            provider.release()
            report['passed'] = len(report['cases']) == 2
    except Exception as error:
        import traceback
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        report['owned_processes_exited'] = not job.processes
        report['source_unchanged'] = report['source_sha256'] == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
        report['passed'] = report['passed'] and report['workspace_removed'] and report['owned_processes_exited'] and report['source_unchanged']
        (folder / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return not report['passed']


if __name__ == '__main__':
    raise SystemExit(main())
