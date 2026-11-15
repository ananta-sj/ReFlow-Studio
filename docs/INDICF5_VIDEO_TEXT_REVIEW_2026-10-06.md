# Video wording review — October 6, 2026

## Status

The sentence-wise Abhishek paragraph passed human clarity and naturalness
review. Video validation is not yet passed. Fresh source/translation drafts
completed using existing local Whisper-large-v3-turbo and NLLB:
`docs/validation/2026-10-06-indicf5-video-cues-dc446977.json`.
Original input: `Sample/2.mp4`, first 44 seconds. The full source lasts
122.531701 seconds. No production setting or package has changed.

The fresh draft has twelve timed phrases. Whisper inference used the existing
GPU runtime and model's configured float16 dtype; audio features were explicitly
cast to match. Total measured preparation time after imports: 29.469 seconds.
Local loading, timestamp range checks, source hash verification and workspace
cleanup passed. These checks do not establish text accuracy. Source cues and
Hindi translations remain unapproved.

## Findings that block meaningful speech/video acceptance

1. A recognition ambiguity at 6.4–8.4 seconds remains: "Me has this report."
   The earlier smaller recognizer produced the same unusual phrase. Agreement
   between recognizers is not proof; compare the actual audio before editing it.
2. Technical film vocabulary is mistranslated: "establishing shot" becomes
   "अस्पष्ट स्थापित तस्वीर". "Filler shot" becomes "भरने शॉट" rather than a
   useful description of supporting footage. These need context-aware wording.
3. Phrase-by-phrase translation produces incomplete Hindi constructions. The
   reporter's walking, gesturing and question form one continuous description
   spread over several source phrases; isolated translation loses that relation.
4. Idioms/profanity are mistranslated: "pricks" becomes "कुतियाओं"; "fucking
   Matrix" becomes "गंदगी मैट्रिक्स". This changes the meaning. A faithful
   adaptation needs to preserve the intended insult/intensity in context.
5. The 35.52–39.84 second translation drops the clause about the narrator's voice
   talking about facts and retains only the transition to monochrome.
6. The 44-second cut ends with "This is followed by". That phrase is incomplete
   because the fixture ends mid-sentence, not because speech generation failed.
   Do not silently discard it or call the shortened translation complete.
7. Existing Hindi 1.342 post-tempo would modify the accepted IndicF5 delivery.
   Timing must become engine-aware before production voice integration.

## Editorial proposals for review, not accepted translations

These are human-readable wording proposals prepared from the recognition draft.
They are not NLLB outputs, are not stored as approved cues, and have not been
used for synthesis. Timing ranges are approximate ASR phrase bounds, not verified
word alignments. Grouping improves context but may require redistributing cue
timing rather than forcing a long utterance into a short slot.

| Range | Source draft / purpose | Proposed Hindi |
| --- | --- | --- |
| 0.00–6.40 | A standard visual language for news reports emerged, recognisable to anyone. | जल्द ही खबरों को दिखाने का एक तय अंदाज़ बन गया, जिसे कोई भी तुरंत पहचान लेता है। |
| 6.40–8.40 | "Me has this report." — exact audio confirmation needed. | Hold for source wording confirmation; do not assume "मेरे पास यह रिपोर्ट है" is accurate. |
| 9.00–14.00 | An unimpressive establishing shot of a significant location. | शुरुआत होती है किसी अहम जगह के एक फीके से दृश्य से, जो हमें बताता है कि हम कहाँ हैं। |
| 14.00–28.72 | Reporter walks toward the camera, gestures and ignores surrounding people, as if gliding through the Matrix, then stops to ask a question. | फिर रिपोर्टर चलते-चलते अपनी बात शुरू करता है। कैमरे की ओर बढ़ते हुए वह हर दूसरे वाक्य पर हाथ से इशारा करता है। आसपास घूमते मूर्खों को वह ऐसे अनदेखा करता है, मानो कमबख्त मैट्रिक्स में सरक रहा हो। फिर रुककर एक सवाल पूछता है। |
| 28.72–30.24 | What comes next? | इसके बाद क्या होता है? |
| 30.96–44.00 | Supporting shot occupies the eyes while the narrator talks about facts; picture may slow, turn monochrome, and show facts sequentially. | अक्सर ऐसा कोई दृश्य आता है, जिसे देखते हुए आप मेरी आवाज़ में तथ्य सुनते रहते हैं। कभी तस्वीर ठहरने लगती है, फिर काली-सफ़ेद हो जाती है। कुछ तथ्य स्क्रीन पर एक-एक करके दिखाई देते हैं। |

The final incomplete "This is followed by" remains unresolved by these
proposals. Extend recognition beyond the arbitrary cut, choose a verified
complete-sentence endpoint, and retain the distinction between excluded fixture
tail and translated content. The condensed film-term explanations and insult
choice need human meaning/tone review. Byte-length timing alone cannot establish
that these edits fit or preserve every nuance.

