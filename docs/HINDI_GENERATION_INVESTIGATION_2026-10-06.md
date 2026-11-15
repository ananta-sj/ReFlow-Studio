# Hindi generation investigation — 6 October 2026

## Decision

No new production repair is established. The user rejected the failing cue with
both cleaned and accepted unprocessed Abhishek references as non-Hindi or
unintelligible. A same-model control reproduced the previously accepted question
exactly, while reproducing the rejected line exactly. Valid Hindi text routing
does not guarantee correct speech. Full-video acceptance remains deferred.

Punctuation and repetition controls below are diagnostic candidates, not new
accepted takes. No production dependency/model/default was changed. Last full
backend result remains 493 passing checks; this diagnostic-only work did not
rerun it. No release, commit, push or source-media deletion.

## Punctuation controls

`dev/diagnose_hindi_punctuation.py` used the same words/reference/current handler,
greedy decoding, no seed, no output mastering or tempo. It substituted ASCII
full stop or removed final punctuation only. Both tokenize with `[hi]`, preserve
their text roundtrip and have zero unknown tokens.

| Variant | Raw duration | Status |
| --- | ---: | --- |
| Original Hindi danda | 5.334 s | Previously rejected by user |
| Regular full stop | 6.305 s | Fully decodes; not human reviewed or accepted |
| No final full stop | 5.889 s | Fully decodes; not human reviewed or accepted |

Total 205.031 seconds; owned workspace removed. Evidence:
`docs/validation/2026-10-06-punctuation.json`, log and
`docs/validation/2026-10-06-punctuation-0030d5d8/`.

## Repetition controls

`dev/diagnose_hindi_repetition.py` kept current Hindi greedy selection and the
accepted reference, overriding only the existing model repetition penalty to
2.0 or 5.0 through the existing handler. These overrides are local to the driver;
production retains its inherited setting. A question control also tested 2.0.

The 5.0 failing-line output matches the previously rejected raw waveform exactly.
The 2.0 output differs, but diagnostic recognition still does not recover the
intended words. Changing the penalty also changes the question waveform. No
variant demonstrates a reliable repair; there is no fresh human acceptance for
the changed candidates. Exact durations/hashes/timing are in
`docs/validation/2026-10-06-repetition.json`, with WAVs in
`docs/validation/2026-10-06-repetition-bad21ae9/`.

## Recognition diagnostic and limits

`dev/inspect_hindi_recognition.py` used the already-cached faster-whisper tiny
model on CPU/int8, in a standalone diagnostic process. It tried auto language
and explicit Hindi, beam size 5, no VAD, no previous-text conditioning. No model
was downloaded. Existing production STT worker isolation is unchanged.

The accepted question was auto-labelled Hindi (~0.746 probability), but its
transcript was a poor mixed Roman-script approximation. The rejected line was
also auto-labelled Hindi (~0.602), yet transcribed to unrelated syllables.
Regular-stop recognition guessed Bengali with only ~0.346 probability. No-stop
recognition yielded a repeated-letter sequence. Lower-penalty controls likewise
failed to recover the intended line. These are recognizer observations, not
verified labels for actual spoken languages.

**This tiny recognizer cannot serve as a reliable Hindi quality gate.** Forcing
Hindi makes the reported language probability 1 by construction; it is not an
independent confidence measurement. Neither its language label nor an apparently
good average log probability proves intelligibility. Human rejection takes
precedence. No candidate is automatically accepted, and no new failed waveform
is offered as an improvement merely because it decodes.

Receipts: `docs/validation/2026-10-06-recognition-controls.json` and
`2026-10-06-recognition-repetition.json`, with corresponding logs. These preserve
the complete recognized text and segment metrics.

## Proposed next evaluation — approval required

Evaluate **AI4Bharat IndicF5** separately, using a bounded Hindi sentence set and
the user's existing voices. Its official documentation lists Hindi among its
supported languages and requires target text, reference audio and the exact
transcript of that audio. It is a separate Indian-language model, not the
currently approved generic F5 default checkpoint.

Sources checked 6 October 2026:

- [Official repository instructions](https://github.com/AI4Bharat/IndicF5/blob/main/README.md)
- [Official model/access page](https://huggingface.co/ai4bharat/IndicF5)

The model page currently requires access-condition acceptance/contact sharing.
The user may need to complete that login/access step and confirm a short
reference transcript. Do not accept those conditions or share account details
on their behalf. Package/model addition requires approval under the user's
standing instruction. No download or installation has occurred in this proposal.

Evaluation scope: inspect and pin official code/dependencies before running;
install in an isolated environment, preserve the existing core and English
path; record actual download/storage/runtime costs; test the exact failed line,
accepted controls, negation, longer speech and both references; retain complete
raw audio and obtain consolidated human listening review. Only after that
consider integration, timing and full video. Do not promise this engine will
solve the failure, or add it to production before evidence supports it.

The unresolved cause in XTTS is text-dependent acoustic generation failure, not
a conclusively identified underlying mechanism. These bounded controls are not
an exhaustive search of every model parameter.
