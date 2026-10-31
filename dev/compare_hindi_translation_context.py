"""Offline NLLB decoding/context experiment; no production setting changes."""
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE'):
    os.environ[key] = '1'
os.environ['OMP_NUM_THREADS'] = '2'


def main():
    import torch
    from core.model_assets import RECOVERY_SOURCES
    from core.providers.translation.nllb_local import NLLBLocalProvider
    from core.render_context import RenderContext, bind_job
    from core.generation_control import generation_kwargs
    if not torch.cuda.is_available():
        raise RuntimeError('Use the existing GPU evaluation runtime.')
    torch.set_num_threads(2)
    source_receipt = ROOT / 'docs/validation/2026-10-06-indicf5-video-cues-9fce0cd4.json'
    source = json.loads(source_receipt.read_text(encoding='utf-8'))
    checks = json.loads((ROOT / 'dev/translation_quality_cases.json').read_text(encoding='utf-8'))
    cases = [dict(id='video-'+str(index+1), source=row['text'])
             for index, row in enumerate(source['source_cues']) if index in (2, 3, 5, 6, 7)]
    cases += [row for row in checks if row['id'] in ('negation', 'time-and-date', 'numbers-and-negation')]
    receipt = ROOT / 'docs/validation' / ('2026-10-06-hindi-translation-context-'+uuid.uuid4().hex[:8]+'.json')
    report = dict(completed=False, semantic_quality_accepted=False, production_changed=False,
                  existing_local_model=RECOVERY_SOURCES['nllb']['repo'], offline=True,
                  source_receipt=source_receipt.name, cases=[], fragments=[])
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            provider = NLLBLocalProvider(str(ROOT / RECOVERY_SOURCES['nllb']['folder']), device='cuda:0')
            provider._ensure_loaded()
            tokenizer, model = provider._tokenizer, provider._model
            tokenizer.src_lang = 'eng_Latn'
            target = tokenizer.convert_tokens_to_ids('hin_Deva')
            report.update(device=provider.device, model_max_positions=model.config.max_position_embeddings,
                          transformers_version=__import__('transformers').__version__)
            def generate(text, beams, length_penalty):
                job.check()
                inputs = tokenizer(text, return_tensors='pt', truncation=False).to(provider.device)
                before = time.monotonic()
                with torch.inference_mode():
                    tokens = model.generate(**inputs, forced_bos_token_id=target,
                        max_new_tokens=512, num_beams=beams, length_penalty=length_penalty,
                        do_sample=False, **generation_kwargs())
                return dict(translation=tokenizer.batch_decode(tokens, skip_special_tokens=True)[0],
                    input_tokens=inputs['input_ids'].shape[-1], output_tokens=tokens.shape[-1],
                    ended_with_eos=int(tokens[0,-1]) == tokenizer.eos_token_id,
                    beams=beams, length_penalty=length_penalty,
                    elapsed_seconds=round(time.monotonic()-before, 3))
            for case in cases:
                row = {**case, 'candidates': []}
                for beams, penalty in ((5, 1.0), (5, 1.2), (8, 1.2)):
                    row['candidates'].append(generate(case['source'], beams, penalty))
                report['cases'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            for fragment in source['raw_source_cues']:
                if 14 <= fragment['start'] < 28.72:
                    report['fragments'].append({**fragment, **generate(fragment['text'], 5, 1.0)})
            report['completed'] = True
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(), elapsed_seconds=round(time.monotonic()-started, 3))
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(receipt=str(receipt), completed=report['completed'])), flush=True)


if __name__ == '__main__':
    main()
