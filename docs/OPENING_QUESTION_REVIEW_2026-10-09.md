# Opening question clarity review — 9 October 2026

## Feedback and protected baseline

The user accepted the chart/family/lighthouse short test except the opening “ऊब गए?”, which sounded rushed and gibberish-like. Acceptance is recorded separately in `docs/validation/2026-10-09-shot-bounded-user-feedback.json`, bound to the reviewed MP4 hash. It does not approve the opening, the full video or a release.

The three accepted phrase WAV files, their positions and the reviewed MP4 are preserved. This follow-up generates only a standalone question sample. It does not silently retime the chart or change a voice profile.

## Diagnosis and selected wording

The reused original question was only **0.3947 seconds** long. IndicF5's current fixed-duration calculation scales an utterance by UTF-8 text length against the confirmed pace calibration. That predicts waveform duration exactly, but does not guarantee that a very short utterance will have sufficient context or phonetic time for clear delivery. The user's feedback establishes that this particular take failed perceptually; the short duration is a likely contributor, not a proven sole cause.

Three wording alternatives were evaluated without loading speech weights:

| Wording | Predicted native duration |
| --- | ---: |
| ऊब गए? | 0.3947 s |
| ऊब गए क्या? | 0.7573 s |
| क्या आप ऊब गए? | 0.9600 s |

The selected standalone trial is **“ऊब गए क्या?”**, a fuller version of the same question. It uses the existing IndicF5/confirmed Abhishek voice and unchanged calibration, seed, guidance, synthesis steps and sentence-gap settings. There is no global slowdown, duration-floor change, new model or package installation. More wording provides additional generated time and context; listening review is still necessary to judge whether it fixes clarity.

## Implementation and verification contract

`dev/verify_opening_question_review.py` synthesizes the selected question through the existing real provider. It compares actual duration with the native estimate, releases the worker, and creates a listening WAV with 250 ms of leading silence and 400 ms of trailing silence. Padding helps audition the standalone phrase; it is not added to the video timeline.

The diagnostic checks the accepted clip and all three phrase hashes before/after generation, confirms that the original voice profile hash remains unchanged, checks FFmpeg audio decoding and removes its temporary render workspace. It records completion or failure in its JSON receipt. No historical generation/acceptance receipt is overwritten.

Artifact directory: `docs/validation/2026-10-09-opening-question-5bd99607`.

Receipt: `docs/validation/2026-10-09-opening-question-5bd99607.json`.

Listening sample: `docs/validation/2026-10-09-opening-question-5bd99607/OPENING_QUESTION_LISTEN.wav`.

Use the receipt's actual completion/check fields as verification evidence. This report describes the intended contract and pending review; it is not itself evidence of successful generation or human acceptance.

Generation subsequently completed successfully. The receipt records the actual native duration, full decode check, explicit worker release, cleaned workspace, unchanged voice profile and unchanged accepted clip/three phrase files. The listening sample is ready; human clarity/naturalness approval remains pending.

## Integration boundary

**Human review: rejected.** The user reported “not at all natural and fast.” The fuller wording did not solve the opening. Its feedback record is `docs/validation/2026-10-09-opening-question-user-feedback.json`. Next trials allocate additional generation time to the original wording through an explicit per-request duration floor, leaving global calibration and accepted clips unchanged.

The current opening runs from approximately 90.0 seconds to the accepted chart start at 90.6 seconds. A 0.7573-second question cannot fit that 0.6-second slot with a comfortable pause. It is therefore **not integrated into a new video** in this follow-up.

First ask whether the new wording is clear and natural. If accepted, prepare a concrete intro timing proposal that preserves the approved phrase recordings and the matching shots. Any necessary chart placement change must be explicit; do not clip the question, overlap the preceding interview, or claim unchanged shot timing after moving it. A general short-utterance duration policy remains separate design work, with regression coverage and a review of existing accepted short takes required before changing defaults.
