"""Timing/envelope evidence only; never infer semantic or listening acceptance."""
import json
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / 'docs/validation/2026-10-04-cue-review-runtime.json').read_text(encoding='utf-8'))
manifest_path = Path(receipt['manifest'])
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
reference = AudioSegment.from_file(manifest_path.parent / 'reference.wav')
report = dict(human_listening_performed=False, semantic_accuracy_verified=False,
              reference_seconds=len(reference)/1000, sampling_temperature=.75,
              generation_seed_recorded=False, cases=[])
for index, cue in enumerate(manifest['cues']):
    take = cue.get('candidate')
    if not take:
        continue
    audio = AudioSegment.from_file(manifest_path.parent / take['file'])
    row = dict(cue=index+1, speech_text=cue['text'], seconds=len(audio)/1000,
               window_seconds=cue['available_seconds'], fits=take['fits'],
               average_dbfs=audio.dBFS, peak_dbfs=audio.max_dBFS, activity=[])
    for threshold in (-45, -35):
        spans = detect_nonsilent(audio, min_silence_len=100, silence_thresh=threshold, seek_step=10)
        row['activity'].append(dict(threshold_dbfs=threshold,
            spans_seconds=[[start/1000, end/1000] for start, end in spans],
            active_seconds=sum(end-start for start, end in spans)/1000,
            trailing_below_threshold_seconds=(len(audio)-spans[-1][1])/1000 if spans else len(audio)/1000))
    report['cases'].append(row)
(ROOT / 'docs/validation/2026-10-04-cue-review-audio-audit.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
