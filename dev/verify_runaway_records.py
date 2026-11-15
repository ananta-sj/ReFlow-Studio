"""Replay the two archived failures against the shared dialogue guard."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from core.dialogue_integrity import require_reasonable, require_speech_window, DialogueIntegrityReviewRequired
    archive = ROOT/'docs/diagnostics/reset-recovery-20261112-084356/outputs/run_records'
    results = []
    for episode, identifier in ((2, 'a14cfa2ee36c46f69b9227f8b705691f'),
                                (5, 'bb12e2d211f049c9b6040c29a027a088')):
        folder = archive/identifier
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        operation = next(item for item in reversed(manifest['operations'])
                         if item['stage'] == 'speech' and item['status'] == 'failed')
        evidence = operation['evidence']
        artifact = next(item for item in manifest['cue_artifacts'] if item['phase'] == 'recognition-grouped')
        cues = json.loads((folder/Path(artifact['path']).name).read_text(encoding='utf-8'))['segments']
        cue = next(row for row in cues if row['cue_id'] == evidence['cue_id'])
        flags = []
        for name, check in (('translation', lambda: require_reasonable(cue['text'], evidence['text'])),
                            ('speech_window', lambda: require_speech_window(evidence['text'], cue['end']-cue['start']))):
            try:
                check()
            except DialogueIntegrityReviewRequired as error:
                flags.append(dict(check=name, reason=str(error)))
        if len(flags) != 2:
            raise RuntimeError('The old failure was not rejected by both shared guards')
        results.append(dict(episode=episode, cue_id=cue['cue_id'], source_characters=len(cue['text']),
                            bad_translation_characters=len(evidence['text']),
                            source_seconds=round(cue['end']-cue['start'], 3), blocked_before_speech=True, flags=flags))
    destination = ROOT/'docs/validation/2026-11-12-runaway-record-replay.json'
    destination.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
