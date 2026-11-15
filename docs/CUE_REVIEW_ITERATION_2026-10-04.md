# Single-voice audio cue review iteration

The sentence-grouping repair exposed two remaining problems: incorrect recognized
words and generated speech exceeding an otherwise valid cue window. This change
adds an application workflow for correcting and auditioning a line, preserving
accepted audio, and assembling a reviewed dub. It uses the existing React,
pywebview bridge, Python, FFmpeg, translation and speech engines. No dependency,
framework, engine, model download, account action or release was added.

## User workflow and current scope

In Dashboard, select **Audio → Dubbed Audio**. The review panel can prepare the
selected media using its current source/target language, voice, device and
background setting. Preparation extracts a mono 24 kHz audio snapshot, optionally
separates vocals/background with the existing separator, snapshots the cleaned
reference, recognizes/group source cues, and translates each cue. It publishes
a complete review only after all preparation succeeds.

The panel lists the 50 most recent saved reviews; older records remain on disk
but pagination is not yet implemented. Each line exposes recognized source text,
text to speak, the original source window, and the available speech window.
Users can listen to the original line, save text corrections, retranslate the
corrected source, generate a new take, play either the candidate or the accepted
take, and explicitly accept a candidate that fits. Editing either text clears
that cue's candidate/acceptance, leaving all other cues intact. Unsaved text
prevents switching lines/reviews or starting a new preparation. Background job
refreshes do not replace unsaved text.
An explicit discard button restores unsaved text without altering saved takes.

Generation uses the production voice/mastering/timing stage. Only audition mode
permits an overlong result to remain playable, so a user can hear what needs
editing. The take reports its duration and whether it fits. Acceptance and final
assembly both reject overlong audio. The normal automatic render guard remains
unchanged. Hindi retains the reviewed 1.342× pitch-preserving tempo; no words are
cut and no faster setting is introduced.

A new generation attempt leaves an existing accepted take intact, including if
the attempt fails or yields an overlong candidate. After listening, accepting a
new fitting candidate replaces the selected take. Final rendering requires an
accepted fitting take for every cue, verifies the saved audio, places the exact
accepted PCM on the source timeline and optionally uses the snapshotted
background with the existing mixer. It does not rerun recognition, translation,
separation or speech. Output is one new WAV; this review route does not yet
publish separate stems or a video.

This first implementation supports **single-voice audio** review only. It does
not provide video/lip-sync review, speaker diarization, editable cue timings,
automatic semantic validation, automatic repair of an out-of-bounds transcript,
or an unlimited preview payload. The original automatic workflows remain
available. Enabling this panel is not a claim that their acceptance gates pass.

## Persistence and ownership

`core/cue_review.py` stores review manifests and audio under
`outputs/cue-reviews/<random identifier>/`. Preparation runs inside an owned
temporary job; a complete folder is published atomically. Failed preparation
publishes no review. Each edit/generation/acceptance increments a revision, and
stale client revisions are rejected. Bridge mutations use the existing render
lock; long preparation, translation, generation and assembly use the existing
worker/session, stop request and owned-job cleanup lifecycle.

Manifest publication is staged and atomic. Review drafts/takes are not exposed
as final media outputs. Accepted/candidate files have immutable random names,
and SHA-256 checks reject modified audio before playback/acceptance/assembly.
Asset paths are restricted to the review folder, including link/reparse-point
checks. Preview transport is an inline WAV data URL capped at 15 MB; no server,
network audio upload or arbitrary filesystem-path playback endpoint was added.
The final player decodes those bytes with the browser's built-in Web Audio API,
creates/resumes its context inside the explicit play click, and provides stop
and decoded duration. Contexts/sources are closed/stopped on replacement or unmount;
obsolete asynchronous decode results cannot start a later clip. It adds no audio
library. The bridge render lock coordinates one instance. The subsequent audit
added a cooperating-process commit lock and verified competing manifest writes;
all multi-instance UI/job interactions have not been validated. See
`CUE_REVIEW_AUDIT_2026-10-04.md`.

The review records a digest of model connections/active selections and settings,
not copies of provider credentials. A configuration change requires preparing a
new review before more translation/generation. The subsequent audit allows
assembly of accepted audio after configuration changes; no models are needed.
Existing saved playback remains available. This is deliberately conservative and does not claim pinned
model-weight content across arbitrary manual replacement of model files.

Source, vocals, background/reference snapshots and saved takes consume storage.
They survive temporary cleanup and app restart. No review/take auto-pruning or
deletion UI was added in this iteration; obsolete takes can remain on disk. They
must not be mistaken for expendable temporary job files or packaged user data.

## Files and verification

- `core/cue_review.py`: preparation, durable storage, text edits, translation,
  take generation/playback/acceptance, and reviewed audio assembly.
- `core/pipeline.py`: explicit audition-only overflow option; default render
  timing rejection preserved.
- `bridge/api.py`: guarded review endpoints and existing-worker integration.
- `frontend/src/lib/api.ts`: typed bridge methods and review records.
- `frontend/src/components/shared/CueReviewPanel.tsx` and Dashboard integration:
  the user-facing workflow.
- `frontend/src/components/shared/CueAudioPlayer.tsx`: native browser decode,
  explicit play/stop and playback lifecycle cleanup.
