# Speech timing repair and measured dense-cue diagnosis — 16 October 2026

## Decision and limits

This iteration repairs two timing-policy problems and makes genuine speech overflow durable and actionable. It does **not** claim that the original dense six-second dubbing cue now completes. The generated line still needs wording/delivery adaptation to fit naturally. No package, model, framework or service was installed, no user default changed, and no paid or external model call was made.

The previous visual-runtime iteration exposed an English XTTS timing failure: 6.605 seconds were needed after permitted fitting, but only 6 seconds were available. Its failed raw take was cleaned with the old job. This iteration generated **one new seeded diagnostic take of the same text/reference**, retained the audio, and used that single take for subsequent offline replay checks. This is a controlled diagnosis, not a byte-identical reproduction of the earlier random generation.

Final tests, protected-state/model/runtime checks and current source hashes are recorded in [consolidated acceptance](validation/2026-10-16-speech-timing-acceptance.json).

## What was actually wrong

1. **Short English speech was slowed to fill time.** The old non-Hindi fitting policy could stretch short speech down to 0.85× speed. That changes delivery even when speech already fits. Spare timeline time should not automatically stretch the speaker's words.
2. **The final cue ignored available media tail.** Intermediate cues could use silence before the next cue. The final cue instead ended at its subtitle/recognition end, even when the source video/audio continued beyond it. Native duration preflight had the same inconsistency.
3. **Actual overflow was lost on failure.** A generic exception stopped the render, and job cleanup removed the generated take. This made review/debugging require another expensive generation. Runtime errors did not retain structured measured timing evidence.
4. **The six-second sample is genuinely dense for this XTTS delivery.** Model generation has variable duration; source cue timing does not guarantee an arbitrary voice/model will speak the same wording naturally inside that window. A silence trim or a more permissive speed cap is not an adequate general solution.

## Measured model evidence

The diagnostic used the existing CPU XTTS candidate, existing XTTS weights and the same cleaned English reference. Python/NumPy/Torch seed was 7; the normal English sampling configuration was retained. Only this evaluation process was seeded; production decoding defaults are unchanged. The reference SHA-256 matched the preceding failed run's recorded reference identity.

Text: “Before long a standard news report visual language established itself, one that's immediately recognizable to any”.

| Measurement | Observation |
| --- | --- |
| Newly generated raw duration | 10.209 s |
| Exact digital silence at start | 0 s |
| Exact digital silence at end | 0.416667 s |
| Actual replay at the existing 1.3× cap | 7.853 s |
| Actual six-second window | 6 s |
| Measured excess after fitting | 1.853 s |
| Ideal duration even after removing all exact tail silence and applying 1.3× | About 7.53 s; still too long |

[Diagnostic receipt](validation/2026-10-16-speech-overflow-diagnosis.json), [raw audio](validation/2026-10-16-speech-overflow-raw.wav), [worker log](validation/2026-10-16-speech-overflow-worker.log). The raw take SHA-256 is `35c4d68b0a3f1558b034ba6e485856d8db74ce1822ba61680b36c3a901afa3ee`. The bounded owned-process diagnostic took 211.124 seconds including startup/loading/cleanup; this is not an isolated model-performance benchmark.

These observations concern this English XTTS diagnostic. They do not establish Hindi/IndicF5 behaviour, semantic accuracy, speaker similarity or listening approval. Exact zero samples are distinct from low-volume speech/noise; no threshold-based speech deletion was introduced. Internal pauses and speech onset are not shifted to make this example pass.

## Production changes

### Natural delivery and consistent windows

`core/speech_timing.py` centralises the fitting policy. Non-Hindi, non-native-preserving routes now use normal speed whenever speech fits, with acceleration only as needed up to the existing 1.3× limit. The reviewed Hindi 1.342× recipe remains unchanged. Providers marked as preserving native delivery remain at 1.0×.

`core/pipeline.py` passes the existing media end as the final cue's available boundary in both sequential and parallel assembly. A final line can use actual trailing space without extending the source video, moving the line's start or borrowing time from another cue. Subtitle/recognition cue timestamps are not stretched to pretend that a dense line fits.

The existing 50 ms ASR end-rounding tolerance remains. Local cue copies are bounded at the actual source end; an out-of-bounds cue or one with no remaining media time is rejected. Original transcript objects are not mutated. Any rounding adjustment is recorded as a speech-boundary report. This prevents the enlarged final-window policy from offering time past the media end.

`core/dialogue_adaptation.py` accepts the actual media duration for native preflight, using the same bounded cue copies. Callers without a media duration keep the previous conservative cue-end behaviour. This aligns prediction and execution; it does not invent a duration estimator for XTTS.

### Durable measured conflict

