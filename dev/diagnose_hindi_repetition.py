"""Bounded repetition-penalty controls, no production setting changes."""
import json
import os
from pathlib import Path
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
    from core.audio_utils import load_speech_audio
    from core.cue_review import digest
    from core.model_assets import RECOVERY_SOURCES
    from core.render_context import RenderContext, bind_job, run_process
    from core.tts.tts_handler import TTSHandler
    approved = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').read_text(encoding='utf-8'))
    reference = Path(approved['directory']) / 'abhishek-reference.wav'
    case = next(row for row in approved['cases'] if row['voice'] == 'abhishek' and row['label'] == 'question')
    if not reference.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Reference outside validation storage')
    if digest(reference) != case['reference_sha256']:
        raise ValueError('Accepted reference changed')
    rejected = json.loads((ROOT / 'docs/validation/2026-10-06-reference-control.json').read_text(encoding='utf-8'))
    destination = ROOT / 'docs/validation' / ('2026-10-06-repetition-' + uuid.uuid4().hex[:8])
    report = dict(production_changed=False, human_quality_accepted=False, offline=True,
                  reference_sha256=digest(reference), seed_set=False, cases=[])
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            handler = TTSHandler(device='cpu', model_path=str(ROOT / RECOVERY_SOURCES['xtts']['folder']), language='hi')
            original = handler.tts.tts_to_file
            penalty = 2.0
            def controlled(*args, **kwargs):
                kwargs['repetition_penalty'] = penalty
                return original(*args, **kwargs)
            handler.tts.tts_to_file = controlled
            for label, penalty, text in [('penalty-2', 2.0, rejected['text']),
                                         ('penalty-5', 5.0, rejected['text']),
                                         ('accepted-question-penalty-2', 2.0, case['text'])]:
                raw = work / (label + '-raw.wav')
                before = time.monotonic()
                handler.generate_audio(text, str(raw), language='hi', reference_audio=str(reference))
                audio = load_speech_audio(raw)
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(raw), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                row = dict(label=label, repetition_penalty=penalty, text=text, seconds=len(audio)/1000,
                           raw_sha256=digest(raw), full_decode_pass=True,
                           elapsed_seconds=round(time.monotonic()-before, 3))
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-06-repetition.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
