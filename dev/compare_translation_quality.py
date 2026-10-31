"""Offline decoding comparison; proposed references are not human acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['REFLOW_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=['nllb', 'm2m100'], default='nllb')
    args = parser.parse_args()
    from core.model_assets import RECOVERY_SOURCES, ensure_assets
    from core.render_context import RenderContext, bind_job
    import torch
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    report = {'engine': args.engine, 'revision': RECOVERY_SOURCES[args.engine]['revision'],
              'source': 'English', 'target': 'Hindi', 'device': 'cpu', 'offline': True,
              'execution_completed': False, 'semantic_quality_accepted': False,
              'reference_status': 'proposed references; human review required', 'cases': []}
    try:
        with bind_job(job):
            ensure_assets(args.engine)
            if args.engine == 'nllb':
                from core.providers.translation.nllb_local import NLLBLocalProvider
                provider = NLLBLocalProvider(str(ROOT / RECOVERY_SOURCES['nllb']['folder']))
                provider._ensure_loaded()
                tokenizer, model = provider._tokenizer, provider._model
                tokenizer.src_lang = 'eng_Latn'
                target = tokenizer.convert_tokens_to_ids('hin_Deva')
            else:
                from core.llm_translator import LLMTranslator
                provider = LLMTranslator.__new__(LLMTranslator)
                provider.init_m2m100()
                tokenizer, model = provider.tokenizer, provider.model
                tokenizer.src_lang = 'en'
                target = tokenizer.get_lang_id('hi')
            report['checkpoint_default_beams'] = model.generation_config.num_beams
            cases = json.loads((ROOT / 'dev/translation_quality_cases.json').read_text(encoding='utf-8'))
            with torch.inference_mode():
                for case in cases:
                    row = {**case, 'candidates': []}
                    inputs = tokenizer(case['source'], return_tensors='pt').to('cpu')
                    for beams in (1, 5):
                        job.check()
                        before = time.monotonic()
                        from core.generation_control import generation_kwargs
                        tokens = model.generate(**inputs, forced_bos_token_id=target,
                            num_beams=beams, do_sample=False, max_new_tokens=512, **generation_kwargs())
                        output = tokenizer.batch_decode(tokens, skip_special_tokens=True)[0].strip()
                        if not output:
                            raise RuntimeError('Quality comparison generated empty text')
                        row['candidates'].append({'beams': beams, 'translation': output,
                            'generated_tokens': len(tokens[0]),
                            'elapsed_seconds': round(time.monotonic() - before, 3)})
                    report['cases'].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
            report['production_probe'] = provider.translate('Good morning.', 'Hindi', source_language='en')
            report['execution_completed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        (ROOT / f'docs/validation/2026-10-04-{args.engine}-quality-comparison.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
