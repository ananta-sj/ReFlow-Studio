"""Conservative acoustic measurements for source-aware cue review."""
import math


def speech_ranges(clip, *, source=False):
    from pydub.silence import detect_nonsilent

    if not math.isfinite(clip.dBFS):
        return []
    threshold = max(-47, clip.dBFS-12) if source else min(-39, clip.dBFS-15)
    return detect_nonsilent(clip, min_silence_len=135, silence_thresh=threshold)


def median_pitch(clip):
    """Estimate F0 from periodic voiced frames, or return None if evidence is weak."""
    import numpy as np

    mono = clip.set_channels(1).set_sample_width(2).set_frame_rate(8000)
    samples = np.asarray(mono.get_array_of_samples(), dtype=np.float64) / 32768
    lag = np.arange(11, 102)
    pitches = []
    for start in range(0, len(samples)-400+1, 200):
        frame = samples[start:start+400]
        frame = frame-frame.mean()
        if np.mean(frame**2) < 1e-6:
            continue
        power = np.concatenate(([0.], np.cumsum(frame**2)))
        corr = np.fft.irfft(abs(np.fft.rfft(frame, n=1024))**2, n=1024)[lag]
        scale = np.sqrt(power[400-lag] * (power[400]-power[lag]))
        scores = corr / np.maximum(scale, 1e-12)
        peaks = np.flatnonzero((scores[1:-1] > scores[:-2]) & (scores[1:-1] >= scores[2:]))+1
        if not len(peaks):
            continue
        strongest = scores[peaks].max()
        choices = peaks[scores[peaks] >= max(.70, strongest*.90)]
        if len(choices):
            pitch = 8000/lag[choices[0]]
            if 80 <= pitch <= 650:
                pitches.append(pitch)
    if len(pitches) < 5:
        return None
    pitch = float(np.median(pitches))
    central = sum(.72*pitch <= value <= 1.39*pitch for value in pitches)
    return round(pitch) if central >= .65*len(pitches) else None


def measure(clip, *, pitch=False, source=False):
    ranges = speech_ranges(clip, source=source)
    if not ranges or sum(end-start for start, end in ranges) < 110:
        return None
    first, last = ranges[0][0], ranges[-1][1]
    return dict(start=first, end=last, level=clip[first:last].dBFS,
                pauses=[(left[1], right[0]) for left, right in zip(ranges, ranges[1:])
                        if right[0]-left[1] >= 240],
                pitch=median_pitch(clip[first:last]) if pitch else None)


def shape_take(clip, source=None, *, compare_pitch=False):
    """Align measured speech onsets and use gentle gain/edge changes at native speed."""
    spoken = measure(clip, pitch=compare_pitch)
    offset = 0
    evidence = {}
    if spoken is None:
        return clip, offset, evidence, 'delivery_uncertain' if source else None

    left = max(0, spoken['start']-45)
    clip = clip[left:spoken['end']+65]
    delay = spoken['start']-left
    if source:
        offset = max(0, source['start']-delay)
        # Track the original line-to-line level without burying soft replies or
        # boosting a separated track into clipping.
        target = max(-34., min(-19., source['level']+4))
        gain = min(max(-10., min(4., target-spoken['level'])), -2-clip.max_dBFS)
        clip = clip.apply_gain(gain)
        difference = offset + spoken['end'] - left - source['end']
        source_span = source['end']-source['start']
        evidence.update(source_onset_ms=source['start'], source_end_ms=source['end'],
                        end_delta_ms=difference, source_pitch_hz=source['pitch'],
                        take_pitch_hz=spoken['pitch'])
        pauses = [(offset+a-left, offset+b-left) for a,b in spoken['pauses']]
        missing_pause = any(not any(min(end, b)-max(start, a) >= 120 for a,b in pauses)
                            for start,end in source['pauses'])
        pitch_far = (source['pitch'] and spoken['pitch']
                     and abs(12*math.log2(spoken['pitch']/source['pitch'])) >= 8)
        review = (difference > 240 or difference < -max(320, .27*source_span)
                  or missing_pause or pitch_far)
    else:
        review = False

    # Use padding for the ramps where possible, preserving quiet consonants.
    attack = min(10, len(clip)//5)
    release = min(28, len(clip)//4)
    if attack and release:
        clip = clip.fade_in(attack).fade_out(release)
    return clip, offset, evidence, 'delivery_uncertain' if review else None
