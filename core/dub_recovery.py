"""Conservative source preservation for automatic video dubbing."""
import re


def _beat(clip):
    import numpy as np

    mono = clip.set_channels(1).set_frame_rate(4000)
    samples = np.asarray(mono.get_array_of_samples(), dtype=float)
    frames = samples[:len(samples)//40*40].reshape(-1, 40)
    energy = np.log1p(np.sqrt(np.mean(np.diff(frames, axis=1)**2, axis=1)))
    onsets = np.maximum(0, np.diff(energy))
    onsets -= onsets.mean()
    corr = np.correlate(onsets, onsets, 'full')[len(onsets)-1:]
    corr /= max(corr[0], 1e-9)
    lag = int(np.argmax(corr[34:82])) + 34
    return lag, corr[lag], corr[2*lag]


def music_cues(transcript, background, source_language):
    """Keep explicit singing cues, plus a narrowly detected Japanese opening."""
    preserved = {i: 'marked_singing' for i, cue in enumerate(transcript)
                 if re.fullmatch(r'\s*(?:[♪♫].*|\[(?:singing|song|music)\])\s*',
                                 cue['text'], flags=re.I)}
    if source_language != 'ja' or background is None or not transcript or transcript[0]['start'] > 5:
        return preserved

    # Require a sustained, consistent beat in the accompaniment from the
    # start. Music underneath ordinary dialogue is not enough by itself.
    last, harmonics, tempo = None, 0, None
    for start in range(0, min(100_000, len(background)-16_000), 10_000):
        window = background[start:start+16_000]
        if window.dBFS < -42:
            break
        lag, strength, harmonic = _beat(window)
        if strength < .075 or (tempo is not None and abs(lag-tempo) > 1):
            break
        if tempo is None:
            tempo = lag
        harmonics += harmonic >= .08
        last = start+16_000
    if last is None or last < 56_000 or harmonics < 3:
        return preserved

    prefix = []
    for i, cue in enumerate(transcript):
        duration = cue['end']-cue['start']
        if (cue['end']*1000 > last or duration < 3.5
                or sum(char.isalnum() for char in cue['text']) > 3*duration
                or re.search(r'[?？!！「」]', cue['text'])
                or (prefix and cue['start']-transcript[i-1]['end'] > 2)):
            break
        prefix.append(i)
    if len(prefix) >= 4 and transcript[prefix[-1]]['end']-transcript[0]['start'] >= 35:
        preserved.update(dict.fromkeys(prefix, 'likely_opening_song'))
    return preserved


def restore_source_ranges(mix, source, ranges):
    """Replace covered intervals with the original mix, blending the edges."""
    from pydub import AudioSegment

    mix, source = AudioSegment._sync(mix, source)
    merged = []
    for start, end in sorted(ranges):
        start = max(0, round(start*1000))
        end = min(len(mix), len(source), round(end*1000))
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    pieces = []
    cursor = 0
    for start, end in merged:
        pieces.append(mix[cursor:start].raw_data)
        original = source[start:end]
        fade = min(20, (end-start)//3)
        if fade:
            if start:
                pieces.append(mix[start:start+fade].fade_out(fade).overlay(original[:fade].fade_in(fade)).raw_data)
            else:
                pieces.append(original[:fade].raw_data)
            pieces.append(original[fade:-fade].raw_data)
            if end < len(mix):
                pieces.append(mix[end-fade:end].fade_in(fade).overlay(original[-fade:].fade_out(fade)).raw_data)
            else:
                pieces.append(original[-fade:].raw_data)
        else:
            pieces.append(original.raw_data)
        cursor = end
    pieces.append(mix[cursor:].raw_data)
    return mix._spawn(b''.join(pieces))
