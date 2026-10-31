"""Offline pinned IndicTrans2 in its existing isolated GPU runtime."""
import importlib.util
import faulthandler
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                  HF_MODULES_CACHE=str(ROOT / 'runtime_profiles/indictrans2-evaluation/hf_modules'))


def postprocess_candidate(module, text, source, target, decoded):
    """Each beam needs its own source placeholder record; processing consumes it."""
    processor = module.IndicProcessor(inference=True)
    processor.preprocess_batch([text], src_lang=source, tgt_lang=target)
    return processor.postprocess_batch(decoded, lang=target)[0]


def session(params):
    faulthandler.dump_traceback_later(45, repeat=True)
    print(json.dumps(dict(engine='indictrans2',stage='loading-runtime')),flush=True)
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, StoppingCriteria, StoppingCriteriaList
    from core.indictrans2_assets import validate_assets
    from core.translation_completion import require_finished
    from core.providers.base import require_translation_text
    if transformers.__version__ != '4.51.3' or torch.__version__ != '2.9.1+cu128' or not torch.cuda.is_available():
        raise RuntimeError('IndicTrans2 needs the existing verified Transformers 4.51.3 / CUDA runtime.')
    print(json.dumps(dict(engine='indictrans2',stage='checking-assets')),flush=True)
    contract = validate_assets(params['model_path'], verify_weights=True)
    torch.set_num_threads(2)
    model_path = contract['model_path']
    print(json.dumps(dict(engine='indictrans2',stage='loading-model')),flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path, trust_remote_code=True,
        local_files_only=True, torch_dtype=torch.float16, attn_implementation='eager',
        use_safetensors=True).eval().to('cuda:0')
    spec = importlib.util.spec_from_file_location('reflow_indictrans_processor', contract['processor_path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    folder = Path(params['session_dir'])
    class Stop(StoppingCriteria):
        def __call__(self, *args, **kwargs):
            return (folder / 'stop').exists()
    print(json.dumps({'engine':'indictrans2', 'stage':'model-ready', 'worker_pid':os.getpid()}), flush=True)
    faulthandler.cancel_dump_traceback_later()
    last = 0
    while not (folder / 'stop').exists():
        for request in sorted(folder.glob('call-????????.json')):
            sequence = int(request.stem[5:])
            if sequence <= last:
                continue
            response = dict(ok=False, engine='indictrans2', worker_pid=os.getpid(), sequence=sequence)
            try:
                call = json.loads(request.read_text(encoding='utf-8'))
                if call['source'] != 'eng_Latn' or call['target'] != 'hin_Deva':
                    raise ValueError('This reviewed IndicTrans2 route supports English to Hindi only.')
                text = require_translation_text(call['text'])
                mode = call.get('mode', 'translation')
                maximum = call.get('max_candidates', 3)
                if mode not in ('translation', 'dialogue_options') or type(maximum) is not int or not 1 <= maximum <= 3:
                    raise ValueError('Unsupported bounded translation request.')
                print(json.dumps(dict(engine='indictrans2',stage='request-started',sequence=sequence,mode=mode)),flush=True)
                if mode == 'dialogue_options':
                    faulthandler.dump_traceback_later(60, repeat=True)
                processor = module.IndicProcessor(inference=True)
                prepared = processor.preprocess_batch([text], src_lang=call['source'], tgt_lang=call['target'])
                inputs = tokenizer(prepared, truncation=False, return_tensors='pt').to('cuda:0')
                count = int(inputs['input_ids'].shape[-1])
                if count > model.config.max_source_positions:
                    raise ValueError('IndicTrans2 input exceeds its token window; split into complete sentences.')
                generation = dict(num_return_sequences=maximum, length_penalty=0.0) if mode == 'dialogue_options' else {}
                with torch.inference_mode():
                    tokens = model.generate(**inputs, do_sample=False, num_beams=5,
                        max_new_tokens=model.config.max_target_positions-1, use_cache=True,
                        stopping_criteria=StoppingCriteriaList([Stop()]), **generation)
                print(json.dumps(dict(engine='indictrans2',stage='tokens-generated',sequence=sequence)),flush=True)
                if (folder / 'stop').exists():
                    raise RuntimeError('IndicTrans2 translation cancelled.')
                if mode == 'dialogue_options':
                    candidates=[]
                    incomplete=0
                    for generated_sequence in tokens.tolist():
                        while generated_sequence and tokenizer.pad_token_id != tokenizer.eos_token_id and generated_sequence[-1] == tokenizer.pad_token_id:
                            generated_sequence=generated_sequence[:-1]
                        try:
                            require_finished([generated_sequence], tokenizer, 'IndicTrans2', model.config.max_target_positions-1)
                        except RuntimeError:
                            incomplete+=1
                            continue
                        decoded=tokenizer.batch_decode([generated_sequence], skip_special_tokens=True, clean_up_tokenization_spaces=True)
                        candidate=require_translation_text(postprocess_candidate(module,text,call['source'],call['target'],decoded))
                        if candidate not in candidates:
                            candidates.append(candidate)
                    response.update(ok=True,candidates=candidates,input_tokens=count,
                                    rejected_incomplete=incomplete,recipe='beam5-length-penalty0',human_review_required=True)
                else:
                    require_finished(tokens, tokenizer, 'IndicTrans2', model.config.max_target_positions-1)
                    decoded = tokenizer.batch_decode(tokens, skip_special_tokens=True, clean_up_tokenization_spaces=True)
                    translated = require_translation_text(processor.postprocess_batch(decoded, lang='hin_Deva')[0])
                    response.update(ok=True, translation=translated, input_tokens=count,
                                    output_tokens=int(tokens.shape[-1]), ended_with_eos=True)
            except Exception:
                response['error'] = traceback.format_exc()[-6000:]
            faulthandler.cancel_dump_traceback_later()
            pending = request.with_suffix('.response.tmp')
            pending.write_text(json.dumps(response, ensure_ascii=False), encoding='utf-8')
            os.replace(pending, request.with_suffix('.response.json'))
            last = sequence
        time.sleep(.05)


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if request['operation'] != 'indictrans2_session':
        raise ValueError('Unsupported IndicTrans2 operation')
    session(request['params'])
