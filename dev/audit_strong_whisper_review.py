"""Compare fresh machine output with the accepted draft without loading AI weights."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'core')]


def main():
    from core.providers.tts.indicf5_local import IndicF5TTSProvider
    base = ROOT/'docs/validation'
    fresh = json.loads((base/'2026-10-08-strong-whisper-app-review-9ad56e5a.json').read_text(encoding='utf-8'))
    manifest = json.loads(Path(fresh['review_manifest']).read_text(encoding='utf-8'))
    draft = json.loads((base/'2026-10-08-full-video-spoken-hindi-draft.json').read_text(encoding='utf-8'))
    provider = IndicF5TTSProvider(str(ROOT/'models/indicf5/evaluation/assets'),
        str(ROOT/'models/indicf5/references/abhishek/profile.json'),'cuda:0')
    rows = []
    for index,cue in enumerate(manifest['cues']):
        predicted = provider.estimate_duration_seconds(cue['text'])
        accepted = draft['cases'][index]
        rows.append(dict(cue=index+1,source=cue['source_text'],raw_translation=cue['text'],
            start=cue['start'],end=cue['end'],available_seconds=cue['available_seconds'],
            predicted_native_seconds=predicted,raw_translation_fits=round(predicted*1000)<=round(cue['available_seconds']*1000),
            same_index_source_matches_prior=cue['source_text']==accepted['source'],
            same_index_timing_matches_prior=cue['start']==accepted['start'] and cue['end']==accepted['end']))
    report = dict(preflight_only=True,synthesized=False,voice_profile_changed=False,
        preparation_receipt='2026-10-08-strong-whisper-app-review-9ad56e5a.json',
        rows=rows,raw_fit_count=sum(row['raw_translation_fits'] for row in rows),
        cue_count=len(rows),digital_silent_tail=fresh['recognition_result']['blocks'][-1],
        note='Index comparison is diagnostic, not a take reuse rule. Changed grouping makes later cue indices incomparable.')
    output = base/'2026-10-08-strong-whisper-native-fit-audit.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Raw translations fit:',report['raw_fit_count'],'/',len(rows))
    print(output)


if __name__ == '__main__':
    main()