- `dev/test_cue_review.py`, speech-integrity regression and full-suite registration:
  real audio persistence, accepted PCM reuse, rejected stale edits, isolated cue
  invalidation, configuration changes, corrupt audio, cancellation, bounded paths,
  bridge guards and atomic preparation/failure behavior.
- `dev/verify_cue_review.py`: actual existing offline engines, with no human
  quality acceptance or final-media approval implied.
- `dev/verify_portable_desktop.py --cue-review`: owned QA-copy synthetic desktop
  interaction checks, separate from real model/listening evidence.

The initial complete backend suite passes **480 tests in 81.319 seconds**;
the final rerun after provider-release cleanup and the preview-size correction
passes **480 tests in 89.524 seconds**:
`validation/2026-10-04-cue-review-backend-final.log`. The source-preview preparation
regression also passes independently after its size-check correction
(`validation/2026-10-04-cue-review-source-preview.log`). All **83 existing frontend checks**
were rerun and passed; the TypeScript/Vite production build passed. Its existing
large-bundle warning remains; no additional framework or warning suppression
was introduced. The Windows QA application refresh checked 168 files with no
size mismatches. Successive refreshes removed only stale generated assets from
that owned copy (`validation/2026-10-04-portable-app-refresh.json`).

An initial actual run on the truncated fifteen-second source failed before
preparation publication: recognition returned a fifth cue beyond the decoded
duration. The strict media guard was retained; workspace cleanup succeeded.
This failure is preserved in `validation/2026-10-04-cue-review-truncated-15s.json`
and its log. A complete-source profile is separate evidence, not a replacement
pass of that truncated case.

The complete-source actual run succeeded in the bounded technical sense:
122.531708 seconds of source produced 21 translated review cues, two candidates
were generated and their saved audio could be decoded/retrieved for playback.
The first candidate is 6.565 seconds in a 6.640-second window and fits. The second
is 9.098 seconds in a 2.600-second window and does not fit. That overlong output
is intentionally available for audition, not acceptance/rendering. Neither take
was marked human-accepted and no final output was produced. The dubious recognized
line “Me has this report.” and the automatic wording remain uncorrected in this
diagnostic fixture. The run took **708.156 seconds**, used existing offline models
on CPU with background explicitly disabled for this profile, and removed its
owned temporary workspace. Receipt: `validation/2026-10-04-cue-review-runtime.json`.
The durable fixture lives under `validation/2026-10-04-cue-review-runtime/`, not
the user's production review folder. It uses explicit fixture model connections.

The actual run exposes substantial CPU latency and variable speech length; a
successful preview endpoint is not a quality or performance acceptance. During
verification, provider lifetime was tightened: preparation releases translation
providers before garbage collection, each completed translate/generate operation
releases its provider, and the bridge collects after review operations return or
fail. No latency reduction or memory admission guarantee is claimed from that
change. The final regression receipt covers these changes.

The first owned-copy desktop check timed out at the library-integrity startup
stage while the separate real model test was active (73.375 seconds). It is kept
as `validation/2026-10-04-cue-review-desktop-startup-timeout.json` and its log;
this is not a passing cue-control check. A retry after model generation is
separate evidence. Cold startup under concurrent load remains a practical concern.

### Desktop failures, repairs and final result

The next check found a same-selection edge case: a repeated selection cleared
the current review without triggering a reload. The handler now preserves the
current review when the value is unchanged; the test also waits for editor
hydration. Retained receipt: `cue-review-desktop-selection-before-fix.json` with
the date prefix used by the other receipts.

An intermediate controls run reported success despite a null audio duration.
Its test compared a `NaN` value numerically, which could not establish audio
decoding. That evidence is retained as
`2026-10-04-cue-review-desktop-controls-before-metadata-check.json`; it is
**superseded and must not be used as playback acceptance**. The test was tightened
to require a finite correct duration. Native HTML media metadata remained stalled
in the hidden QA desktop for both direct data URLs and Blob URLs, including a
muted play attempt. The connected element stayed at ready state zero with no
decoder error. Receipts include `cue-review-desktop-data-uri-before-blob.json`
and `cue-review-desktop-hidden-preload.json` with the date prefix. These results
do not prove the cause or the behavior of a visible user-operated window.

The final player uses the browser's native Web Audio decoder and explicit
play/stop controls. Final desktop receipt:
`validation/2026-10-04-cue-review-desktop.json` — **PASS in 26.391 seconds**, two
editors, actual native WAV decode **1.500 seconds**, stop verified, overlong
candidate acceptance blocked, acceptance persisted, edit isolated to one cue,
incomplete final render blocked, no captured JavaScript errors. The test uses
synthetic PCM, suppresses audible output, and bypasses only the context-resume
permission in that hidden scripted window because its scripted click is not a
trusted user gesture. Native decoding and the actual review/bridge operations
remain in use. **Audible visible-app playback and visual layout were not tested**
by this receipt; production retains real resume permission and explicit play.
The final frontend production build passes and the owned portable QA copy has
the final player. Backend evidence remains the final 480-check receipt.

## Release implications

This implements a previously missing correction/audition/regeneration workflow
within a bounded scope. Automatic recognition/translation quality, video and
multi-speaker review, current full media acceptance, calibrated resources,
optional integrations, clean-machine distribution and platform gates remain
open. See `RELEASE_READINESS_2026-10-04.md`. No commit, push or public release
was performed.
