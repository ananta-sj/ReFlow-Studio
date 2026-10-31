"""Common comparison inputs; editorial Hindi is not an automatic gold score."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_cases():
    video = json.loads((ROOT / 'docs/validation/2026-10-06-indicf5-video-cues-9fce0cd4.json').read_text(encoding='utf-8'))
    cases = [dict(id='video-'+str(i+1), source=row['text']) for i,row in enumerate(video['source_cues'])]
    cases += json.loads((ROOT / 'dev/translation_quality_cases.json').read_text(encoding='utf-8'))
    cases += [dict(id='held-out-apology', source="I'm sorry, I didn't mean to interrupt you. Please go on."),
              dict(id='held-out-reassurance', source="Don't worry. We still have enough time to fix this."),
              dict(id='held-out-phone', source='Call +91-9876543210 at 10:30.')]
    return cases
