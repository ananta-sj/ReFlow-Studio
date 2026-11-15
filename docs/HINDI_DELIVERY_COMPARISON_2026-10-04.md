# Hindi delivery controls — 4 October 2026

User clarification: words in the latest controls are clear, but delivery sounds
artificial. English control was accepted. Earlier full/short-reference samples
remain rejected as gibberish; those are separate cases, not superseded listening
acceptances. The current remaining problem is delivery, not a demonstrated text
loss in the tokenizer or a newly reported volume/pace problem.

## One-variable comparisons

`dev/compare_hindi_delivery.py` retains the current seed-1234 baseline, whose
processed duration is 3.143 seconds, and generates two diagnostic alternatives:

1. Same raw speech bytes, existing loudness normalization and approved 1.342 pace,
   but without the existing EQ and compression. This can test whether mastering
   coloration contributes to the artificial impression. It cannot change the
   model's underlying pauses, syllable delivery or intonation.
2. Temperature 0.90 instead of 0.75, with the same text, reference, seed, sentence
   splitting and synthesis speed, then the existing mastering and approved pace.
   Temperature changes sampling; it is an experiment, not a naturalness setting
   guaranteed to improve speech. The words must still be checked for accuracy.

Text remains “मेरे पास यह रिपोर्ट है।” and reference remains the exact clip used
in earlier accepted longer Hindi examples. Hash checks protect the saved raw
baseline and reference. No reference cleanup, word trimming, extra acceleration,
model cache, production default, new dependency or engine download was introduced.
All new files are separate diagnostic artifacts; accepted/user audio is preserved.

The existing compression and EQ are removed together in the first comparison
as one mastering-route change. If this route is preferred, isolate compression
from EQ before deciding which production adjustment is responsible.

## Evidence and acceptance

Receipt: `validation/2026-10-04-hindi-delivery.json`; log:
`validation/2026-10-04-hindi-delivery.log`. Successful WAV decoding and file
publication establish execution only. Listening acceptance is pending and must
address clear words, natural delivery and endings. Neither shorter duration nor
a selected sample establishes broad Hindi quality. The original slot remains
2.600 seconds; this experiment does not alter it or accept overflow.

Execution completed in **69.406 seconds**; one model load took **37.844 seconds**.
New speech generation took **26.750 seconds**. The no-EQ/compression alternative
is **3.143 seconds**, exactly the baseline duration; the temperature-0.90 case is
**3.105 seconds** (raw 4.192 seconds). Both still overflow the original slot.
No improved-delivery claim follows from the 38-millisecond duration difference.
The first route's loudness receipt is measured before pace processing; do not
present that measurement as final post-tempo loudness.

Files: `validation/2026-10-04-hindi-delivery-7e725813/`. Complete raw/mastered
controls and baseline are retained. All generated speech decodes and contains
signal; owned workspace removed; whitespace diff check passes. No production
changes, so prior backend/UI results remain retained, not newly rerun.
Listening decision: compare both alternatives against the previous baseline;
choose a preferred route only if words remain clear and delivery improves. If
neither improves, do not promote either setting. A preferred short clip would
still require longer-passage and varied-text acceptance before a default change.

User selected **B**, the temperature-0.90 take, over A without existing EQ and
compression. Recorded preference in the receipt; this is a preference among
these two short-cue alternatives, not final Hindi quality acceptance. The current
mastering route is therefore retained for further comparison. Temperature-0.90
remains a candidate, not a production default.

Longer-passage follow-up uses `dev/compare_long_hindi_delivery.py`: retain the
previously approved quality passage's 0.75 baseline, generate the same text with
temperature 0.90, reference/seed/mastering/approved pace unchanged. Keep raw,
mastered and listening files. This evaluates a different text and multiple
sentences before broader adoption. Receipt/log use `long-hindi-delivery` names;
earlier approved samples are not overwritten.

Longer run completed successfully in **107.563 seconds**. Model load37.532s,
synthesis64.516s. New raw8.836s/listening6.565s versus saved baseline5.778s;
the same approved pace is applied, but sampling changes the generated delivery
length. A longer result is not necessarily slower or less natural perceptually;
listen before judging. Files are under
`validation/2026-10-04-long-hindi-delivery-42286fae/`. Both new and baseline WAVs
decode and contain signal; workspace removed. Human acceptance remains pending.

The engine log shows the two Hindi sentences (separated by danda `।`) submitted
as a **single split entry**, despite `split_sentences=True`. This is a concrete
boundary-processing observation and does not establish that it causes artificial
delivery. A future isolated punctuation/boundary comparison may be needed; no
punctuation conversion or splitting default was changed here. Production code
remains unchanged; prior regression results are retained rather than rerun.
