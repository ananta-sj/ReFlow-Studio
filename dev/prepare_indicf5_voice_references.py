"""Offline reference transcription drafts; preserve sources and require review."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'


def digest(path):
    with path.open('rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    print(json.dumps({'stage': 'starting-reference-preparation', 'interpreter': sys.executable}), flush=True)
    import numpy as np
    import soundfile as sf
    print(json.dumps({'stage': 'loading-torch'}), flush=True)
    import torch
    print(json.dumps({'stage': 'loading-transformers'}), flush=True)
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    from core.generation_control import generation_kwargs
    from core.render_context import RenderContext, bind_job, run_process
    torch.set_num_threads(2)
    prior = json.loads((ROOT / 'docs/validation/2026-10-04-native-hindi.json').read_text(encoding='utf-8'))
    job = RenderContext(ROOT / 'temp')
    tag = '2026-10-06-indicf5-user-references-' + uuid.uuid4().hex[:8]
    destination = ROOT / 'docs/validation' / tag
    receipt = ROOT / 'docs/validation' / (tag + '.json')
    report = dict(completed=False, human_transcripts_verified=False, voice_synthesis_tested=False,
                  production_changed=False, offline=True, device='cpu',
                  recognition_model='existing local whisper-large-v3-turbo',
                  interpreter=sys.executable, recognition_api='feature extractor and model.generate; no codec pipeline',
                  language_hint='hi; reference transcription only, not language detection', references=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            work = job.workspace / 'references'
            work.mkdir()
            for source_row in prior['references']:
                source = Path(source_row['source'])
                source_hash = digest(source)
                if source_hash != source_row['source_sha256']:
                    raise ValueError('Reference source differs from retained original: ' + source.name)
                name = source_row['name']
                reference = work / (name + '-full-reference.wav')
                recognition = work / (name + '-recognition.wav')
                for path, rate in ((reference, 24000), (recognition, 16000)):
                    run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(source),
                                 '-ac', '1', '-ar', str(rate), '-c:a', 'pcm_s16le', str(path)], check=True, timeout=60)
                report['references'].append(dict(name=name, source=str(source), source_sha256=source_hash,
                    reference_file=reference.name, reference_sha256=digest(reference),
                    reference_seconds=sf.info(reference).duration, full_recording=True,
                    silence_trimmed=False, gain_adjusted=False, transcript=''))
            local = ROOT / 'models/f5/reference-asr'
            print(json.dumps({'stage': 'loading-existing-reference-recognizer'}), flush=True)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(str(local), local_files_only=True, torch_dtype=torch.float32)
            processor = AutoProcessor.from_pretrained(str(local), local_files_only=True)
            model.eval()
            calls = 0
            def progress(module, args):
                nonlocal calls
                job.check()
                calls += 1
                if calls % 16 == 0:
                    print(json.dumps({'recognition_decoder_calls': calls}), flush=True)
            hook = model.model.decoder.register_forward_pre_hook(progress)
            try:
                for row in report['references']:
                    job.check()
                    print(json.dumps({'stage': 'transcribing-reference', 'voice': row['name']}), flush=True)
                    samples, rate = sf.read(work / (row['name'] + '-recognition.wav'), dtype='float32')
                    if rate != 16000 or not np.isfinite(samples).all():
                        raise ValueError('Invalid reference recognition input')
                    before = time.monotonic()
                    features = processor.feature_extractor(samples, sampling_rate=rate,
                        return_tensors='pt', return_attention_mask=True)
                    with torch.inference_mode():
                        tokens = model.generate(**features, task='transcribe', language='hi',
                            return_timestamps=True, max_new_tokens=256, do_sample=False, **generation_kwargs())
                    result = processor.tokenizer.decode(tokens[0].tolist(), skip_special_tokens=True, output_offsets=True)
                    row.update(transcript=result['text'].strip(), chunks=result.get('offsets', []),
                               recognition_seconds=round(time.monotonic()-before, 3))
                    if not any(char.isalnum() for char in row['transcript']):
                        raise ValueError('No usable reference transcript')
                    print(json.dumps(row, ensure_ascii=False), flush=True)
            finally:
                hook.remove()
            for row in report['references']:
                if digest(Path(row['source'])) != row['source_sha256']:
                    raise RuntimeError('Original reference changed')
            job.publish(work, destination)
            report.update(completed=True, original_files_unchanged=True, directory=str(destination))
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'receipt': str(receipt), **report}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
