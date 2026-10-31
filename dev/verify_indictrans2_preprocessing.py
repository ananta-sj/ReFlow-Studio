"""Exercise reviewed upstream preprocessing and dependency/CUDA isolation only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = '0c607654e8b6cce897a32039df79018a1daff4e2'
EXPECTED = '354c3299229f8b05602d82d0a84a8c2e98082dce38879a3459ca2fc33ec8f7b8'


def main():
    started = time.monotonic()
    report = dict(passed=False, model_loaded=False, translation_quality_evaluated=False,
                  toolkit_revision=REVISION, checks=[])
    try:
        import torch
        import transformers
        import tokenizers
        import huggingface_hub
        import sentencepiece
        import sacremoses
        import indicnlp
        profile = ROOT / 'runtime_profiles/indictrans2-evaluation/Lib/site-packages'
        report['packages'] = {}
        for module in (torch, transformers, tokenizers, huggingface_hub, sentencepiece, sacremoses, indicnlp):
            report['packages'][module.__name__] = dict(version=getattr(module, '__version__', None),
                                                      path=module.__file__)
            if module is not torch:
                assert Path(module.__file__).is_relative_to(profile), module.__name__ + ' escaped overlay'
        assert Path(torch.__file__).is_relative_to(ROOT / 'runtime_profiles/indicf5-gpu-evaluation')
        assert transformers.__version__ == '4.51.3'
        source = ROOT / 'dev/vendor/indictrans2-toolkit-review' / (REVISION+'-processor.py')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED
        spec = importlib.util.spec_from_file_location('reviewed_indictrans_processor', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        examples = [
            ('Email studio@example.com at https://example.com/help.', ['studio@example.com', 'https://example.com/help']),
            ('Do not charge 1,250 rupees on 12/10/2026.', ['1,250', '12/10/2026']),
            ('Call +91-9876543210 at 10:30.', ['+91-9876543210', '10:30']),
            ('Good morning. This is a short test.', []),
        ]
        for text, entities in examples:
            processor = module.IndicProcessor(inference=True)
            prepared = processor.preprocess_batch([text], src_lang='eng_Latn', tgt_lang='hin_Deva')
            assert len(prepared) == 1 and prepared[0].startswith('eng_Latn hin_Deva ')
            # A synthetic Hindi output carrying the actual prepared placeholders verifies restoration,
            # without pretending it is a generated model translation.
            simulated = 'नमस्ते ' + prepared[0].removeprefix('eng_Latn hin_Deva ')
            result = processor.postprocess_batch([simulated], lang='hin_Deva')[0]
            entities_preserved = all(entity in result for entity in entities)
            assert processor._placeholder_entity_maps.empty()
            report['checks'].append(dict(input=text, preprocessed=prepared[0],
                synthetic_postprocessed=result, expected_entities=entities, passed=entities_preserved))
        assert torch.cuda.is_available(), 'CUDA unavailable'
        tensor = torch.tensor([2., 3.], device='cuda')
        assert float((tensor * tensor).sum().cpu()) == 13.
        report['cuda'] = dict(device=torch.cuda.get_device_name(0), calculation_passed=True)
        report['runtime_and_cuda_passed'] = True
        report['passed'] = all(row['passed'] for row in report['checks'])
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-preprocessing.json'
        receipt.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(dict(receipt=str(receipt), passed=report['passed'], error=report.get('error'))), flush=True)
    if not report['passed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