If speech still exceeds its window and the excess contains signal, execution raises `SpeechTimingReviewRequired`. It remains a RuntimeError subclass for existing failure handling, while preserving its structured report through the segment wrapper. The error states the measured requirement, available time and retained speed limit.

When a real run manifest exists, the complete fitted take is published as a unique WAV beside the run record before temporary segment cleanup. The manifest stores a `measured-speech-timing` report with `status=needs_review` and sets `review_required=true`. The report records cue/actor/text, generated/fitted/available durations, speed, excess, candidate file identity/hash, and explicit `words_cut=false` / `auto_rewrite=false` flags. Parallel publication is serialised with the manifest's RLock; report/file names cannot collide.

The saved take is review evidence, **not an accepted fit or a completed render**. The normal final-output publication safeguards remain. Exact digital-silence overflow may still be discarded under the existing rule; audible overflow may not. Rendering/review paths that deliberately allow overflow continue to retain candidates without accepting them as fitting speech.

No new automatic wording rewrite or one-click import of these measured candidates into the existing cue-review workspace is claimed. The report and audio are durable run artifacts; further review-workspace integration remains possible follow-up work.

## Verification

[Actual-audio replay acceptance](validation/2026-10-16-speech-timing-replay.json) passes seven checks with **zero additional model calls**:

- The actual generated take cannot be forced into six seconds; it produces a measured review conflict at the unchanged cap.
- Its full candidate audio persists, its SHA-256 verifies, and the manifest's review-required flag survives job cleanup.
- A separate **synthetic 12-second media-window control**, with a cue ending at six seconds, uses genuine supplied tail space during parallel assembly. This is not an extension of the failed six-second source video.
- A spacious cue retains the take's 10.209-second duration rather than stretching its words. Mastering runs normally; no speech shortening or new TTS inference is used.

Regression tests cover short-English normal speed, final media-tail use in sequential/parallel execution, unchanged Hindi/native caps, bounded timestamp rounding without input mutation, real WAV publication/hashing and measured review metadata. Existing cue-review, speech integrity, dialogue and parallel tests are included. Full-suite discovery retains the established exclusions for two standalone scripts, `test_model_download.py` and `test_pipeline_dryrun.py`. Counts overlap and must not be summed.

## Retained failed checks and corrections

- The first 936-case backend run found an old parallel-buffer test fixture defining 20 one-second cues inside a hard-coded three-second source. New bounds validation correctly prevented execution, so its worker-ready assertion failed. The fixture now supplies its actual cue extent; production validation was not weakened.
- Focused runs that included the existing disposable HTTP assistance test initially failed because the sandbox blocked its localhost socket. Their reports remain. The same focused set was rerun with the required local-server access; it does not contact a paid/external AI service.
- An attempted focused-output filename reuse collided with an earlier still-running test's log handle. No application code/state changed; a separate final log filename was used. Failed and intermediate results are retained alongside final verified results.

No user audio-review loop, package upgrade or model download was used to make a fixture pass. The raw diagnostic and reviewed overflow candidate remain intentionally retained; owned inference/replay workspaces and child processes are released.

## What is still needed for dense lines

The real six-second cue still requires a shorter, meaning-preserving rendition or a suitable different delivery. The original video must not be extended silently, and these speed limits must not be bypassed. This is now reported accurately instead of losing the take.

Current saved dialogue mode is **off**, with **zero configured instruction-model connections** and no writer/reviewer selected. Existing translation and TTS models are not interchangeable with a general instruction-following dialogue editor. Automatic adaptation therefore needs either a configured API model or an approved local-model setup through the previously planned hybrid route. Existing external-text consent, request budgets, candidate review and actual re-synthesis/fit verification must remain in place. A model's claim of semantic equivalence is not automatic acceptance.

Until that route is configured and evaluated, wording changes remain a review action. No external request or new installation is authorised by this report. Full six-second dub completion, broader Hindi/long/multi-speaker quality and all prior release/performance/licensing gates remain open.

## Final acceptance summary

All **nine consolidated acceptance checks passed**. The full backend suite passed **936 tests in 187.449 seconds**; the final overlapping focused set passed **131 tests in 57.041 seconds**, including the corrected parallel fixture and localhost review-assistance test. Seven actual-audio replay checks passed without additional generation. Source/profile evidence is bound in the acceptance receipt.

All six established runtime identities, original XTTS assets and protected user state are preserved. The built frontend is unchanged. The diagnostic and replay workers/workspaces are released, while raw/review audio and reports remain intentionally retained. No new package/model installation, default change, external AI request or release approval occurred.

The original six-second cue is still **not completed**. Its next requirement is a meaning-preserving wording/delivery adaptation, configured and evaluated through the hybrid assistance route or handled manually in review. The timing bugs are repaired; automatic dense-line completion remains an explicit open item.
