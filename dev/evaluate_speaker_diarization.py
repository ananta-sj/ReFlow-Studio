"""Approved local Community-1 evaluation; never enables a production route."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ.update(PYANNOTE_METRICS_ENABLED='0', HF_HUB_DISABLE_TELEMETRY='1',
                  OMP_NUM_THREADS='2')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--device', choices=('cpu', 'cuda:0'), default='cuda:0')
    args = parser.parse_args()
    folder = ROOT/'runtime_profiles/speaker-diarization'
    if Path(sys.executable).resolve() != (folder/'python.exe').resolve():
        raise RuntimeError('Use only the isolated speaker evaluation interpreter')
    if (folder/'.owner').read_text() != 'reflow.speaker-evaluation.v1':
        raise RuntimeError('Unexpected speaker runtime')
    model = ROOT/'models/speaker-diarization/community-1'
    from huggingface_hub import get_token, snapshot_download
    if args.download:
        token = get_token()
        if not token:
            raise RuntimeError('A private local Hugging Face login is required; do not send tokens in chat')
        snapshot_download('pyannote/speaker-diarization-community-1', local_dir=str(model), token=token)
        token = None
    if not (model/'config.yaml').is_file():
        raise RuntimeError('Community-1 model weights have not been downloaded')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', REFLOW_OFFLINE='1')
    def offline(event, details):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('Speaker evaluation runs offline after the approved model download')
    sys.addaudithook(offline)
    # Initialize pandas' native datetime API before Lightning's lazy optional
    # imports can re-enter pandas through the metrics dependency graph.
    import pandas
    import torch
    from pydub import AudioSegment
    import numpy as np
    from pyannote.audio import Pipeline
    torch.set_num_threads(2)
    torch.manual_seed(0)
    if args.device == 'cuda:0' and (not torch.cuda.is_available() or torch.cuda.mem_get_info()[0] < 3*1024**3):
        raise RuntimeError('Free at least 3 GB of NVIDIA memory, or explicitly choose --device cpu')
    clip = AudioSegment.from_wav(args.audio).set_channels(1).set_frame_rate(16000).set_sample_width(2)
    samples = np.asarray(clip.get_array_of_samples(), dtype=np.float32)/32768
    started = time.monotonic()
    pipeline = Pipeline.from_pretrained(str(model))
    pipeline.segmentation_batch_size = 8
    pipeline.embedding_batch_size = 8
    pipeline.to(torch.device(args.device))
    diagnostics = {}
    def observe(step, artifact, **kwargs):
        if step == 'embeddings' and artifact is not None:
            values = np.asarray(artifact)
            diagnostics.update(embedding_shape=list(values.shape),
                finite_embedding_fraction=float(np.isfinite(values).mean()))
    output = pipeline(dict(waveform=torch.from_numpy(samples)[None, :], sample_rate=16000), hook=observe)
    turns = [dict(start=float(turn.start), end=float(turn.end), speaker=label)
             for turn, _, label in output.exclusive_speaker_diarization.itertracks(yield_label=True)]
    if not turns or any(row['start'] < 0 or row['end'] <= row['start'] or row['end'] > len(clip)/1000+.05 for row in turns):
        raise RuntimeError('Speaker detector returned invalid or empty source turns')
    result = dict(model='pyannote/speaker-diarization-community-1', device=args.device,
                  audio=str(args.audio.resolve()), audio_seconds=len(clip)/1000,
                  speakers=len({row['speaker'] for row in turns}), turns=turns,
                  elapsed_seconds=round(time.monotonic()-started, 2), human_quality_accepted=False,
                  production_route_enabled=False, diagnostics=diagnostics)
    destination = ROOT/'outputs'/('speaker-diarization-'+args.audio.stem+'.json')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
