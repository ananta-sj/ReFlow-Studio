"""Shared native generation budget; defaults preserve accepted calibration."""
import math
import re


def segment_text(text,continuous_utterance=False):
    if type(continuous_utterance) is not bool:
        raise ValueError('IndicF5 continuous utterance option must be a boolean.')
    if not isinstance(text,str) or not text.strip() or len(text)>4000:
        raise ValueError('IndicF5 needs 1–4000 characters of nonblank speech text.')
    text=text.strip()
    parts=[text] if continuous_utterance else [part.strip() for part in re.findall(r'[^।!?]+[।!?]?',text) if part.strip()]
    if not parts or len(parts)>128 or ''.join(parts).replace(' ','')!=text.replace(' ',''):
        raise ValueError('IndicF5 sentence segmentation changed text or exceeds limits.')
    return parts


def validate_minimum_sentence_seconds(value):
    if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not .1 <= value <= 5):
        raise ValueError('IndicF5 minimum sentence duration must be 0.1–5 finite seconds.')
    return value


def sentence_hops(sentence,profile,rate=24000,minimum_sentence_seconds=None):
    floor=validate_minimum_sentence_seconds(minimum_sentence_seconds)
    seconds=profile['calibration_seconds']*len(sentence.encode('utf-8'))/len(profile['calibration_text'].encode('utf-8'))
    hops=max(1,round(seconds*rate/256))
    if floor is not None:
        hops=max(hops,math.ceil(floor*rate/256))
    return hops
