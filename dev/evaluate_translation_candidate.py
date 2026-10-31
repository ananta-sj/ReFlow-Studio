"""Actual approved runtime imports/tokenizer checks; no model downloads."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CODE=r'''
import importlib,importlib.metadata as metadata,json,os,sys
from pathlib import Path
root,scratch=Path(sys.argv[1]),Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='2',HF_HOME=str(scratch/'hf'))
def offline(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:raise RuntimeError('Translation runtime acceptance forbids networking')
sys.addaudithook(offline)
report=dict(passed=False,checks={},models_downloaded=False)
def check(name,value):
    report['checks'][name]=bool(value);print(name,bool(value),flush=True)
    if not value:raise AssertionError(name)
try:
    from packaging.utils import canonicalize_name
    plan=json.loads((root/'docs/validation/2026-10-16-m2m100-runtime-proposal.json').read_text())
    actual={}
    for dist in metadata.distributions():
        name=canonicalize_name(dist.metadata['Name'])
        check('unique_'+name,name not in actual);actual[name]=dist.version
    check('exact_41_package_closure',actual=={row['name']:row['version'] for row in plan['packages']})
    check('python_31316',sys.version_info[:3]==(3,13,16))
    profile=root/'runtime_profiles/translation-candidate'
    for name in ['torch','transformers','sentencepiece','tokenizers','safetensors','psutil','requests']:
        module=importlib.import_module(name)
        check('origin_'+name,Path(module.__file__).resolve().is_relative_to(profile))
    import torch,sentencepiece
    torch.set_num_threads(2)
    check('cpu_arithmetic',bool(torch.all(torch.ones((2,2))@torch.ones((2,2))==2)))
    check('cpu_torch_version',torch.__version__=='2.14.1+cpu')
    from transformers import M2M100Tokenizer,M2M100ForConditionalGeneration
    model=root/'models/translation/m2m100_418M'
    tokenizer=M2M100Tokenizer.from_pretrained(str(model),local_files_only=True)
    for code in ['en','hi','fr']:
        check('real_language_token_'+code,type(tokenizer.get_lang_id(code)) is int and tokenizer.get_lang_id(code)!=tokenizer.unk_token_id)
    processor=sentencepiece.SentencePieceProcessor(model_file=str(model/'sentencepiece.bpe.model'))
    encoded=processor.encode('Hello world.',out_type=int)
    check('sentencepiece_round_trip',bool(encoded) and processor.decode(encoded)=='Hello world.')
    report['passed']=all(report['checks'].values())
except BaseException as error:
    import traceback
    report.update(error=repr(error),traceback=traceback.format_exc())
finally:
    (root/'docs/validation/2026-10-16-translation-candidate-native.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
raise SystemExit(not report['passed'])
'''


def main():
    with tempfile.TemporaryDirectory(prefix='translation-native-',dir=ROOT/'temp') as scratch:
        with (ROOT/'docs/validation/2026-10-16-translation-candidate-native.log').open('wb') as log:
            result=subprocess.run([str(ROOT/'runtime_profiles/translation-candidate/python.exe'),'-B','-X','utf8',
                '-c',CODE,str(ROOT),scratch],stdout=log,stderr=subprocess.STDOUT,timeout=240,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('Translation runtime acceptance exit:',result.returncode)
    return result.returncode


if __name__=='__main__':raise SystemExit(main())
