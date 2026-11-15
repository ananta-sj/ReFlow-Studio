# Speech intelligibility failure follow-up — 4 October 2026

## Trigger and corrected interpretation

The user rejected both full-reference and short-reference Hindi takes:
“both are gibberish after first 2-3 words”. Both are failed listening examples.
The earlier reduction from 6.868 to 4.202 seconds and identical repeated audio
establish timing/repeatability only; they do not establish successful speech.
Rejection is recorded in `validation/2026-10-04-reference-comparison.json` and
the comparison report. Neither take nor reference preparation was promoted.

## Diagnostic controls

`dev/diagnose_review_speech.py` uses the same installed offline CPU XTTS engine,
temperature 0.75 and sentence splitting, with no new tool or model download.
Use the exact six-second reference retained from seconds 2–8 of `Sample/2.mp4`,
which was used in the earlier user-approved longer Hindi listening examples.
This is a previously successful reference context, not an independently verified
clean speaker sample. Preserve its bytes without new normalization or trimming.

Compare the same Hindi text “मेरे पास यह रिपोर्ट है।” with seed 1234 and seed 7,
then an English control “I have this report.” with seed 1234. The English control
is diagnostic text, not a proposed correction to the suspect source transcript.
All use one loaded model instance; seeds reset Python/NumPy/Torch per case.

Keep raw synthesis, existing mastered output and approved-pace listening output
separately. Hindi uses unchanged 1.342× pitch-preserving pace; English uses 1.0×.
Raw listening is necessary to distinguish synthesis failure from postprocessing.
No seed default, reference policy, model cache or accepted audio was changed.

Record tokenizer round-trip, unknown-token count, model config/vocabulary hashes,
reference hash, declared recovery revision, durations, generation time and raw
audio hashes. A declared revision and expected file size alone do not certify
checkpoint provenance or byte integrity; this experiment does not assert that.

## Evidence and limits

Receipt: `validation/2026-10-04-speech-diagnosis.json`.
Log: `validation/2026-10-04-speech-diagnosis.log`.

Hindi input encodes to 14 tokens with zero unknown tokens, and decodes to the
complete expected line with its language marker. This rules out dropped text in
this tokenizer round-trip, but does not certify correct model pronunciation or
speech content. The installed language configuration declares Hindi support;
its Hindi preprocessing performs basic cleanup without transliteration.

The existing automatic transcription of the source (“Me has this report.”)
remains suspect. Meaning must be reviewed independently even if a later voice
take becomes intelligible. No audio-quality assertion can substitute for this.
Production code is unchanged; prior backend/UI regression results remain scoped
to their existing contracts rather than being claimed as intelligibility tests.

## Completed control results

Execution completed in **131.719 seconds**; model loaded once in **37.360 seconds**.
All WAVs decode and contain signal. Temporary workspace removed; diff whitespace
check passes. Files are retained in
`validation/2026-10-04-speech-diagnosis-11dd6b4a/`.

| Case | Raw duration | Listening duration | Synthesis time | Unknown tokens |
| --- | --- | --- | --- | --- |
| Hindi, seed 1234 | 4.238 s | 3.143 s | 32.531 s | 0 |
| Hindi, seed 7 | 4.436 s | 3.293 s | 34.891 s | 0 |
| English, seed 1234 | 2.172 s | 2.172 s | 18.140 s | 0 |

English round-trips completely with expected lowercasing; Hindi round-trips
completely for both cases. Neither Hindi take fits the original 2.600-second cue.
Changing seed yields different output bytes; neither seed has been promoted.
User listening is pending. Different durations do not indicate correct speech.

The immediate listening controls are `hindi-1234-raw.wav`, `hindi-1234.wav` and
`english-1234.wav`. Ask whether the raw Hindi also becomes gibberish and whether
English stays intelligible. If raw Hindi fails, mastering/tempo cannot explain
the entire failure. If raw is intelligible but processed fails, investigate the
audio processing chain. If English also fails, avoid attributing the issue solely
to Hindi. These are diagnostic branches, not established causes. Alternate Hindi
seed output remains available for further comparison.

Existing earlier approved samples remain scoped to their own text/reference
cases. No fully corrected render or new quality acceptance resulted from this
run. Reference byte hash and model config/vocab hashes are in the receipt; no
checkpoint redownload or full checkpoint provenance assertion was made.

## Subsequent listening feedback

User: “english is too good.=, and regarding hindi is okish”. English is accepted
for this control only. Hindi is partially improved, not final quality acceptance.
The user has not specified raw-versus-processed preference or which Hindi words
remain problematic. The receipt records this distinction and keeps overall human
quality acceptance false. This evidence makes a universal engine-output failure
less likely, but does not isolate reference, Hindi pronunciation, sampling or
postprocessing as the cause. Reference and seed defaults remain unchanged.
Clarification requested: intelligibility/pronunciation versus artificial delivery
versus pauses/endings/pace, and which Hindi version sounds better.

User clarification: **“Words are clear; delivery sounds artificial.”** This
narrows the remaining complaint to delivery for the latest Hindi controls;
raw-versus-processed preference remains unspecified. Do not describe the latest
controls as gibberish or final naturalness acceptance. Follow-up compares the
same raw take without existing EQ/compression and a one-variable temperature
comparison using the same reference, seed and approved pace. No production
change follows from this clarification alone.
