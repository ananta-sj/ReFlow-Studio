# Stage connections and translation recovery — 9 October 2026

## Scope

The user authorized continued work on stage connections and interrupted-work recovery while retaining the restriction against live model calls. This iteration audits the existing fixed pipelines, repairs translation-worker lifetime on unsuccessful exits, and verifies restart behavior using disposable synthetic audio and fixture providers. No tools, dependencies or models were installed; no weights were loaded; no speech/translation model inference or external provider request occurred. No new user-facing dub was generated.

This is an incremental architecture repair, not an assertion that every advertised feature or independent full-video workflow is release validated. Source observations and regression fixtures are distinguished from actual model-quality testing throughout this report.

## Stage connections reviewed

The fixed plan is compiled by `PipelineSpec`, selections/settings are frozen by `ReflowPipeline.run`, and a durable `RunManifest` records source identity, operations, cue artifacts, checkpoint decisions and the final result. The existing four templates remain video dub, video dub with lip sync, audio dub and subtitle translation. The manager continues to consume these supported operations; this iteration does not add free-form agent execution.

| Connection | Existing implementation observed | Evidence limit / remaining work |
| --- | --- | --- |
| Input → preprocessing | Media extraction/probes run through owned, bounded processes; source identity is retained by the run manifest. | This iteration does not render an independent source video or validate every codec/platform. |
| Preprocessing → separation / STT | Background separation is conditional; recognition receives the chosen vocal/extracted PCM source. Grouping retains cue identities and recognized source-language metadata. | Actual separation and STT inference are deferred; restart test uses a synthetic PCM file and fixture recognizer. |
| STT → translation | Source-language resolution and route checks precede translation. Selected local recognition/translation can use content-bound checkpoints. | Checkpoint reuse is limited to supported Whisper Turbo/IndicTrans2 adapters, not every engine. |
| Translation → moderation / dialogue | Translation preserves source text/timing provenance; selected moderation can adapt/remove lines. Moderation disables translation reuse where its output would otherwise be cached. | Meaning, naturalness and live assisted-review quality are not established by fixture text. |
| Dialogue → speech | Cast/language preflight and native-delivery duration checks feed speech generation. | This iteration does not synthesize speech or validate model-based fit. |
| Speech → timing / mix | Existing media validation, timing guards, mastering and background mixing remain unchanged. | Actual synchronization, English leakage and delivery need independent inference and listening review. |
| Mix → optional visual processing | Enabled lip-sync/enhancement/filter outputs use existing output/duration checks. | Import readiness is separate from checkpoint-backed rendering. Generic F5 remains import-unverified from the previous iteration. |
| Postprocessing → export | Staged output/bundle publication and final output identity prevent an ordinary failed job from being labeled successful. | Full format/platform and independent video acceptance gates remain open. |

The stages called “dubbing/dialogue” in the plan coordinate voice selection, phrasing and timing; TTS supplies the actual speech signal. A separate model is not required for each orchestration step. Current verified restart support is reuse of completed recognition/translation text stages; it is not a general resumable render graph that skips any completed media stage. `retry_limit` remains zero: a restart is deliberate, not an automatic loop.

## Defect found

The shared audio translation path, video path, subtitle generator and review-preparation path called `_release_translation` only after successful processing. That function releases the selected IndicTrans2 worker session. A translation exception, cancellation, early subtitle-generator close, review cue/progress failure or video subtitle-writing failure could bypass the stage's explicit release. Owned render-job cleanup remains a later safeguard, but it did not substitute for ending the worker at the stage boundary or when the generator unwinds.

This defect was found by source tracing. New regression tests then verify the previously missing failure/close guarantees. No actual model was started to reproduce the leak, so the report does not claim to have measured orphaned GPU memory or a live hung model process.

## Repair

`core/pipeline.py` adds `_translation_stage`, a context manager around the already resolved provider. It calls the existing release function on successful exit, an exception, cancellation or generator close. Release behavior remains scoped to the existing IndicTrans2 lifecycle; it does not call invented lifecycle methods on API/NLLB/other providers.

