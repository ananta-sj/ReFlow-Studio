"""Prepare a transparent editorial draft for review, never as raw engine output."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw_path = ROOT / 'docs/validation/2026-10-08-indictrans2-full-video-translation.json'
raw = json.loads(raw_path.read_text(encoding='utf-8'))
assert raw['completed'] and len(raw['cases']) == 14
accepted_path = ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-draft.json'
editorial = json.loads(accepted_path.read_text(encoding='utf-8'))
acceptance = json.loads((ROOT / 'docs/validation/2026-10-06-video-hindi-editorial-acceptance.json').read_text(encoding='utf-8'))
assert acceptance['human_translation_accepted'] and hashlib.sha256(accepted_path.read_bytes()).hexdigest() == acceptance['draft_sha256']
texts = [row['text'] for row in editorial['cues']] + [
    'आम लोगों की बेतुकी बातें सुनिए।',
    'ये ज़्यादा है। हमें जानना है कि असल में हो क्या रहा है, लोगों की राय नहीं। मुझे ये छोटे बयान पसंद नहीं। आम तौर पर राहगीरों की राय नहीं चाहिए।',
    'नहीं। फिर खाली जगह भरने को एक और नीरस दृश्य। अब रिपोर्ट इंसानी कहानी पर आती है। रसोई में चिट्ठियाँ खोलता एक साधारण आदमी बताता है कि इस मुद्दे का उस पर क्या असर पड़ा। समाचार देखते वक़्त कोई बताता रहता है कि क्या हो रहा है। मैं उसकी बात सुनता भी नहीं। बस ख़बरें हैं। बस ख़बरें।',
    'ऊब गए? जगाने को ये एनिमेटेड चार्ट, ये औसत परिवार की परछाईं, और लेज़र से सिर कटवाता लाइटहाउस का रखवाला। रिपोर्ट ख़त्म होने को है। राहगीर, साइनबोर्ड, खिड़की से निकला पाइप। फिर आख़िरी सारांश, पास की चीज़ का मज़ेदार दृश्य और चुटीला समापन। किस्मत अच्छी हो तो राजा के लायक शब्दों का खेल, यानी रीजेंट्स ट्रीट।',
    'चार्ली ब्रूकर, न्यूजवाइप, लंदन।',
    'धन्यवाद।',
]
draft = dict(completed=True, preparation_only=True, human_quality_accepted=False,
             human_full_draft_accepted=False, production_changed=False, synthesized=False,
             translation_origin='assistant_spoken_adaptation_with_prior_accepted_editorial',
             raw_translation_receipt=str(raw_path), source_receipt=raw['source_receipt'],
             source_sha256=raw['source_sha256'], cases=[])
for index, (row,text) in enumerate(zip(raw['cases'], texts)):
    if index < 8:
        prior = editorial['cues'][index]
        assert (prior['start'],prior['end']) == (row['start'],row['end'])
    draft['cases'].append({**row, 'raw_translation':row['translation'], 'translation':text,
                          'wording_origin':'previously accepted editorial' if index < 8 else 'new assistant editorial draft',
                          'speech_duration_verified':False})
draft['review_points'] = [
    'These are editorial adaptations, not improved raw IndicTrans2 inference.',
    'First eight texts reuse previously accepted concise editorial wording; the full new render remains unaccepted.',
    'New cue 9 turns a descriptive line into a conversational invitation.',
    'Cue 10 condenses hedging and paraphrases sound bites as short statements and punter as a passerby.',
    'Cue 11 condenses the graceful transition and renders dowdy as ordinary; these nuances need review.',
    'Cue 12 condenses the imagery/summary and retains the English wordplay as a transliterated phrase; its humour is not proven preserved.',
    'Cue 14 uses Hindi धन्यवाद instead of the raw transliterated English थैंक यू.',
    'Native durations must be measured; word count alone does not establish that any new cue fits.',
]
path = ROOT / 'docs/validation/2026-10-08-full-video-spoken-hindi-draft.json'
path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['# Full-video spoken Hindi draft — review required', '',
         'The raw opening failed its timing window. This draft preserves that raw output in a separate column and proposes concise spoken wording. '
         'It is assistant editorial work, not raw IndicTrans2 output. The first eight proposals reuse previously accepted text; later proposals are new and unaccepted.', '',
         '| Time | English source | Raw IndicTrans2 | Spoken draft |', '| --- | --- | --- | --- |']
for row in draft['cases']:
    cells = [f"{row['start']:.2f}–{row['end']:.2f}s", row['source'], row['raw_translation'], row['translation']]
    lines.append('| '+' | '.join(cell.replace('|','\\|').replace('\n',' ') for cell in cells)+' |')
lines += ['', '## Nuances requiring review', ''] + ['- '+point for point in draft['review_points']]
doc = ROOT / 'docs/FULL_VIDEO_SPOKEN_HINDI_DRAFT_2026-10-08.md'
doc.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(json.dumps(dict(draft=str(path), review=str(doc), cases=len(draft['cases']))))
