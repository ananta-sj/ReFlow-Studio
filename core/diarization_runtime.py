"""Read-only validation of the explicitly approved local speaker runtime."""
import json
from pathlib import Path
from core.python_runtime import project_root
from core.runtime_integrity import sha, digest, safe_path


def validate(candidate=False):
    root = project_root()
    folder = safe_path(root/'runtime_profiles/speaker-diarization')
    try:
        profile = json.loads((folder/'profile.json').read_text(encoding='utf-8'))
        if (folder/'.owner').read_text() != 'reflow.speaker-evaluation.v1':
            raise ValueError('Unrecognized speaker runtime')
        if (folder/'python313._pth').read_text() != profile['pth']:
            raise ValueError('Speaker import paths changed')
        if {name:sha(folder/name) for name in profile['bootstrap']} != profile['bootstrap']:
            raise ValueError('Speaker interpreter changed')
        from email.parser import Parser
        packages = {}
        for path in sorted((folder/'Lib/site-packages').glob('*.dist-info/METADATA')):
            headers = Parser().parsestr(path.read_text(encoding='utf-8'))
            packages[headers['Name'].lower().replace('_', '-')] = headers['Version']
        expected = {key.lower().replace('_', '-'):version for key,version in profile['installed'].items()}
        if packages != expected:
            raise ValueError('Speaker dependency versions changed')
        from core.cuda_runtime import validate as cuda
        base = cuda('speech')['identity']
        from core.stage_checkpoints import tree_identity
        model = safe_path(root/'models/speaker-diarization/community-1')
        identity = digest(dict(bootstrap=profile['bootstrap'], packages=packages, base=base,
            model=tree_identity(model, {'.yaml', '.bin', '.npz', '.npy', '.safetensors'}),
            sources={name:sha(root/name) for name in ('core/diarization_runtime.py',
                     'core/diarization_worker.py')}))
        if not candidate and profile.get('speaker_probe', {}).get('identity') != identity:
            raise ValueError('The dedicated speaker model needs its local verification test')
        return dict(executable=str(folder/'python.exe'), model=str(model), identity=identity)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError('Speaker detector unavailable: '+str(error)) from error
