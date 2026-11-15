# Cue review audit — 4 October 2026

**Decision: continue internal testing; not ready for a fully featured release.**
This audit reviewed the saved audio correction workflow, retained real-engine
results, provider lifecycle and the connection to video rendering. It fixes
reproducible persistence and assembly defects using the existing stack. It does
not claim a new listening acceptance or a successful complete automatic dub.

## Findings and repairs

| Finding | Consequence | Action and evidence |
| --- | --- | --- |
| Configuration changes blocked final assembly | Users could lose the ability to assemble already accepted audio after changing model settings, although assembly needs no model inference. | Configuration checks now apply to translation/generation. Rendering accepted takes still checks hashes, actual durations and complete acceptance, and uses the saved review language/timeline. A regression changes model settings and verifies output without invoking speech generation. |
| Revision checks did not cover the commit across processes | Two app instances could read the same revision and overwrite each other's edits. | Reused the installed JSON persistence thread/process lock around revision recheck and atomic publication. A two-subprocess rendezvous test verifies exactly one revision-1 writer commits revision 2; the other gets a reload error. |
| Saved records lacked comprehensive validation | Invalid timing or inconsistent fit metadata could reach playback or mixing. | Validate version, revision, finite duration/timestamps, ordered nonoverlapping cues, text, speech windows, hashes and take metadata on load/save/preparation. Reject accepted overflow, unsupported asset filenames and Windows device names. Tests cover malformed/nonfinite timing, overlap, inconsistent fit, overflow and invalid record types. |

Existing revision checks remain at operation start. Long operations also recheck
the expected revision at commit. Publication stages a separate JSON file and
replaces the manifest atomically. A losing generation may leave an unreferenced
immutable take; it cannot overwrite the winning manifest or a previous take.
Lock files are retained to avoid splitting the cooperating-process lock domain.
This verifies competing manifest commits, not every multi-instance UI or job
interaction. The app's existing per-instance render lock remains in use.

The configuration digest remains deliberately broad: unrelated model/settings
changes can still block further translation or generation until a new review is
prepared. Accepted rendering and playback remain available. No provider cache,
engine, dependency or new model download was added.

## Voice and timing evidence

`dev/audit_review_audio.py` measures retained candidates with existing pydub.
Receipt: `validation/2026-10-04-cue-review-audio-audit.json`.

| Candidate | Duration | Available window | Average / peak waveform level | Activity above −45 dBFS | Trailing quiet at that threshold |
| --- | --- | --- | --- | --- | --- |
| First Hindi sentence | 6.565 s | 6.640 s | −14.89 / −1.51 dBFS | 5.61 s | 0.435 s |
| “मेरे पास यह रिपोर्ट है।” | 9.098 s | 2.600 s | −14.57 / −1.50 dBFS | 8.10 s | 0.478 s |

The second take cannot fit by trimming its trailing quiet. Activity measurements
are waveform thresholds, not a transcript or proof of audible word boundaries.
They do not establish pronunciation, repetition, naturalness or semantic quality.
These levels are waveform dBFS, not a new integrated loudness measurement.
No quiet audio was cut and the approved Hindi pace was not changed.

The cleaned reference spans 119.204 seconds of a 122.532-second source. It has
not been verified as a clean single-speaker reference. A controlled comparison
with a reviewed reference is needed before attributing voice problems to it.
Sampling temperature is 0.75; generation seeds are not recorded. Repeated voice
consistency therefore remains unverified. The user's earlier approved 4.839-second
reading remains evidence for that selected reading only.

## CPU latency

The retained complete-source review took 708.156 seconds to prepare 21 cues and
generate two candidates on CPU. Recorded inference durations were 76.672 and
103.037 seconds. The remaining time includes preparation, translations, imports,
model setup and cleanup; the receipt does not isolate those costs.

Each regeneration constructs a fresh speech provider, repeating model setup.
Provider caching could improve this but must account for cancellation, model
changes, memory pressure and disposal before implementation. This audit does
not claim a measured speed improvement from earlier lifetime cleanup. No new
real-model run was started for this audit.

## Missing video and product acceptance

The Dashboard exposes review for audio inputs only. Review assembly publishes a
WAV. `process_video_gen` still transcribes, translates and generates its own
speech; it cannot consume the corrected cues and accepted takes from this review.
Video integration needs source/frame provenance, accepted-track mux/lip-sync
wiring, corrected subtitle alignment and real moving-face acceptance.

Still open: visible audible playback and layout review, human transcript and
translation review, varied-passage voice consistency, complete corrected media
outputs, calibrated resource estimates, speaker identification/multi-speaker
review, clean-machine distribution and the remaining release readiness gates.
Saved review pruning/deletion and pagination beyond 50 recent reviews are also
missing. Durable user takes must not be treated as disposable job caches.

## Verification and change record

- Focused review suite: **13 passed in 12.839 seconds**;
  `validation/2026-10-04-cue-review-audit-focused.log`.
- Complete backend suite: **483 passed in 66.201 seconds**;
  `validation/2026-10-04-cue-review-audit-backend.log`.
- Existing real review still validates with all **21 cues** under the new schema.
- Refreshed isolated portable application: **168 files**, no size mismatches;
  `validation/2026-10-04-portable-app-refresh.json`.
- Hidden portable desktop: **PASS in 21.688 seconds**, native WAV decoder reports
  1.500 seconds, stop works, overflow/incomplete assembly blocked, acceptance
  persisted and edits isolated; no JavaScript errors.
  `validation/2026-10-04-cue-review-audit-desktop.json`.
  This test suppresses sound and bypasses context-resume permission in the hidden
  fixture. Audible playback and visual layout were not tested.
- Frontend unchanged: retained **83 passing checks** and production build from
  the previous iteration; not rerun for these backend-only changes.
- Whitespace diff check passed. Existing failure receipts were preserved.

Changed implementation: `core/cue_review.py`. Changed regressions:
`dev/test_cue_review.py` (including renaming the generation-only configuration
test to match its scope). Added measurement utility: `dev/audit_review_audio.py`.
Updated iteration, release/product readiness and architecture records. No commit,
push, deployment or release; original runtimes, models and media preserved.

### Controlled reference follow-up — 4 October 2026

Existing offline CPU XTTS comparison completed in200.937s using the same Hindi text, seed1234, temperature.75 and approved1.342 pace. Saved full reference produced6.868s; a cleaned6.640s first-cue reference produced4.202s; repeating the short reference yielded identical raw/processed hashes. Neither fits the2.600s slot. Model loading39.031s once; synthesis72.563s/full and34.531–42.735s/short. Installed XTTS caps conditioning at30s despite the119.204s saved reference. Naturalness, reference cleanliness/speaker identity and translation meaning still need listening review. No production settings/cache/new tool/model download changed. New diagnostic script dev/compare_review_reference.py and detailed report VOICE_REFERENCE_COMPARISON_2026-10-04.md; receipt validation/2026-10-04-reference-comparison.json. Prior backend483/UI evidence retained, no new production edits. Release decision remains not ready.
