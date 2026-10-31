"""Offline, pinned IndicTrans2 comparison; never changes production defaults."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_MODULES_CACHE'] = str(ROOT / 'runtime_profiles/indictrans2-evaluation/hf_modules')
os.environ['OMP_NUM_THREADS'] = '2'
MODEL = ROOT / 'models/translation/indictrans2-evaluation'
REVISION = '0c607654e8b6cce897a32039df79018a1daff4e2'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--cue-receipt', type=Path, help='Translate every timed cue in a completed full-video source receipt')
    args = parser.parse_args()
    stage = 'preflight' if args.preflight else ('full-video-translation' if args.cue_receipt else 'comparison')
    receipt = ROOT / 'docs/validation' / ('2026-10-08-indictrans2-'+stage+'.json')
    report = dict(completed=False, stage=stage, offline=True, production_changed=False,
                  semantic_quality_accepted=False, cases=[])
    started = time.monotonic()
    def save():
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        download = json.loads((ROOT / 'docs/validation' / ('2026-10-08-indictrans2-download-'+
                              ('source' if args.preflight else 'weights')+'.json')).read_text())
        assert download['complete'], 'Download receipt is incomplete'
        for row in download['files']:
            path = MODEL / row['name']
            assert path.stat().st_size == row['bytes'], 'Asset size changed'
            if path.suffix == '.py':
                assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], 'Model source changed'
        report['model_revision'] = download['revision']
        from transformers import AutoConfig, AutoTokenizer, AutoModelForSeq2SeqLM
        from transformers.dynamic_module_utils import get_class_from_dynamic_module
        import torch
        torch.set_num_threads(2)
        config = AutoConfig.from_pretrained(str(MODEL), trust_remote_code=True, local_files_only=True)
        tokenizer = AutoTokenizer.from_pretrained(str(MODEL), trust_remote_code=True, local_files_only=True)
        model_class = get_class_from_dynamic_module(config.auto_map['AutoModelForSeq2SeqLM'],
                                                   str(MODEL), local_files_only=True)
        assert callable(model_class.generate)
        report.update(transformers_version=__import__('transformers').__version__,
                      tokenizer_class=type(tokenizer).__name__, model_class=model_class.__name__,
                      input_limit=config.max_source_positions, output_limit=config.max_target_positions)
        source = ROOT / 'dev/vendor/indictrans2-toolkit-review' / (REVISION+'-processor.py')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == '354c3299229f8b05602d82d0a84a8c2e98082dce38879a3459ca2fc33ec8f7b8'
        spec = importlib.util.spec_from_file_location('reviewed_indictrans_processor', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if args.preflight:
            processor = module.IndicProcessor(inference=True)
            prepared = processor.preprocess_batch(['Good morning. This is a short test.'],
                                                  src_lang='eng_Latn', tgt_lang='hin_Deva')
            inputs = tokenizer(prepared, truncation=False, return_tensors='pt')
            assert inputs['input_ids'].shape[-1] <= config.max_source_positions
            report['input_tokens'] = int(inputs['input_ids'].shape[-1])
            report['weights_loaded'] = False
        else:
            assert torch.cuda.is_available(), 'CUDA required for this evaluation'
            before = time.monotonic()
            model = AutoModelForSeq2SeqLM.from_pretrained(str(MODEL), trust_remote_code=True,
                local_files_only=True, torch_dtype=torch.float16, attn_implementation='eager',
                use_safetensors=True).eval().to('cuda:0')
            report['load_seconds'] = round(time.monotonic()-before, 3)
            report['device'] = torch.cuda.get_device_name(0)
            from dev.translation_evaluation_cases import load_cases
            if args.cue_receipt:
                source_path = args.cue_receipt.resolve()
                assert source_path.is_relative_to(ROOT / 'docs/validation')
                source_report = json.loads(source_path.read_text(encoding='utf-8'))
                assert source_report['completed'] and source_report['full_video']
                report.update(source_receipt=str(source_path), source_sha256=source_report['source_sha256'])
                cases = [dict(id='video-'+str(i+1), source=row['text'], start=row['start'], end=row['end'])
                         for i,row in enumerate(source_report['source_cues'])]
            else:
                cases = load_cases()
            from core.translation_completion import require_finished
            torch.cuda.reset_peak_memory_stats()
            for case in cases:
                processor = module.IndicProcessor(inference=True)
                prepared = processor.preprocess_batch([case['source']], src_lang='eng_Latn', tgt_lang='hin_Deva')
                inputs = tokenizer(prepared, truncation=False, return_tensors='pt').to('cuda:0')
                count = int(inputs['input_ids'].shape[-1])
                assert count <= config.max_source_positions, 'Input exceeds model window'
                before = time.monotonic()
                with torch.inference_mode():
                    tokens = model.generate(**inputs, do_sample=False, num_beams=5,
                        max_new_tokens=config.max_target_positions-1, use_cache=True)
                require_finished(tokens, tokenizer, 'IndicTrans2 evaluation', config.max_target_positions-1)
                decoded = tokenizer.batch_decode(tokens, skip_special_tokens=True,
                                                 clean_up_tokenization_spaces=True)
                translated = processor.postprocess_batch(decoded, lang='hin_Deva')[0]
                assert translated.strip(), 'Empty output'
                row = {**case, 'translation':translated, 'input_tokens':count,
                       'output_tokens':int(tokens.shape[-1]), 'ended_with_eos':True,
                       'elapsed_seconds':round(time.monotonic()-before, 3)}
                report['cases'].append(row)
                save()
                print(json.dumps(row, ensure_ascii=False), flush=True)
            report['peak_cuda_allocated_bytes'] = torch.cuda.max_memory_allocated()
            report['peak_cuda_reserved_bytes'] = torch.cuda.max_memory_reserved()
        report['completed'] = True
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        save()
        print(json.dumps(dict(receipt=str(receipt), completed=report['completed'])), flush=True)


if __name__ == '__main__':
    main()
