"""Run actual arithmetic/import/audio checks inside the isolated candidate."""
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import argparse

ROOT=Path(__file__).resolve().parents[1]
PROFILE=ROOT/'runtime_profiles/xtts-candidate'
OUT=ROOT/'docs/validation'

def main():
    global PROFILE
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='initial')
    parser.add_argument('--profile',choices=['xtts-candidate','xtts-security-candidate'],default='xtts-candidate')
    args=parser.parse_args()
    PROFILE=ROOT/'runtime_profiles'/args.profile
    assert args.label.replace('-','').isalnum()
    assert Path(sys.executable).resolve()==(PROFILE/'python.exe').resolve()
    lock=json.loads((OUT/('2026-10-13-xtts-security-cpu-lock-review.json' if args.profile=='xtts-security-candidate' else '2026-10-13-xtts-candidate-lock-review.json')).read_text(encoding='utf-8'))
    caches=tempfile.TemporaryDirectory(prefix=args.profile+'-probe-cache-',dir=ROOT/'temp')
    cache_root=Path(caches.name)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',REFLOW_OFFLINE='1',
        OMP_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',HF_HOME=str(cache_root/'hf'),
        TORCH_HOME=str(cache_root/'torch'),TTS_HOME=str(cache_root/'tts'),MPLCONFIGDIR=str(cache_root/'matplotlib'),
        NUMBA_CACHE_DIR=str(cache_root/'numba'),TEMP=str(cache_root),TMP=str(cache_root))
    connections=[]
    def offline(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
            import traceback
            connections.append(dict(event=event,address=repr(args[1:]),blocked=True,
                stack=traceback.format_stack(limit=8)))
            raise RuntimeError('Candidate verification forbids network operations')
    sys.addaudithook(offline)
    report=dict(passed=False,python=sys.version,executable=sys.executable,
                release_eligible=False,network_attempts=connections,model_loaded=False,
                paths=sys.path,checks={},errors=[])
    started=time.monotonic()
    try:
        from packaging.utils import canonicalize_name
        from packaging.requirements import Requirement
        distributions={}
        for distribution in metadata.distributions():
            name=canonicalize_name(distribution.metadata['Name'])
            distributions.setdefault(name,[]).append(distribution)
        report['checks']['no_duplicate_distribution_records']=all(len(v)==1 for v in distributions.values())
        expected={r['name']:r for r in lock['packages']}
        report['checks']['exact_locked_package_set']=set(distributions)==set(expected)
        report['checks']['versions_match_lock']=all(name in distributions and distributions[name][0].version==row['version'] for name,row in expected.items())
        report['checks']['distribution_origins_isolated']=all(Path(d.locate_file('')).resolve().is_relative_to(PROFILE.resolve()) for ds in distributions.values() for d in ds)
        problems=[]
        for edge in lock['edges']:
            req=Requirement(edge['requirement']); name=canonicalize_name(req.name)
            if name not in distributions or distributions[name][0].version not in req.specifier:
                problems.append(edge)
        report['checks']['active_target_dependencies_satisfied']=not problems
        report['dependency_problems']=problems
        origins={}
        handles=[]
        for name in ['torch','numpy','scipy','numba','soundfile','pydub','transformers','docopt','librosa','TTS.api']:
            if name=='TTS.api' and args.profile=='xtts-security-candidate':
                sys.path.insert(0,str(ROOT))
                from dev.xtts_security_compat import activate
                report['compatibility_adapter']=activate()
            module=importlib.import_module(name)
            origins[name]=dict(file=module.__file__,version=getattr(module,'__version__',None))
            assert Path(module.__file__).resolve().is_relative_to(PROFILE.resolve()),name
            if name=='torch':handles.append(os.add_dll_directory(str(ROOT/'ffmpeg/shared_libs')))
        report['imports']=origins
        report['checks']['engine_imports_isolated']=True
        import torch
        import numpy as np
        import soundfile as sf
        from torchcodec.decoders import AudioDecoder
        x=torch.nn.functional.conv2d(torch.ones(1,1,8,8),torch.ones(1,1,3,3))
        report['checks']['torch_cpu_convolution']=tuple(x.shape)==(1,1,6,6) and bool(torch.all(x==9))
        report['checks']['cpu_build_selected']=torch.__version__==expected['torch']['version'] and torch.version.cuda is None
        with tempfile.TemporaryDirectory(prefix='xtts-candidate-probe-',dir=ROOT/'temp') as folder:
            wav=Path(folder)/'probe.wav'
            samples=np.sin(2*np.pi*440*np.arange(2400)/24000).astype('float32')*.2
            sf.write(wav,samples,24000,subtype='PCM_16')
            decoded=AudioDecoder(str(wav)).get_all_samples()
            report['checks']['torchcodec_real_audio_decoding']=decoded.sample_rate==24000 and decoded.data.numel()==2400 and float(decoded.data.abs().max())>.1
            from pydub import AudioSegment
            clip=AudioSegment.from_wav(wav)
            report['checks']['pydub_audioop_compatibility']=len(clip)==100 and clip.max>0
            from docopt import docopt
            report['checks']['docopt_python313_parser']=docopt('Usage: app [--quiet]',argv=['--quiet'])['--quiet'] is True
        report['checks']['all_network_operations_blocked']=all(row['blocked'] for row in connections)
        report['checks']['no_outbound_or_dns_attempts']=not any(row['event']!='socket.bind' for row in connections)
        report['checks']['supported_target_python']=sys.version_info[:3]==(3,13,16)
        report['passed']=all(report['checks'].values())
    except Exception as error:
        import traceback
        report['errors'].append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    finally:
        caches.cleanup()
        report['cache_workspace_removed']=not cache_root.exists()
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        name=f'2026-10-13-{args.profile}-runtime-probe.json' if args.label=='initial' else f'2026-10-13-{args.profile}-runtime-probe-{args.label}.json'
        destination=OUT/name
        assert not destination.exists(),'Preserve prior probe evidence'
        destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return not report['passed']

if __name__=='__main__':raise SystemExit(main())
