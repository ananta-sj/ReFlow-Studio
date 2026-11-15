"""Local, reference-based source speaker matching for cue review."""
import math


MIN_SIMILARITY = .50
MIN_MARGIN = .15
MIN_VOICED_MS = 650


def speech_excerpt(audio):
    """Keep a usable source excerpt, without concatenating across pauses."""
    from pydub.silence import detect_nonsilent

    if len(audio) < MIN_VOICED_MS or not math.isfinite(audio.dBFS) or audio.dBFS < -48:
        return None
    ranges = detect_nonsilent(audio, min_silence_len=150, silence_thresh=max(-50, audio.dBFS-17))
    if sum(end-start for start, end in ranges) < MIN_VOICED_MS:
        return None
    return audio[max(0, ranges[0][0]-30):ranges[-1][1]+40]


def load_encoder(model, device='cpu'):
    """Load just the installed XTTS speaker encoder. Checkpoint metadata stays inert."""
    import torch
    from TTS.tts.layers.xtts.hifigan_decoder import ResNetSpeakerEncoder

    class ConfigData:
        pass

    metadata = [
        'TTS.config.shared_configs.BaseDatasetConfig',
        'TTS.tts.models.xtts.XttsAudioConfig',
        'TTS.tts.models.xtts.XttsArgs',
        'TTS.tts.configs.xtts_config.XttsConfig',
    ]
    if not model.is_file():
        raise ValueError('Character matching needs an installed XTTS model.')
    with torch.serialization.safe_globals([(ConfigData, name) for name in metadata]):
        weights = torch.load(model, map_location='cpu', weights_only=True, mmap=True)['model']
    prefix = 'hifigan_decoder.speaker_encoder.'
    state = {key[len(prefix):]: value for key, value in weights.items() if key.startswith(prefix)}
    encoder = ResNetSpeakerEncoder(log_input=True, use_torch_spec=True, audio_config=dict(
        fft_size=512, win_length=400, hop_length=160, sample_rate=16000, preemphasis=.97, num_mels=64))
    encoder.load_state_dict(state)
    encoder.to(device)
    encoder.eval()

    def encode(audio):
        import numpy as np
        pcm = audio.set_channels(1).set_sample_width(2).set_frame_rate(16000)
        samples = np.asarray(pcm.get_array_of_samples(), dtype=np.float32) / 32768
        with torch.inference_mode():
            return encoder(torch.from_numpy(samples)[None, None, :].to(device), l2_norm=True)[0].cpu().numpy()

    return encode


def identify(embedding, references):
    """Return a label only when the reference match is both strong and distinct."""
    import numpy as np
    scores = []
    for label, refs in references.items():
        score = max(float(np.dot(embedding, ref)) for ref in refs)
        if len(refs) > 1:
            center = np.mean(refs, axis=0)
            norm = np.linalg.norm(center)
            if norm > 0:
                score = max(score, float(np.dot(embedding, center/norm)))
        scores.append((label, score))
    if len(scores) < 2 or not all(math.isfinite(score) for _, score in scores):
        return None
    scores.sort(key=lambda item: item[1], reverse=True)
    label, score = scores[0]
    if score < MIN_SIMILARITY or score-scores[1][1] < MIN_MARGIN:
        return None
    return label


def match_excerpt(clip, encode, references):
    if clip is None:
        return None, 'insufficient_speech'
    label = identify(encode(clip[:6000]), references)
    if label is None:
        return None, 'ambiguous'
    # A cue can span a speaker handoff even when the transcript has no overlap.
    if len(clip) >= 2400:
        middle = len(clip)//2
        for part in (clip[:middle], clip[middle:]):
            speech = speech_excerpt(part)
            other = identify(encode(speech[:6000]), references) if speech is not None else None
            if other is not None and other != label:
                return None, 'mixed_speakers'
    return label, 'matched'
