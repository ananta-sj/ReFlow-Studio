"""Use the installed XTTS encoder without loading the speech synthesizer."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]

if __name__ == '__main__':
    request_path = Path(sys.argv[1]).resolve()
    if not request_path.is_relative_to((ROOT/'temp/jobs').resolve()):
        raise ValueError('Unowned speaker analysis request')
    params = json.loads(request_path.read_text(encoding='utf-8'))
    folder = Path(params['folder']).resolve()
    if folder != request_path.parent:
        raise ValueError('Unowned speaker output folder')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', REFLOW_OFFLINE='1')
    from core.render_context import check_cancelled
    def offline(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('Speaker matching is offline')
    sys.addaudithook(offline)
    if params['device'] == 'cuda:0':
        from core.cuda_runtime import validate
        route = validate('speech')
        from core.cuda_xtts_compat import activate
    else:
        from core.xtts_runtime import validate
        route = validate()
        from core.xtts_compat import activate
    if Path(sys.executable).resolve() != Path(route['executable']).resolve():
        raise ValueError('Unexpected speaker analysis interpreter')
    activate()
    import torch
    torch.set_num_threads(2)
    from core.speaker_matching import load_encoder
    from core.batch_speakers import analyze
    encode = load_encoder(Path(params['model_path'])/'model.pth', device=params['device'])
    result = analyze(params['audio_path'], params['cues'], folder, encode)
    check_cancelled()
    (folder/'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
