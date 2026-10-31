"""Serial user-voice evaluation using human-confirmed exact reference excerpts."""
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
PROFILE = ROOT / 'runtime_profiles/indicf5-evaluation'
sys.path.insert(0, str(ROOT))
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['MPLCONFIGDIR'] = str(ROOT / 'temp/indicf5-matplotlib')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('--variants', action='store_true')
    parser.add_argument('--selected', action='store_true')
    parser.add_argument('--prosody', action='store_true')
    parser.add_argument('--reference-comparison', action='store_true')
    parser.add_argument('--alternate-followup', action='store_true')
    parser.add_argument('--long-followup', action='store_true')
    parser.add_argument('--segmented-followup', action='store_true')
    parser.add_argument('--video-followup', action='store_true')
    parser.add_argument('--text-file', type=Path)
    args = parser.parse_args()
    profile = ROOT / 'runtime_profiles/indicf5-gpu-evaluation' if args.gpu else PROFILE
    device = 'cuda:0' if args.gpu else 'cpu'
    if args.variants and not args.gpu:
        raise ValueError('Bounded tuning batch requires the verified GPU evaluation profile')
    if args.selected and (not args.gpu or args.variants):
        raise ValueError('Selected review requires GPU and cannot be combined with a variant sweep')
    if args.prosody and (not args.selected or args.variants):
        raise ValueError('Prosody comparison requires selected GPU settings')
    if args.reference_comparison and (not args.selected or args.prosody):
        raise ValueError('Reference comparison requires selected settings without prosody sweep')
    if args.alternate_followup and (not args.selected or args.prosody or args.reference_comparison):
        raise ValueError('Alternate follow-up requires selected GPU settings without another sweep')
    if args.long_followup and not args.alternate_followup:
        raise ValueError('Long follow-up requires alternate follow-up mode')
    if args.segmented_followup and not args.long_followup:
        raise ValueError('Segmented follow-up requires long follow-up mode')
    if args.video_followup and (not args.long_followup or args.segmented_followup):
        raise ValueError('Video follow-up requires long mode without paragraph segmentation')
    if Path(sys.executable).resolve().parent != profile.resolve():
        raise ValueError('Use the isolated IndicF5 evaluation interpreter')
    print(json.dumps({'stage': 'starting-user-voice-evaluation'}), flush=True)
    import numpy as np
    import soundfile as sf
    import torch
    if args.gpu:
        if json.loads((profile / 'profile.json').read_text(encoding='utf-8')).get('status') != 'gpu-environment-verified':
            raise ValueError('Verify GPU package isolation and operations first')
        if (not torch.cuda.is_available() or torch.__version__ != '2.9.1+cu128' or
                profile / 'Lib/site-packages' not in Path(torch.__file__).resolve().parents):
            raise ValueError('GPU execution unavailable or torch resolved outside GPU profile')
    from safetensors.torch import load_file
    from vocos import Vocos
    from f5_tts.model import DiT
    from f5_tts.infer.utils_infer import load_model, infer_batch_process
    from core.loudness import measure_loudness
    from core.render_context import RenderContext, bind_job, run_process
    preparation = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78.json').read_text(encoding='utf-8'))
    acceptance = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-reference-excerpts-user-acceptance.json').read_text(encoding='utf-8'))
    if not preparation['completed'] or not acceptance['human_transcripts_verified']:
        raise ValueError('Reference preparation or transcript confirmation missing')
    if acceptance['reference_receipt'] != 'docs/validation/2026-10-06-indicf5-reference-excerpts-20f08c78.json':
        raise ValueError('Acceptance belongs to different reference excerpts')
    approved = {row['name']: row for row in acceptance['references']}
    prepared = {row['name']: row for row in preparation['references']}
    cases = [dict(id=name, voice=name, speed=1.0, cfg=2.0, seed=1234) for name in ('sujata', 'abhishek')]
    if args.variants:
        cases += [dict(id='sujata-guidance', voice='sujata', speed=1.0, cfg=1.5, seed=1234),
                  dict(id='sujata-seed', voice='sujata', speed=1.0, cfg=2.0, seed=42),
                  dict(id='abhishek-pace', voice='abhishek', speed=0.65, cfg=2.0, seed=1234),
                  dict(id='abhishek-pace-seed', voice='abhishek', speed=0.65, cfg=2.0, seed=42)]
    selection = None
    if args.selected:
        selection = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-user-choices.json').read_text(encoding='utf-8'))
        prior = json.loads((ROOT / selection['trial_receipt']).read_text(encoding='utf-8'))
        previous = {row['name']: row for row in prior['cases']}
        cases = []
        for chosen in selection['preferred_choices']:
            evidence = previous[chosen['case']]
            if (chosen['listening_sha256'] != evidence['listening_sha256'] or
                    chosen['speed'] != evidence['native_generation_speed'] or
                    chosen['cfg'] != evidence['cfg_strength'] or
                    chosen['seed'] != evidence['diagnostic_seed_before_synthesis']):
                raise ValueError('Preferred settings differ from presented trial evidence')
            cases.append(dict(id=chosen['voice']+'-selected', voice=chosen['voice'],
                              speed=chosen['speed'], cfg=chosen['cfg'], seed=chosen['seed']))
        if args.prosody:
            controls = cases
            cases = []
            for base in controls:
                cases.extend([{**base, 'id': base['voice']+'-steps64', 'steps': 64},
                              {**base, 'id': base['voice']+'-guidance15', 'cfg': 1.5, 'steps': 32},
                              {**base, 'id': base['voice']+'-guidance25', 'cfg': 2.5, 'steps': 32}])
    assets = ROOT / 'models/indicf5/evaluation/assets'
    checkpoint = assets / 'model.safetensors'
    if checkpoint.stat().st_size != 1402789408:
        raise ValueError('Checkpoint differs from pinned official asset size')
    target = 'मेरे पास यह रिपोर्ट है।'
    if args.text_file:
        target = args.text_file.read_text(encoding='utf-8').strip()
        if not target or len(target) > 1000:
            raise ValueError('Review script must contain 1–1000 characters')
    alternate_acceptance = None
    if args.reference_comparison or args.alternate_followup:
        alternate_acceptance = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-alternate-abhishek-acceptance.json').read_text(encoding='utf-8'))
        alternate_preparation = json.loads((ROOT / alternate_acceptance['reference_receipt']).read_text(encoding='utf-8'))
        alternate = next(row for row in alternate_preparation['references'] if row['voice'] == 'abhishek')
        if (not alternate_preparation['completed'] or not alternate_acceptance['human_transcripts_verified'] or
                alternate['sha256'] != alternate_acceptance['reference_sha256'] or
                alternate['transcript_draft'] != alternate_acceptance['reference_text']):
            raise ValueError('Alternate reference confirmation mismatch')
        baseline = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-gpu-user-voices-747ae53b.json').read_text(encoding='utf-8'))
        baseline_case = next(row for row in baseline['cases'] if row['voice'] == 'abhishek')
        if not baseline['completed'] or (args.reference_comparison and baseline_case['text'] != target):
            raise ValueError('Duration control must use the same completed baseline passage')
        base = next(row for row in cases if row['voice'] == 'abhishek')
        cases = [{**base, 'id': 'abhishek-reference-control', 'target_seconds': baseline_case['seconds']},
                 {**base, 'id': 'abhishek-reference-alternate', 'target_seconds': baseline_case['seconds'],
                  'alternate_reference': True}]
        if args.alternate_followup:
            review = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-reference-comparison-user-review.json').read_text(encoding='utf-8'))
            evidence = json.loads((ROOT / 'docs/validation' / review['trial_receipt']).read_text(encoding='utf-8'))
            candidate = next(row for row in evidence['cases'] if row['name'] == review['preferred_case'])
            if (not evidence['completed'] or candidate['listening_sha256'] != review['listening_sha256'] or
                    candidate['reference_sha256'] != alternate_acceptance['reference_sha256']):
                raise ValueError('Follow-up preference/reference evidence mismatch')
            if target == evidence['text']:
                raise ValueError('Follow-up must exercise a different passage')
            cases = [dict(id='abhishek-followup-seed'+str(seed), voice='abhishek',
                          speed=candidate['native_generation_speed'], cfg=candidate['cfg_strength'],
                          seed=seed, steps=candidate['nfe_step'], alternate_reference=True,
                          target_seconds=candidate['seconds']) for seed in (42, 1234)]
            if args.long_followup:
                longer_review = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-followup-user-review.json').read_text(encoding='utf-8'))
                longer_evidence = json.loads((ROOT / 'docs/validation' / longer_review['trial_receipt']).read_text(encoding='utf-8'))
                preferred = next(row for row in longer_evidence['cases'] if row['name'] == longer_review['preferred_case'])
                if (not longer_evidence['completed'] or preferred['listening_sha256'] != longer_review['listening_sha256'] or
                        preferred['reference_sha256'] != alternate_acceptance['reference_sha256'] or
                        target == preferred['text']):
                    raise ValueError('Long follow-up preference/reference/text evidence mismatch')
                seconds = preferred['seconds'] * len(target.encode('utf-8')) / len(preferred['text'].encode('utf-8'))
                cases = [dict(id='abhishek-extended-selected', voice='abhishek',
                    speed=preferred['native_generation_speed'], cfg=preferred['cfg_strength'],
                    seed=preferred['diagnostic_seed_before_synthesis'], steps=preferred['nfe_step'],
                    alternate_reference=True, target_seconds=seconds,
                    duration_basis='UTF-8 text-length ratio to listener-preferred follow-up passage',
                    duration_calibration_receipt=longer_review['trial_receipt'])]
                if args.video_followup:
                    approval = json.loads((ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-acceptance.json').read_text(encoding='utf-8'))
                    draft_path = ROOT / 'docs/validation' / approval['draft_file']
                    draft = json.loads(draft_path.read_text(encoding='utf-8'))
                    if (not approval['human_translation_accepted'] or draft['source_excerpt_seconds'] != 52 or
                            approval.get('draft_sha256') != digest(draft_path)):
                        raise ValueError('Video draft approval missing or fixture changed')
                    target = ' '.join(cue['text'] for cue in draft['cues'])
                    cases = []
                    for index, cue in enumerate(draft['cues']):
                        sentences = [s.strip() for s in re.findall(r'[^।!?]+[।!?]', cue['text'])]
                        if not sentences or ' '.join(sentences) != cue['text']:
                            raise ValueError('Video text must reconstruct exactly from complete Hindi sentences')
                        for sentence_index, sentence in enumerate(sentences):
                            seconds = preferred['seconds'] * len(sentence.encode('utf-8')) / len(preferred['text'].encode('utf-8'))
                            cases.append(dict(id=f'video-cue-{index+1:02d}-sentence-{sentence_index+1:02d}',
                                voice='abhishek', text=sentence, cue_index=index, sentence_index=sentence_index,
                                cue_start=cue['start'], cue_end=cue['end'],
                                speed=preferred['native_generation_speed'], cfg=preferred['cfg_strength'],
                                seed=preferred['diagnostic_seed_before_synthesis'], steps=preferred['nfe_step'],
                                alternate_reference=True, target_seconds=seconds,
                                duration_basis='Per-sentence UTF-8 ratio to preferred B; no cue-based acceleration',
                                duration_calibration_receipt=longer_review['trial_receipt']))
                if args.segmented_followup:
                    sentences = re.findall(r'[^।]+।', target)
                    sentences = [sentence.strip() for sentence in sentences]
                    if len(sentences) != 6 or ' '.join(sentences) != target:
                        raise ValueError('Segmented review requires the exact six-sentence paragraph')
                    total_hops = round(seconds * 24000 / 256)
                    weights = [len(sentence.encode('utf-8')) for sentence in sentences]
                    shares = [total_hops * weight / sum(weights) for weight in weights]
                    hops = [int(share) for share in shares]
                    for index in sorted(range(len(hops)), key=lambda i: shares[i]-hops[i], reverse=True)[:total_hops-sum(hops)]:
                        hops[index] += 1
                    base_case = cases[0]
                    cases = [{**base_case, 'id': 'abhishek-sentence-'+str(i+1), 'text': sentence,
                              'target_seconds': count * 256 / 24000,
                              'duration_basis': 'Sentence UTF-8 shares of paragraph target; largest-remainder hop allocation'}
                             for i, (sentence, count) in enumerate(zip(sentences, hops))]
    tag = ('2026-10-06-indicf5-gpu-user-voices-' if args.gpu else '2026-10-06-indicf5-user-voices-') + uuid.uuid4().hex[:8]
    destination = ROOT / 'docs/validation' / tag
    receipt = ROOT / 'docs/validation' / (tag + '.json')
    report = dict(completed=False, human_quality_accepted=False, production_changed=False,
        offline=True, device=device, text=target, nfe_step=32, baseline_native_generation_speed=1.0,
        planned_cases=cases, interpreter=sys.executable, torch_version=torch.__version__,
        preference=selection, text_file=str(args.text_file) if args.text_file else None,
        cpu_gpu_byte_equivalence_claimed=False,
        reference_transcripts_human_verified=True, reference_acceptance=acceptance,
        alternate_reference_acceptance=alternate_acceptance,
        video_draft=str(draft_path) if args.video_followup else None,
        video_draft_sha256=digest(draft_path) if args.video_followup else None,
        video_translation_approval=approval if args.video_followup else None,
        trained_weights_strictly_loaded=False, model_loaded_once=True, cases=[], directory=str(destination))
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    def save():
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        with bind_job(job):
            torch.set_num_threads(2)
            torch.manual_seed(1234)
            model = load_model(DiT, dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                vocab_file=str(assets / 'checkpoints/vocab.txt'), device=device)
            config = next((ROOT / 'models/f5/cache/models--charactr--vocos-mel-24khz/snapshots').glob('*/config.yaml'))
            vocoder = Vocos.from_hparams(str(config))
            state = load_file(str(checkpoint), device='cpu')
            mp, vp = 'ema_model._orig_mod.', 'vocoder._orig_mod.'
            ms = {key[len(mp):]: value for key, value in state.items() if key.startswith(mp)}
            vs = {key[len(vp):]: value for key, value in state.items() if key.startswith(vp)}
            if len(ms) != 364 or len(vs) != 83 or len(ms)+len(vs) != len(state):
                raise ValueError('Checkpoint tensor namespaces or counts differ')
            model.load_state_dict(ms, strict=True)
            vocoder.load_state_dict(vs, strict=True)
            vocoder.to(device)
            del state, ms, vs
            model.eval()
            vocoder.eval()
            report.update(trained_weights_strictly_loaded=True, model_tensors=364, vocoder_tensors=83)
            if any(char not in model.vocab_char_map for char in target):
                raise ValueError('Target text contains characters outside vocabulary')
            destination.mkdir()
            save()
            print(json.dumps({'stage': 'trained-model-loaded', 'receipt': str(receipt)}), flush=True)
            for case in cases:
                job.check()
                name = case['id']
                case_target = case.get('text', target)
                reference_row = prepared[case['voice']]
                confirmed = approved[case['voice']]
                reference = Path(preparation['directory']) / reference_row['reference_file']
                if case.get('alternate_reference'):
                    reference = Path(alternate['file'])
                    if ROOT / 'docs/validation' not in reference.resolve().parents:
                        raise ValueError('Alternate reference outside validation root')
                    reference_row = dict(reference_sha256=alternate['sha256'], proposed_reference_text=alternate['transcript_draft'])
                    confirmed = alternate_acceptance
                if digest(reference) != confirmed['reference_sha256'] or confirmed['reference_sha256'] != reference_row['reference_sha256']:
                    raise ValueError('Reference differs from accepted excerpt')
                if confirmed['reference_text'] != reference_row['proposed_reference_text']:
                    raise ValueError('Transcript differs from accepted proposal')
                if any(char not in model.vocab_char_map for char in confirmed['reference_text']):
                    raise ValueError('Reference text contains characters outside vocabulary')
                samples, rate = sf.read(reference, dtype='float32', always_2d=True)
                if rate != 24000 or samples.shape[1] != 1:
                    raise ValueError('Expected mono native-rate reference')
                work = job.workspace / name
                work.mkdir()
                calls = 0
                def progress(module, args):
                    nonlocal calls
                    job.check()
                    calls += 1
                    if calls % 8 == 0:
                        print(json.dumps({'voice': name, 'diffusion_forward_calls': calls}), flush=True)
                hook = model.transformer.register_forward_pre_hook(progress)
                if args.gpu:
                    torch.cuda.synchronize()
                    torch.cuda.reset_peak_memory_stats()
                before = time.monotonic()
                fixed_total_seconds = None
                expected_frames = None
                if 'target_seconds' in case:
                    target_hops = round(case['target_seconds'] * rate / 256)
                    expected_frames = target_hops * 256
                    if vocoder.head.istft.padding != 'center' or vocoder.head.istft.hop_length != 256:
                        raise ValueError('Fixed-duration calculation requires the verified centered Vocos head')
                    # Upstream fix_duration includes reference hops, which are removed before vocoding.
                    # Centered ISTFT returns (mel_frames - 1) * hop_length samples.
                    fixed_total_seconds = (len(samples) // 256 + target_hops + 1 + 1e-6) * 256 / rate
                    if len(samples) // 256 + target_hops + 1 > 4096:
                        raise ValueError('Fixed duration exceeds local model sequence limit; use separate cue evaluation')
                print(json.dumps({'stage': 'generating', 'voice': name}), flush=True)
                try:
                    torch.manual_seed(case['seed'])
                    wave, output_rate, _ = infer_batch_process((torch.from_numpy(samples.T.copy()), rate),
                        confirmed['reference_text'], [case_target], model, vocoder, device=device, nfe_step=case.get('steps', 32),
                        speed=case['speed'], cfg_strength=case['cfg'], fix_duration=fixed_total_seconds)
                    if args.gpu:
                        torch.cuda.synchronize()
                finally:
                    hook.remove()
                synthesis = time.monotonic()-before
                if output_rate != 24000 or not np.isfinite(wave).all() or np.max(np.abs(wave)) == 0:
                    raise ValueError('Invalid synthesized audio')
                if expected_frames is not None and len(wave) != expected_frames:
                    raise ValueError(f'Fixed target duration mismatch: expected {expected_frames}, actual {len(wave)}')
                raw, listening = work / 'raw.wav', work / 'listening.wav'
                sf.write(raw, wave, output_rate, subtype='FLOAT')
                level = measure_loudness(raw)
                gain = min(-18.0-level['input_i'], -1.55-level['input_tp'])
                run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(raw), '-af', f'volume={gain}dB',
                    '-c:a', 'pcm_s16le', str(listening)], check=True, timeout=60)
                for path in (raw, listening):
                    run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', os.devnull],
                        check=True, timeout=60)
                if sf.info(raw).frames != sf.info(listening).frames:
                    raise ValueError('Gain-only preparation changed duration')
                if digest(reference) != confirmed['reference_sha256']:
                    raise ValueError('Accepted reference changed during generation')
                job.publish(work, destination / name)
                row = dict(name=name, voice=case['voice'], text=case_target, reference_file=str(reference),
                    reference_sha256=confirmed['reference_sha256'], reference_text=confirmed['reference_text'],
                    reference_seconds=len(samples)/rate, seconds=len(wave)/output_rate,
                    synthesis_seconds=round(synthesis, 3), diagnostic_seed_before_synthesis=case['seed'],
                    native_generation_speed=case['speed'], cfg_strength=case['cfg'],
                    nfe_step=case.get('steps', 32),
                    fixed_total_seconds=fixed_total_seconds, expected_target_frames=expected_frames,
                    duration_basis=case.get('duration_basis'),
                    duration_calibration_receipt=case.get('duration_calibration_receipt'),
                    cue_index=case.get('cue_index'), sentence_index=case.get('sentence_index'),
                    cue_start=case.get('cue_start'), cue_end=case.get('cue_end'),
                    peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated() if args.gpu else None,
                    forward_calls=calls, listening_gain_db=gain, listening_loudness=measure_loudness(destination/name/'listening.wav'),
                    raw_sha256=digest(destination/name/'raw.wav'), listening_sha256=digest(destination/name/'listening.wav'),
                    full_decode_pass=True, gain_only=True, post_generation_tempo_changed=False,
                    human_quality_accepted=False)
                report['cases'].append(row)
                save()
                print(json.dumps(row, ensure_ascii=False), flush=True)
            report['completed'] = True
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        save()
        print(json.dumps({'receipt': str(receipt), **report}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
