"""Minimal SRT read/write - no external dependency needed for a format
this simple. Powers the subtitle_translate pipeline template (subtitle
file in -> translate each cue -> subtitle file out, skipping STT/TTS/video
entirely) in core/pipeline.py.
"""

import re

_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
_BLOCK_RE = re.compile(
    r"\d+\s*\n(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _parse_timestamp(ts: str) -> float:
    match = _TIME_RE.fullmatch(ts)
    if not match:
        raise ValueError('Invalid subtitle timestamp: ' + ts)
    h, m, s, ms = match.groups()
    if int(m) >= 60 or int(s) >= 60:
        raise ValueError('Invalid subtitle timestamp: ' + ts)
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: str) -> list[dict]:
    """Returns [{"start": float, "end": float, "text": str}, ...] - the
    same segment shape core/pipeline.py already uses for a transcript, so
    it can be translated with the exact same code path."""
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read().replace("\r\n", "\n")

    segments = []
    if not content.strip():
        return segments
    for cue, block in enumerate(re.split(r'\n[ \t]*\n', content.strip()), 1):
        lines = block.splitlines()
        if len(lines) < 3 or not re.fullmatch(r'\d+', lines[0].strip()):
            raise ValueError(f'Subtitle cue {cue}: expected index, timestamps and text')
        timing = re.fullmatch(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})', lines[1].strip())
        if not timing:
            raise ValueError(f'Subtitle cue {cue}: invalid timing line')
        start_ts, end_ts = timing.groups()
        start, end = _parse_timestamp(start_ts), _parse_timestamp(end_ts)
        text = '\n'.join(lines[2:]).strip()
        if end <= start or not text:
            raise ValueError(f'Subtitle cue {cue}: invalid interval or empty text')
        segments.append({
            "start": start,
            "end": end,
            "text": text,
        })
    return segments
