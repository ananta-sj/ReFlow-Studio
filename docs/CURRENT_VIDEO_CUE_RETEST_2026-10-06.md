# Current Hindi video cue retest — 6 October 2026

## Result

The retained failing cue still does not fit under current production behavior.
The complete processed take lasts **5.429 seconds**, against **2.600 seconds**
available: an overflow of **2.829 seconds**. No final video was generated, no
words were cut, and the take is not human-accepted.

## Execution and preserved scope

`dev/verify_current_failed_cue.py` adapts the earlier isolated retry into one
current inference attempt with new dated receipt/media paths. It reuses the
44-second baseline's cleaned Abhishek reference and the diagnostic translation
`मेरे पास यह रिपोर्ट है।`. Source wording remains unconfirmed; this test does
not certify that translation's meaning.

The actual XTTS provider and production `_dub_segment` path ran offline on CPU:
Hindi greedy decoding, corrected native output sample rate, cloned-Hindi
loudness processing and approved RubberBand pace 1.342. No production settings,
packages, models, user registry or original media were changed. Separation,
recognition, translation and reference preparation were not repeated.

Diagnostic `allow_overflow=True` was used solely to preserve complete audio for
inspection. The receipt compares its length against the original window. This
is not a relaxed production render, and it does not exercise the normal overflow
exception in this execution. The existing normal word-cutting guard remains in
production and its prior regression coverage is retained, not rerun here.

Total elapsed time: **216.094 seconds**; segment call: **106.469 seconds**.
Elapsed setup/inference cost on this run should not be treated as a calibrated
resource estimate or compared directly with earlier runs on different inputs.

Both raw and processed WAVs pass full FFmpeg decode, with mono 24 kHz audio.
Exact stream durations and SHA-256 values are recorded separately in the media
receipt. Owned job workspace was removed after evidence publication.

## Evidence

- `docs/validation/2026-10-06-current-cue.json`
- `docs/validation/2026-10-06-current-cue.log`
- `docs/validation/2026-10-06-current-cue-media.json`
- `docs/validation/2026-10-06-current-cue-9f9cce11/trial-1-raw.wav`
- `docs/validation/2026-10-06-current-cue-9f9cce11/trial-1.wav`

Historical accepted samples, rejected controls and the failed automatic video
baseline were preserved. No complete backend/frontend rerun was warranted by
this diagnostic-only addition. The last production backend result remains 493
passing checks.

## Interpretation and next checkpoint

The latest voice-quality repair does not resolve this cue's timing with the
retained cleaned Abhishek reference. One take does not establish why its duration
is long or demonstrate a general voice-quality regression. Listening is needed
to distinguish pauses, delivery, stutters and pronunciation; duration alone
cannot establish any of them.

Next: compare accepted reference preparation against the automatic cleaned
reference and confirm ambiguous source wording. Keep the approved pace; do not
truncate speech, invent source words or shorten meaning just to obtain a pass.
A fresh successful complete video and human final review remain outstanding.

## Human review: rejected

The user reported: “not at all clear... is it hindi?? or tamil or telugu??”
The processed take is explicitly rejected for clarity/language intelligibility.
This does not identify its actual spoken language; no Tamil/Telugu classification
has been established. The updated receipt records this rejection. Mechanical
decode success must not be treated as speech-quality success.

The next controlled inference uses the exact hashed unprocessed Abhishek
reference from accepted coverage, keeping this text, greedy decoding and output
processing unchanged. Its outcome must be reviewed before any production
reference-preparation change is made.

## Unprocessed-reference control: rejected after listening

`dev/verify_reference_control.py` ran the same Hindi text and production route
with the exact retained accepted Abhishek reference, SHA-256
`9c64601dd08a9ccd28c11fe7a9deb40a858bda54a39e77234a443bf0a498b905`.
No seed or production setting was changed. Raw output is 5.334 seconds and the
processed output is 3.975 seconds (precise stream duration 3.974667). The latter
still exceeds the 2.600-second cue by 1.375 seconds. Both mono 24 kHz files fully
decode. The job took 135.906 seconds, segment call 90.047 seconds, and its owned
workspace was removed.

The shorter output demonstrates a difference with reference substitution in
these runs, not proof that cleaning alone causes unintelligibility. The entire
reference-preparation difference was substituted rather than individual filters
 isolated; no cross-run random-seed control was applied. No final video or
 accepted fitting take exists.

Evidence: `docs/validation/2026-10-06-reference-control.json`, accompanying log
and `2026-10-06-reference-control-media.json`; audio in
`docs/validation/2026-10-06-reference-control-e2ba16f5/`.

The user rejected both the raw and processed recordings: “not at all... both
are not hindi audio's they are completely different langs”. This establishes
failed intended Hindi intelligibility, without independently identifying which
other language or phonetic failure occurred. It rules out reference substitution
alone as a demonstrated repair. The control receipt records rejection.

Further diagnostic: `dev/diagnose_current_hindi_routing.py` compares the exact
previously accepted Abhishek question and the rejected line through one actual
adapter/model instance, with the accepted reference, no production seed, no
output tempo or mastering. It records tokenizer roundtrip/unknowns, model mode,
native rate and a raw hash comparison against the approved question. Results
belong to `docs/validation/2026-10-06-routing.json`. Even valid input tokens cannot
certify generated speech. Full-video work is deferred while this quality failure
is investigated.

## Same-model routing comparison: completed

The diagnostic completed in 160.546 seconds and fully decoded both raw WAVs.
The previously accepted Abhishek question was reproduced exactly: 4.129 seconds,
raw SHA-256 `bea3682834550544e41f8c775c86f455f37f5caac93c5bc563fee565bf0ae7a6`.
This is retained accepted-waveform equivalence, not new blanket listening
acceptance for unrelated text.

The rejected line also reproduced exactly: 5.334 seconds, raw SHA-256
`e381c6745f4e4f8bbb36651fd25350cd77aba5c3681f0b9a4b4e7e52681cb914`, matching
the rejected unprocessed-reference control. No further listening request is
needed for that identical rejected waveform. Both inputs start with `[hi]`, have
zero unknown tokens, and roundtrip to their exact Hindi text. The writer rate is
24 kHz; GPT and decoder report evaluation mode. The parent XTTS module reports
training=True; that flag alone does not establish active dropout or a cause.

The same loaded adapter, model and hashed reference reproduce a known accepted
Hindi case and a known rejected case. Therefore a blanket language-routing or
reference substitution repair is not established. The current greedy profile
has demonstrated text-dependent Hindi intelligibility failure; its accepted
coverage was too narrow to certify general Hindi generation. The underlying
acoustic/model cause remains unresolved. A replay of this rejected waveform or
more tempo processing is not a repair.

Evidence is in `docs/validation/2026-10-06-routing.json`, corresponding log and
`docs/validation/2026-10-06-routing-07261d44/`. No production code or dependency
changed. Full-video/release acceptance remains blocked by speech quality, source
meaning and cue fit. Any proposal to introduce a new Hindi engine requires the
user's prior approval, with its rationale and dependency/storage implications.