## Next validation sequence

1. Resolve the short recognition ambiguity against its original source excerpt.
2. Extend the source excerpt to a complete sentence and group related source
   phrases before translating. Compare grouped NLLB drafts with the proposals.
3. Establish source/translation meaning, then generate short sentence/cue units
   with the accepted Abhishek reference and settings. Keep the rejected continuous
   generation as evidence.
4. Measure natural speech duration against cue windows; retain audible words and
   refuse destructive truncation. Do not silently apply XTTS's old tempo policy.
5. Validate complete moving video, subtitles, source-speech removal, background
   preservation and final listening. A voice-only pass is not a full-workflow pass.

## Runtime/diagnostic failure history

Initial preparation receipt:
`docs/validation/2026-10-06-indicf5-video-cues-363c095b.json`.
It failed on float32 features versus float16 model weights; workspace cleanup
completed. The corrected retry above succeeded. Both logs are retained:
`docs/validation/2026-10-06-indicf5-video-cues.log` and
`docs/validation/2026-10-06-indicf5-video-cues-retry.log`.

## Source wording confirmed; context experiment started

The user confirmed "Me has this report" against the exact original excerpt.
Receipt: `docs/validation/2026-10-06-video-source-wording-acceptance.json`.
Preserve the unusual source grammar; do not rewrite it as an ASR correction.
This supersedes the pending source-wording ambiguity above. It does not approve
the Hindi translation or other phrases.

`dev/prepare_indicf5_video_cues.py --context` extracts 60 seconds for recognition
and groups consecutive ASR phrases until terminal sentence punctuation. It
selects the first complete group endpoint at or after the old 44-second cut.
All extra complete groups and incomplete tail phrases are retained separately
in the receipt rather than silently deleted. The selected complete endpoint,
not a fixed 44-second duration, becomes the future video fixture boundary.
Grouping uses punctuation and approximate ASR phrase bounds, not verified
word alignment; grammar and completeness still need content review.

Fresh grouping must preserve the human-confirmed phrase exactly as a source
group. NLLB now translates complete groups with English source context rather
than each raw ASR phrase. This changes segmentation as well as available source
context; it does not establish that NLLB will resolve every film term or idiom.
Source phrase end times are now bounded by each actual recognition block's
audio end, correcting the earlier possibility of a timestamp extending slightly
past a 30-second block boundary. No source audio is modified except decoding
and extracting the explicit longer fixture. Source hash checks remain.

Log: `docs/validation/2026-10-06-indicf5-video-context.log`.
No new package/model/tool is installed, and production is unchanged.

The context run completed with receipt
`docs/validation/2026-10-06-indicf5-video-cues-9fce0cd4.json` in 32.531 seconds
after imports, with eight complete source groups through 52.0 seconds. The
confirmed phrase is retained. Extra source material and incomplete tails remain
recorded; source hash and cleanup checks passed. Grouping recovered the omitted
narrator/facts clause and the full monochrome sequence. However, film-term and
idiom mistranslations remain, including "गंदगी मैट्रिक्स" and faces being
"तैयार" instead of excluded from the frame. Context alone is insufficient.

An explicit assistant editorial draft now exists:
`docs/validation/2026-10-06-video-hindi-editorial-draft.json`, with a bilingual
reading copy in `docs/VIDEO_HINDI_DRAFT_2026-10-06.md`. The draft records its
authorship, adaptation policy, pending human review and untested-synthesis
status. It is not silently substituted for NLLB output or claimed to be an
automatic translation-engine improvement. Concise film-term descriptions and
approximate sarcastic insult intensity are review choices. Last-cue obligatory
and subtle-framing nuances are not explicit; this limitation is recorded.

Timing estimates are retained in
`docs/validation/2026-10-06-video-hindi-draft-timing.json`. The first draft's
cue 6 exceeded its window under the accepted B text-length calibration. Cues
6–8 were condensed before synthesis, retaining core actions and documenting
nuance tradeoffs. The current eight draft cues are estimated to fit including
0.20-second internal sentence gaps; cues 4 and 5 have relatively little spare
time. These are heuristic estimates, not actual audio-fit passes. Do not cut
audible words or silently accelerate generated speech if measurements differ.
Human wording/tone review precedes presenting this as a faithful dub.
No speech has used this editorial draft, and production remains unchanged.

Subsequent update: the user approved the editorial draft with "yes". Approval,
including pinned draft SHA256, is in
`docs/validation/2026-10-06-video-hindi-editorial-acceptance.json`.
It has since been used for fourteen sentence-wise generations and a completed
52-second review video. This supersedes the earlier unsynthesized/pending-draft
status; it does not accept raw NLLB output or establish automatic translation
quality. Details: `docs/INDICF5_VIDEO_ITERATION_2026-10-06.md`.
