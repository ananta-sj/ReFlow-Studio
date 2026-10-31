"""Fresh offline source/translation drafts for the existing moving-video fixture."""
import hashlib
import argparse
import json
import os
import re
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE'):
    os.environ[key] = '1'
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['OMP_NUM_THREADS'] = '2'


def digest(path):
    with path.open('rb') as handle:
        result = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            result.update(chunk)
        return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--context', action='store_true', help='Extend to 60 seconds and translate complete sentence groups')
    parser.add_argument('--full-video', action='store_true', help='Recognize and group the complete existing video')
    parser.add_argument('--source-only', action='store_true', help='Prepare timed source cues without loading NLLB')
    args = parser.parse_args()
    excerpt_seconds = 60 if args.context else 44
    import numpy as np
    import soundfile as sf
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    from core.generation_control import generation_kwargs
    from core.render_context import RenderContext, bind_job, run_process
    from core.model_assets import RECOVERY_SOURCES
    from core.providers.translation.nllb_local import NLLBLocalProvider
    expected = ROOT / 'runtime_profiles/indicf5-gpu-evaluation'
    if Path(sys.executable).resolve().parent != expected or not torch.cuda.is_available():
        raise ValueError('Use the previously verified isolated GPU interpreter')
    torch.set_num_threads(2)
    source = ROOT / 'Sample/2.mp4'
    original_hash = digest(source)
    label = '2026-10-08-full-video-source-' if args.full_video else '2026-10-06-indicf5-video-cues-'
    destination = ROOT / 'docs/validation' / (label+uuid.uuid4().hex[:8])
    report = dict(completed=False, human_text_reviewed=False, human_quality_accepted=False,
        production_changed=False, offline=True, source=str(source), source_sha256=original_hash,
        source_excerpt_seconds=excerpt_seconds, context_grouping=args.context or args.full_video,
        recognition_model='existing local whisper-large-v3-turbo',
        recognition_device='cuda:0', recognition_language_hint='en',
        translation_model='existing local NLLB', source_cues=[], translated_cues=[],
        directory=str(destination))
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            if args.full_video:
                probe = run_process(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(source)],
                                    capture_output=True, text=True, check=True, timeout=60)
                excerpt_seconds = float(json.loads(probe.stdout)['format']['duration'])
                report.update(source_excerpt_seconds=excerpt_seconds, full_video=True)
            work = job.workspace / 'evidence'
            work.mkdir()
            audio = work / 'source-16k.wav'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(source), '-t', str(excerpt_seconds),
                '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(audio)], check=True, timeout=120)
            samples, rate = sf.read(audio, dtype='float32')
            if rate != 16000 or samples.ndim != 1 or not np.isfinite(samples).all():
                raise ValueError('Invalid source audio')
            print('Loading existing stronger recognition model', flush=True)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(str(ROOT / 'models/f5/reference-asr'),
                local_files_only=True).to('cuda:0').eval()
            report['recognition_dtype'] = str(model.dtype)
            processor = AutoProcessor.from_pretrained(str(ROOT / 'models/f5/reference-asr'), local_files_only=True)
            hook = model.model.decoder.register_forward_pre_hook(lambda *_: job.check())
            try:
                for first in range(0, len(samples), 30*rate):
                    job.check()
                    block = samples[first:first+30*rate]
                    features = processor.feature_extractor(block, sampling_rate=rate,
                        return_tensors='pt', return_attention_mask=True).to('cuda:0')
                    features['input_features'] = features['input_features'].to(dtype=model.dtype)
                    with torch.inference_mode():
                        tokens = model.generate(**features, task='transcribe', language='en',
                            return_timestamps=True, max_new_tokens=440, do_sample=False, **generation_kwargs())
                    decoded = processor.tokenizer.decode(tokens[0].tolist(), skip_special_tokens=True, output_offsets=True)
                    report.setdefault('recognition_blocks', []).append(dict(start_seconds=first/rate, **decoded))
                    for item in decoded.get('offsets', []):
                        start, end = item['timestamp']
                        text = item['text'].strip()
                        if start is None or end is None or not text:
                            raise ValueError('Recognition produced an incomplete timed phrase')
                        begin = first/rate+start
                        finish = min(first/rate+end, (first+len(block))/rate, excerpt_seconds)
                        if not 0 <= begin < finish <= excerpt_seconds:
                            raise ValueError('Recognition timestamps outside source excerpt')
                        report['source_cues'].append(dict(start=begin, end=finish, text=text))
                    print('Recognized source block at '+str(first/rate)+' seconds', flush=True)
            finally:
                hook.remove()
            if not report['source_cues']:
                raise ValueError('No timed source phrases')
            del features, tokens, model, processor
            torch.cuda.empty_cache()
            translation_inputs = report['source_cues']
            if args.context or args.full_video:
                report['raw_source_cues'] = report['source_cues']
                grouped, pending = [], []
                for cue in report['raw_source_cues']:
                    pending.append(cue)
                    if re.search(r'[.!?][\"\u201d]*$', cue['text']):
                        grouped.append(dict(start=pending[0]['start'], end=pending[-1]['end'],
                                            text=' '.join(row['text'] for row in pending)))
                        pending = []
                if args.full_video and pending:
                    grouped.append(dict(start=pending[0]['start'], end=pending[-1]['end'],
                                        text=' '.join(row['text'] for row in pending)))
                if args.full_video:
                    joined = []
                    for cue in grouped:
                        at_block_boundary = abs(cue['start'] / 30 - round(cue['start'] / 30)) < .001
                        if (joined and at_block_boundary and re.match(r'^[a-z]', cue['text'])
                                and re.search(r'\b(?:and|or|but|because|not)\.$', joined[-1]['text'])):
                            previous = joined.pop()
                            report.setdefault('recognition_boundary_joins', []).append([previous, cue])
                            cue = dict(start=previous['start'], end=cue['end'],
                                       text=previous['text'][:-1]+' '+cue['text'])
                        joined.append(cue)
                    grouped = joined
                endpoint = grouped[-1]['end'] if args.full_video and grouped else next((cue['end'] for cue in grouped if cue['end'] >= 44), None)
                if endpoint is None:
                    raise ValueError('No complete sentence endpoint beyond 44 seconds in extended source')
                translation_inputs = [cue for cue in grouped if cue['end'] <= endpoint]
                report.update(source_cues=translation_inputs, selected_video_end_seconds=endpoint,
                              unselected_complete_groups=[cue for cue in grouped if cue['end'] > endpoint],
                              incomplete_tail_cues=pending,
                              grouping_policy=('Join timed ASR phrases through the full source; retain final timed tail for review' if args.full_video else
                                               'Join ASR phrases until terminal sentence punctuation; select first complete endpoint at/after 44 seconds'))
                confirmed = json.loads((ROOT / 'docs/validation/2026-10-06-video-source-wording-acceptance.json').read_text(encoding='utf-8'))
                if confirmed['confirmed_source_text'] not in [cue['text'] for cue in translation_inputs]:
                    raise ValueError('Fresh context transcript differs from human-confirmed source phrase')
                report['confirmed_source_wording'] = confirmed
            if not args.source_only:
                translator = NLLBLocalProvider(str(ROOT / RECOVERY_SOURCES['nllb']['folder']), device='cuda:0')
                for i, cue in enumerate(translation_inputs):
                    job.check()
                    translated = translator.translate(cue['text'], 'Hindi', source_language='en')
                    report['translated_cues'].append({**cue, 'text': translated})
                    print('Translated cue '+str(i+1), flush=True)
                del translator
            else:
                report['translation_model'] = None
            torch.cuda.empty_cache()
            if digest(source) != original_hash:
                raise ValueError('Source changed during preparation')
            (work / 'cue-drafts.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            job.publish(work, destination)
            report.update(completed=True, source_unchanged=True)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        receipt = destination.with_suffix('.json')
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'receipt':str(receipt), 'completed':report['completed'], 'error':report.get('error')}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
