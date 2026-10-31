"""Compare accepted text and rejected cue through the same actual XTTS adapter."""
import hashlib
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from core.audio_utils import load_speech_audio
    from core.providers import resolve as providers
    from core.render_context import RenderContext, bind_job, run_process
    from dev.verify_workflows import FixtureRegistry
    approved = json.loads((ROOT / 'docs/validation/2026-10-04-greedy-coverage.json').read_text(encoding='utf-8'))
    control = next(row for row in approved['cases'] if row['voice'] == 'abhishek' and row['label'] == 'question')
    reference = Path(approved['directory']) / 'abhishek-reference.wav'
    if not reference.resolve().is_relative_to((ROOT / 'docs/validation').resolve()):
        raise ValueError('Reference outside validation storage')
    if sha(reference) != control['reference_sha256']:
        raise ValueError('Approved reference changed')
    rejected = json.loads((ROOT / 'docs/validation/2026-10-06-reference-control.json').read_text(encoding='utf-8'))
    destination = ROOT / 'docs/validation' / ('2026-10-06-routing-' + uuid.uuid4().hex[:8])
    report = dict(human_quality_accepted=False, production_changed=False, language='hi',
                  offline=True, reference_sha256=sha(reference), seed_set=False, cases=[])
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'evidence'
            work.mkdir()
            provider = providers.resolve_tts(FixtureRegistry(), 'cpu')
            for label, text in [('accepted-question', control['text']), ('rejected-line', rejected['text'])]:
                output = work / (label + '-raw.wav')
                before = time.monotonic()
                provider.synthesize(text, str(output), language='hi', reference_audio=str(reference))
                handler = provider._handler
                model = handler.tts.synthesizer.tts_model
                tokenizer = model.tokenizer
                tokens = tokenizer.encode(text, 'hi')
                audio = load_speech_audio(output)
                row = dict(label=label, text=text, seconds=len(audio)/1000, raw_sha256=sha(output),
                           first_token=tokenizer.tokenizer.id_to_token(tokens[0]),
                           token_roundtrip=tokenizer.decode(tokens),
                           unknown_tokens=tokens.count(tokenizer.tokenizer.token_to_id('[UNK]')),
                           writer_rate=handler.tts.synthesizer.output_sample_rate,
                           model_training=model.training, gpt_training=model.gpt.training,
                           decoder_training=model.hifigan_decoder.training,
                           elapsed_seconds=round(time.monotonic()-before, 3))
                if label == 'accepted-question':
                    row['raw_sha_matches_approved'] = row['raw_sha256'] == control['raw_sha256']
                    row['approved_raw_seconds'] = control['seconds']
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-f', 'null', os.devnull],
                            check=True, timeout=60)
                row['full_decode_pass'] = True
                report['cases'].append(row)
                report['model_path'] = handler.model_path
                print(json.dumps(row, ensure_ascii=False), flush=True)
            job.publish(work, destination)
            report['directory'] = str(destination)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        (ROOT / 'docs/validation/2026-10-06-routing.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