If release itself fails while the translation stage is already unwinding, the original failure/cancellation is retained and only the cleanup exception type is logged. Provider error text could contain sensitive details, so it is not added to that cleanup log. If release fails after otherwise successful work, that failure remains visible and prevents the next stage from proceeding. This avoids silently continuing with an unsuccessfully released worker. The owned job/process cleanup remains the fallback; this helper is not a guarantee that an arbitrary failing cleanup implementation can terminate its process.

The scope wraps translation in the shared audio helper, video generator and subtitle generator, and the complete cue-translation loop in `core/cue_review.py:prepare`. The video's worker is now released as soon as translation finishes, before subtitle generation. Success-only duplicated release calls were removed. Existing successful-stage deletion of provider references and VRAM-cache cleanup remain in place. Source-preserving moderation and non-translation paths are unchanged.

## New recovery evidence

1. Shared audio helper: fixture translation failure and `RenderCancelled` both attempt one stage release. A simulated cleanup failure does not replace the original failure; speech-input cues are not saved as if translation completed.
2. Release failure after success: a simulated release error remains explicit before later work proceeds.
3. Subtitle generator: the real fixed-template run is closed after its translated-cue progress event. It releases the stage worker once, records cancellation, restores registry selection and publishes no translated subtitle output.
4. Review preparation: the existing synthetic-media persistence test now verifies release after both successful preparation and a translation failure. Its earlier accepted review remains unchanged on failure.
5. Restart connection: a synthetic two-second PCM source passes through the real recognition/grouping/checkpoint and translation helpers with fixture providers. The second translation cue fails. Recognition is stored, incomplete translation is not stored, and release occurs. A new run with the same source/configuration reuses recognition from the prior run identity, retranslates both cues, stores only the completed translation and releases again. The fixture recognizer is called once, translator four times total (two in each run), and release twice.

The restart test uses small disposable model/runtime/code fingerprint fixtures. It proves the reuse/control-flow contract under those fixtures, not the installed neural models' outputs or performance. Existing cache corruption, source/model/runtime/code/configuration invalidation, partial-generator and lineage tests remain part of validation. Cache formats and supported adapters were not changed.

## Files and validation record

Production changes are limited to `core/pipeline.py` and `core/cue_review.py`. Tests extend `dev/test_indictrans2_integration.py`, `dev/test_pipeline_foundation.py`, `dev/test_stage_checkpoints.py` and `dev/test_cue_review.py`. The receipt runner gains a `stage-recovery` label and includes checkpoint/transcription source hashes. No frontend source or dependency declaration changes.

The first focused invocation used Windows' sandbox-generated default temporary directory. Seventy-five of 103 tests failed with denied renames while setting up/writing disposable records there. Its log is retained as `validation/2026-10-09-stage-recovery-focused.log`. This invocation failure is not presented as a production regression or a demonstrated repair of application file locking. The rerun explicitly uses project-owned temporary files and the existing regression permissions. **All 103 focused tests passed in 23.456 seconds**, recorded in `validation/2026-10-09-stage-recovery-focused-final.log`.

Final full validation passed **733 tests across 41 modules in 104.297 seconds**, with zero failures or errors. Receipt/log: `validation/2026-10-09-stage-recovery-backend-complete.json/.log`. Saved registry/settings remained unchanged during the suite and final production-source hashes match the tested inventory. The accepted editorial video remains unchanged with SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. Final evidence binding is `validation/2026-10-09-stage-recovery-evidence-integrity.json`. No new frontend build or browser validation is claimed because frontend source did not change.

## Remaining gates

General lifecycle coverage for other providers, fully measured resource estimates, wider device/platform testing, optional-engine asset loading/rendering, model-backed timing/meaning/naturalness and an independent full-video acceptance run remain open. Generic F5's bounded import check remains unverified. Live assisted-review evaluation remains deferred by the user. Release readiness remains pending.
