"""Offline Community-1 inference, using decoded waveforms rather than native codecs."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]
os.environ.update(PYANNOTE_METRICS_ENABLED='0', HF_HUB_DISABLE_TELEMETRY='1',
    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', REFLOW_OFFLINE='1', OMP_NUM_THREADS='2')


def unpadded_embeddings(embedding, plans):
    for cue_id,clip in plans:
        yield cue_id, embedding(clip[None,:,:])


def detect(audio_path, device, route, cues_path=None, reference_audio_path=None):
    def offline(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            raise RuntimeError('The local speaker detector cannot use the network')
    sys.addaudithook(offline)
    import pandas  # Initialize native datetime API before Lightning's lazy imports.
    import torch
    import numpy as np
    import soundfile
    from torchaudio.functional import resample
    from pyannote.audio import Pipeline
    if device == 'cuda:0' and (not torch.cuda.is_available() or torch.cuda.mem_get_info()[0] < 3*1024**3):
        raise RuntimeError('Speaker detection needs 3 GB of free RTX memory; free memory and Retry, or select CPU for a new run.')
    if device not in ('cpu', 'cuda:0'):
        raise ValueError('Unsupported speaker device')
    torch.set_num_threads(2)
    torch.manual_seed(0)
    samples, native_rate = soundfile.read(audio_path, dtype='float32', always_2d=True)
    duration = len(samples)/native_rate
    waveform = torch.from_numpy(samples.T).mean(dim=0, keepdim=True)
    if native_rate != 16000:
        waveform = resample(waveform, native_rate, 16000)
    started = time.monotonic()
    pipeline = Pipeline.from_pretrained(route['model'])
    pipeline.segmentation_batch_size = 8
    pipeline.embedding_batch_size = 8
    pipeline.to(torch.device(device))
    result = pipeline(dict(waveform=waveform, sample_rate=16000))
    cue_embeddings = []
    if cues_path:
        cues = json.loads(Path(cues_path).read_text(encoding='utf-8'))
        from core.transcription import require_media_bounds
        require_media_bounds(cues, duration)
        clean = waveform
        if reference_audio_path:
            values, rate = soundfile.read(reference_audio_path, dtype='float32', always_2d=True)
            if abs(len(values)/rate-duration) > .05:
                raise ValueError('Reference audio is not aligned with the source')
            clean = torch.from_numpy(values.T).mean(dim=0, keepdim=True)
            if rate != 16000:
                clean = resample(clean, rate, 16000)
        plans = []
        for cue in cues:
            start, end = round(cue['start']*16000), round(cue['end']*16000)
            if end-start >= 10400:
                plans.append((cue['cue_id'], clean[:,start:min(end,start+96000)]))
        # WeSpeaker normalizes filterbanks over the complete waveform before
        # its pooling mask. Zero-padding variable clips changes their voice
        # vectors even when the padding has zero pooling weight. Keep the
        # actual duration; a cue's identity must not depend on its batch mates.
        for cue_id,embeddings in unpadded_embeddings(pipeline._embedding,plans):
            calibrated = pipeline._plda(embeddings)
            for vector, transformed in zip(embeddings,calibrated):
                norm = np.linalg.norm(vector)
                transformed_norm = np.linalg.norm(transformed)
                if np.isfinite(vector).all() and norm > 0 and np.isfinite(transformed).all() and transformed_norm > 0:
                    cue_embeddings.append(dict(cue_id=cue_id,vector=(vector/norm).tolist(),raw_norm=float(norm),
                        calibrated_vector=(transformed/transformed_norm).tolist()))
    def turns(annotation):
        return [dict(start=float(turn.start), end=float(turn.end), speaker=label)
                for turn, _, label in annotation.itertracks(yield_label=True)]
    return dict(device=device, audio_seconds=duration,
                turns=turns(result.exclusive_speaker_diarization),
                overlapping_turns=turns(result.speaker_diarization),
                cue_embeddings=cue_embeddings,
                elapsed_seconds=round(time.monotonic()-started, 2))


def main():
    from core.diarization_runtime import validate
    from core.render_context import check_cancelled
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--device', choices=('cpu', 'cuda:0'), default='cuda:0')
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--cues', type=Path)
    parser.add_argument('--reference-audio', type=Path)
    args = parser.parse_args()
    route = validate(candidate=args.probe)
    if Path(sys.executable).resolve() != Path(route['executable']).resolve():
        raise RuntimeError('Wrong speaker interpreter')
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'temp/jobs').resolve()):
        raise ValueError('Speaker output must belong to a render job')
    result = detect(args.audio, args.device, route, args.cues, args.reference_audio)
    check_cancelled()
    result['identity'] = route['identity']
    pending = output.with_suffix('.pending')
    pending.write_text(json.dumps(result, allow_nan=False), encoding='utf-8')
    pending.replace(output)


if __name__ == '__main__':
    main()
