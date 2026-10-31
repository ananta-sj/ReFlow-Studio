"""Live offline checks of local translation completion guards, not meaning acceptance."""
import gc
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
for name in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'REFLOW_OFFLINE'):
    os.environ[name] = '1'
os.environ['OMP_NUM_THREADS'] = '2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=('all', 'nllb', 'm2m100'), default='all')
    args = parser.parse_args()
    import torch
    from core.model_assets import RECOVERY_SOURCES
    from core.providers.translation.nllb_local import NLLBLocalProvider
    from core.llm_translator import LLMTranslator
    from core.translation_completion import require_finished
    from core.render_context import RenderContext, bind_job
    torch.set_num_threads(2)
    job = RenderContext(ROOT / 'temp')
    receipt = ROOT / 'docs/validation' / ('2026-10-08-translation-completion-live-'+uuid.uuid4().hex[:8]+'.json')
    report = dict(completed=False, semantic_quality_accepted=False, production_settings_changed=False,
                  offline=True, engines=[])
    started = time.monotonic()
    try:
        with bind_job(job):
            for engine in (('nllb', 'm2m100') if args.engine == 'all' else (args.engine,)):
                if engine == 'nllb':
                    subject = NLLBLocalProvider(str(ROOT / RECOVERY_SOURCES['nllb']['folder']),
                        device='cuda:0' if torch.cuda.is_available() else 'cpu')
                else:
                    subject = LLMTranslator.__new__(LLMTranslator)
                    subject.init_m2m100()
                row = dict(engine=engine, translations=[])
                for text in ('I do not want to cancel the order.', 'The price is 1,250 rupees, not 250 rupees.',
                             'It starts here, with a lacklustre establishing shot of a significant location.'):
                    row['translations'].append(dict(source=text, output=subject.translate(text, 'Hindi', source_language='en')))
                try:
                    subject.translate('word '*1400, 'Hindi', source_language='en')
                except (ValueError, RuntimeError) as exc:
                    if 'input has' not in str(exc) or 'limit' not in str(exc):
                        raise
                    row['oversize_input_rejected'] = str(exc)
                else:
                    raise RuntimeError('Oversize input was not rejected')
                tokenizer = subject._tokenizer if engine == 'nllb' else subject.tokenizer
                model = subject._model if engine == 'nllb' else subject.model
                device = subject.device
                target = tokenizer.convert_tokens_to_ids('hin_Deva') if engine == 'nllb' else tokenizer.get_lang_id('hi')
                inputs = tokenizer('This is a deliberately long translation that cannot finish in four tokens.',
                                   return_tensors='pt', truncation=False).to(device)
                with torch.inference_mode():
                    tokens = model.generate(**inputs, forced_bos_token_id=target, max_new_tokens=4, do_sample=False)
                try:
                    require_finished(tokens, tokenizer, engine, max_new_tokens=4)
                except RuntimeError as exc:
                    if 'output token limit' not in str(exc):
                        raise
                    row['forced_end_at_cap_rejected'] = str(exc)
                else:
                    raise RuntimeError('Forced token-cap ending was accepted')
                row.update(device=device, input_limit=model.config.max_position_embeddings)
                report['engines'].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                del subject, model, tokenizer, inputs, tokens
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
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
