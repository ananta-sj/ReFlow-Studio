# Batch dubbing repair status — 12 November 2026

## Verified repairs

- The exact failed speech inputs from episode 2 (535 characters in 4.7 seconds) and episode 5 (1,049 characters in 3 seconds) contain runaway Hindi repetition. Their original Japanese cues have 28 and 13 characters respectively.
- The provider-independent dialogue guard rejects both archived failures before synthesis. Evidence: `docs/validation/2026-11-12-runaway-record-replay.json`.
- Shared translation screening, bounded phrase recovery, and a separate speech-window guard cover the normal pipeline across providers/languages. Ordinary sentences are not translated word by word. Unrecoverable lines remain explicit review items; source restoration is restricted to the existing unmoderated, non-lip-sync route.
- STT/translation cache code identities now exclude unrelated export/UI code. Speech identities use selected speech methods instead of the entire pipeline file. Old cache identities conservatively invalidate once after this schema/code change.
- Local run records retain bounded, credential-redacted failure messages.
- Batch character references and acoustic checks are connected to Video Dub. Generated-speech readback screening and a persistent `.review.json` summary are implemented. These are warnings, not proof of natural acting or semantic correctness.
- Existing related suite: 83 tests passed. Latest batch-specific suite: 13 tests passed. These counts overlap.

## Not accepted as solved

- The actual 24-second episode-1 scene (121–145 seconds) exposed coarse ASR blocks. Pause-based refinement now produces ten source turns, with recognition-only padding preserving the original timeline.
- The current XTTS speaker encoder did not establish reliable repeated character groups in that scene. The test was stopped; no accepted multi-character dub was produced.
- Automatic batch matching now stops before synthesis when no character group is supported. It must not be represented as production-ready or studio-quality.
- General detection of songs sung by characters remains unfinished. Existing intro-song preservation is limited.
- CPU fallback/resume selection for low GPU memory is not implemented.

## Dedicated speaker detector — 13 November update

The user approved an isolated Community-1 evaluation, accepted its access conditions, and authenticated locally. Its dependencies and model are installed separately from the working speech runtime. After the user resolved the Windows block, a real RTX test on 300 seconds of native stereo episode audio passed: five detected groups, with two distinct usable references in the mother/daughter scene. No speaker count was forced. Evidence: `docs/validation/community-speaker-probe-2026-11-13/result.json`.

Community-1 detects speaker turns and groups; it does not translate or synthesize voices. Local offline operation is enabled. Normal batch matching now invokes the verified worker. Short or ambiguous replies remain review items, and this test does not establish universal anime accuracy or natural acting.

Same-language embedded Japanese SDH captions were found in the original episode. The video pipeline now prefers valid matching-language text, strips nonspoken speaker labels/readings, and uses explicit labels to anchor character references. Explicit song and sound cues are not synthesized. Original sound restoration excludes dialogue intersections and is disabled when it would bypass moderation or lip-sync. Videos without eligible captions keep recognition. Automatic source-language selection still uses recognition.

The focused caption/speaker/recovery/export suite passed 50 tests. A full-context normal-pipeline attempt passed separation, caption selection, matching and translation, then was deliberately stopped during speech to limit test cost. It exposed an additional short malformed Hindi syllable repetition; the shared guard now rejects that exact case and has a regression test. Generated takes and recovery files remain available.

The next render selects only the mother/daughter conversation after detecting speakers across the full five-minute context. This is a test-harness scope restriction, not a forced speaker assignment or hand-written translation. No new Hindi preview has yet been accepted by listening. General song detection without caption evidence, low-memory CPU fallback selection, and guaranteed emotional delivery remain unfinished.

## Actual conversation result and follow-up fixes

- The full-context character test completed: four distinct references were used and the mother/daughter scene had two matched groups. `outputs/batch-character-scene-1794569090/verification.json` records the scope and result. Character matching is verified for this sample, not every anime.
- The Hindi draft is **not accepted**: seven of twelve selected cues retained original audio after timing conflicts. Some very short lines caused XTTS to generate approximately 24 seconds before retry. Slow/runaway speech generation remains unresolved.
- A final-cue bug allowed a long following silence to become a speech window. Speech fitting and native-duration preflight now cap borrowed silence at 350 ms. Real synthesized-tone tests cover sequential/parallel tails and rejection of an oversized take despite a long following pause. This fix was made after the diagnostic render; the draft is not an end-to-end test of the revised fitting policy.
- Readback had included the whole trailing scene gap, causing one recognition timestamp failure to discard every readback. It now checks bounded cue windows, pads to complete 30-second windows, and falls back to individual checks when a batch fails. Rechecking the saved audio checked five dubbed lines: four passed recognition agreement, one needs review. Original reports remain in the audit trail; the published summary uses the latest readback.
- Voice references now come from aligned separated vocals when available. Speaker detection and source recognition still use original audio. Source acoustic measurements also use the clean voice track. Regression tests prove the separation of these inputs.
- The Dashboard now has a Clear reference button and explains that an explicit custom reference uses that voice throughout. Automatic source-character matching requires XTTS without a custom reference.
- An English-pivot comparison using the existing NLLB model did not fix the Japanese idiom error and worsened another repetition. Evidence: `docs/validation/2026-11-13-translation-pivot.json`. This route was not adopted. Selected-model wording errors remain unresolved; recognition agreement is not a semantic translation check.
- Frontend production build passed. The speech/timing suite passed 79 tests; the focused character/recovery suite passed 59 tests (overlapping coverage). GPU readiness and the dedicated speaker proof both remain valid.

Keep `docs/diagnostics/reset-recovery-20261112-084356` and the original source videos. Do not start another overnight batch before a short multi-character preview is accepted.
