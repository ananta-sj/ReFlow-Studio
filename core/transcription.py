"""List-compatible transcription results with optional source metadata.

Use to_payload() at JSON boundaries: JSON encoders treat list subclasses
as lists and would otherwise omit their metadata attributes.
"""

import logging
import math


class TranscriptionResult(list):
    def __init__(self, segments, language=None, language_probability=None, language_origin=None):
        if not isinstance(segments, list):
            raise ValueError("Transcription segments must be a list.")
        if any(not isinstance(segment, dict) or not {"start", "end", "text"} <= segment.keys()
               for segment in segments):
            raise ValueError("Transcription segments require start, end, and text fields.")
        super().__init__(dict(segment) for segment in segments)
        if language is not None and (not isinstance(language, str) or not language.strip()):
            logging.warning("Ignoring invalid transcription language metadata.")
            language = None
        self.language = language.strip() if language is not None else None
        if language_probability is not None and (
            isinstance(language_probability, bool)
            or not isinstance(language_probability, (int, float))
            or not 0 <= language_probability <= 1
            or not math.isfinite(language_probability)
        ):
            logging.warning("Ignoring invalid transcription language probability metadata.")
            language_probability = None
        # A probability without a language cannot describe a source language.
        if language_origin not in (None, 'hint'):
            raise ValueError('Invalid transcription language origin.')
        self.language_origin = language_origin
        self.language_probability = (language_probability if self.language and language_origin != 'hint' else None)

    def to_payload(self):
        payload = {"segments": [dict(segment) for segment in self],
                   "language": self.language, "language_probability": self.language_probability}
        if self.language_origin is not None:
            payload['language_origin'] = self.language_origin
        return payload

    def with_segments(self, segments):
        """Retain source metadata when segmentation/text changes downstream."""
        return TranscriptionResult(segments, self.language, self.language_probability, self.language_origin)


def normalize_transcription(value):
    """Accept the new envelope and legacy lists without inventing a language."""
    if isinstance(value, TranscriptionResult):
        return value.with_segments(value)
    if isinstance(value, list):
        return TranscriptionResult(value)
    if isinstance(value, dict) and "segments" in value:
        return TranscriptionResult(value["segments"], value.get("language"),
                                   value.get("language_probability"), value.get('language_origin'))
    raise ValueError("Transcription response must contain a segment list or a segments envelope.")


def require_media_bounds(segments, duration):
    """Reject provider timestamps outside the actual decoded source."""
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Transcription source duration must be finite and positive')
    for index, segment in enumerate(segments):
        start, end = segment.get('start'), segment.get('end')
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (start, end)):
            raise ValueError(f'Transcription segment {index + 1} has invalid timestamps')
        if start < 0 or end <= start or end > duration + .05:
            raise ValueError(f'Transcription segment {index + 1} falls outside the source duration ({duration:.3f}s)')
    return segments


def require_spoken_transcription(value):
    """Keep lexical Unicode speech; punctuation alone is not a spoken cue.

    Raw recognizer evidence remains with the provider. This is not a VAD,
    semantic correctness test or a filter for every hallucinated phrase.
    """
    result = normalize_transcription(value)
    spoken = []
    for segment in result:
        text = segment.get('text')
        if not isinstance(text, str):
            raise ValueError('Recognition returned invalid speech text.')
        if any(character.isalnum() for character in text):
            spoken.append(segment)
    if not spoken:
        raise ValueError('No spoken words were recognized. Check the source audio or choose another clip.')
    return result.with_segments(spoken)
