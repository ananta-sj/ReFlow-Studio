# Explicit question generation duration — 9 October 2026

## User review and diagnosis

The fuller “ऊब गए क्या?” trial was rejected as unnatural and fast. Its 0.757-second waveform was generated with the existing byte-length calibration. Merely adding a word did not solve delivery. The chart/family/lighthouse phrases remain accepted separately; their files and timing were not changed.

This iteration returns to the original wording **“ऊब गए?”** and gives the model additional generation time for that utterance. It does not slow an already-generated recording, change voice references, revise global calibration or install a framework/model.

## Implementation

`core/indicf5_duration.py` centralizes the existing sentence-to-hop duration calculation. With no override it retains exactly the previous rounded hop formula. An explicitly supplied `minimum_sentence_seconds` floors the generated duration, rounding the floor up to the model's 256-sample hop. A floor never shortens a naturally longer sentence.

Both the provider's duration estimator and `core/indicf5_worker.py` use this shared helper. This keeps predicted and actual waveform length consistent. The provider supports a keyword-only per-request floor and preserves it across an owned-job call. It includes the floor in the request only when explicitly set. The worker validates it for every request; it does not retain a previous request's floor as a session default.

Valid floors are finite numbers between 0.1 and 5 seconds. Booleans, strings, NaN, infinities and out-of-range values are rejected. Invalid input fails before runtime startup/output replacement. The existing 4,096-frame model limit, reference checks, glyph validation, staged output, cancellation and gain-only preparation remain in force.

The option applies to each sentence in the explicitly controlled request. It is **not enabled automatically**, exposed as a new UI default or added to the normal pipeline's parameters. The accepted global voice profile and normal calibration remain unchanged. A general policy for very short utterances needs separate quality review and timing integration.

## Actual speech trials

`dev/verify_question_generation_budget.py` uses the existing real GPU IndicF5 provider and confirmed Abhishek reference for three requests in one worker:

| Request | Explicit duration floor | Actual waveform duration | Purpose |
| --- | ---: | ---: | --- |
| A | 0.9 s | 0.9067 s | Original wording with more phonetic time |
| B | 1.1 s | 1.1093 s | Slightly longer alternative |
| Default regression | None | 0.3947 s | Confirm original recipe remains unchanged |

The final default call reproduced the original accepted-render opening question's PCM **byte-for-byte**, even after the two controlled requests. This is a live regression check that the floor is not sticky and that the extracted shared calculation does not alter default speech output. That known rejected short question is not included in the listening comparison.

The listening WAV plays **A, then B**, with 250 ms initial padding, 900 ms between takes and 400 ms final padding. Padding is for standalone audition only. Neither longer question has been inserted into the video. Both exceed the existing 0.6-second opening slot, so a concrete intro timing plan is required after the user chooses an acceptable take. Do not overlap the interview, truncate either question or silently move accepted shot phrases.

## Verification

`docs/validation/2026-10-09-duration-floor-tests.log`: **100 tests passed** in 65.178 seconds across duration-floor validation, IndicF5 integration, speech integrity and cue review. New tests cover exact preservation of default hop calculations, upward rounding, inability to shorten longer speech, invalid controls and preservation of existing output before a worker starts.

`docs/validation/2026-10-09-default-duration-regression.json`: all **14 prior accepted default duration predictions** remain equal to their original native waveform durations within one 24 kHz sample. This check does not regenerate those 14 takes or overwrite their original receipts.

Live receipt: `docs/validation/2026-10-09-question-generation-budget-e2c252b4.json`.

Listening sample: `docs/validation/2026-10-09-question-generation-budget-e2c252b4/QUESTION_A_THEN_B.wav`.

The live run passed actual/predicted waveform duration checks, floor enforcement, one-worker reuse, default PCM equality, explicit release, full audio decoding, unchanged original voice profile, unchanged accepted short-video hash and unchanged hashes for all three accepted shot phrase WAVs. Temporary job storage was removed. Raw A/B/default-regression WAVs and the JSON evidence remain in the validation folder.

## Remaining limits

**User review result:** clarity improved slightly, but neither take was accepted as natural. No A/B choice was made. Feedback is retained in `docs/validation/2026-10-09-question-budget-user-feedback.json`. The next controlled test evaluates the question in one continuous utterance with its following line, while keeping the total duration budget approximately equal to the original segmented construction. The explicit duration option remains opt-in and is not promoted as a naturalness fix.

Longer generation time is a targeted acoustic experiment, not proof of naturalness. The user must review articulation, pronunciation and question intonation. An overly long fixed duration can itself cause drawn-out or artificial speech. No candidate is human accepted yet; full-video and release approval remain absent.

If one take is accepted, prepare and review an intro that accommodates it while keeping the approved phrase recordings and matching visual windows. Broader automatic phrase-to-shot adaptation and short-utterance policy remain unfinished product work. No newly installed tools, persistent model selection, global pace setting, cache deletion, commit or push is involved in this iteration.
