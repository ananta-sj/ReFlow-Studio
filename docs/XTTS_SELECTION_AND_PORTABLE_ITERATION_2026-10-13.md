# XTTS selection and portable integration — 13 October 2026

## Purpose

The previous iteration validated an optional XTTS provider, but selecting it required a developer environment variable. The portable builder could not include its runtime and omitted the dependency-lock file required for validation. This iteration connects that provider to persisted application settings and assembles a relocated Windows portable trial.

This iteration connects runtime selection, review provenance and portable packaging to the validated speech provider. It adds no model, package, framework or paid service. Existing runtimes and model files are reused. The current runtime remains the default, and the trial does not establish complete release readiness.

## Selection across application workflows

Settings now contains an **XTTS speech runtime** choice in the engine settings section:

- **Current runtime** retains existing behaviour.
- **Isolated CPU runtime (trial)** selects the approved separate runtime. The option is disabled if recipe validation fails. The render device must be CPU.

The bridge validates an isolated runtime before saving this selection, so an unavailable installation cannot be enabled through the UI. Rendering validates it again; a runtime removed or changed after saving is not silently substituted. Other engines, including API speech and IndicF5, retain their own routing.

The saved choice reaches the TTS resolver in both audio and video pipelines, setup inspection, cue audition and assisted review. Normal rendering uses the existing frozen settings snapshot, so a later settings change cannot change the runtime of a running job. Manifest settings retain the selected value alongside the provider's runtime and model identities.

Lifecycle inspection also found that speech-stage cleanup recognised IndicF5 alone. An isolated XTTS worker would have remained loaded until whole-job cleanup, potentially overlapping video-model memory. The isolated provider now identifies its engine, and shared `release_speech` cleanup closes either stage-owned worker after speech. Audio/video rendering and cue audition use that boundary. Job cleanup still handles failure and cancellation. The live trial verifies an actual worker exits before starting the next session; no absolute RAM reduction measurement is claimed.

Existing settings files do not require a write or migration to read the new default. Existing legacy review configuration hashes are preserved by omitting the newly introduced `legacy` value from the review digest. Choosing `isolated` changes that digest and requires a new review configuration, preventing a previous accepted recipe from being reused under a different runtime.

Persisted application settings are authoritative for application workflows. Direct developer provider calls can still use `REFLOW_XTTS_RUNTIME`; that variable does not override an explicit saved choice supplied by the application resolver.

## Implementation inventory

| File | Change |
| --- | --- |
| `core/settings.py` | Adds and validates the `xtts_runtime` setting with `legacy` default. |
| `core/providers/resolve.py` | Accepts explicit runtime selection only for XTTS, leaving independent engines unchanged. |
| `core/providers/base.py`, `core/providers/tts/xtts_local.py` | Adds shared stage-worker cleanup and identifies the isolated XTTS engine. |
| `core/feature_session.py` | Stops only the exact owned session process when graceful shutdown is slow, preserving the enclosing job and unrelated workers. |
| `core/pipeline.py` | Passes the frozen selection into audio/video speech routing. |
| `core/cue_review.py` | Passes the selection into review operations and preserves legacy configuration hashes. |
| `core/engine_readiness.py` | Accepts explicit selection from the bridge while retaining developer-call compatibility. |
| `bridge/api.py` | Exposes trial availability, validates saving and uses the saved selection for setup inspection. |
| `frontend/src/lib/api.ts` | Defines the setting and availability response types. |
| `frontend/src/pages/Settings.tsx` | Adds the choice, availability state and CPU guidance using existing UI components. |
| `packaging/build_portable.py` | Adds explicit optional-profile selection and the exact bound dependency lock; validates the recipe before inventorying it, marks the candidate as not release-ready and bounds copy concurrency. |
| `dev/test_xtts_portable_selection.py` | Adds nine selection/recipe acceptance cases and two copy integrity/failure cases. |
| `dev/test_engine_readiness.py`, `dev/test_runtime_probe.py` | Updates bridge fixtures to include the saved-settings dependency. |
| `dev/verify_xtts_portable_trial.py` | Exercises relocated imports, saved selection, actual speech and generation cancellation using existing source model assets. |

The compatibility adapter, worker implementation and installed replacement package versions are unchanged from the previous accepted recipe.

## Portable recipe and test scope

The builder accepts `--profile xtts-security-candidate`. It includes that optional environment plus its exact hash-bound lock at `docs/validation/2026-10-13-xtts-security-cpu-lock-review.json`. This closes a concrete missing-file dependency that would otherwise cause validation to fail after relocation.

The generated trial is `dist/portable-xtts-trial-2026-10-13`. It is created as a new folder, without replacing existing builds. Its [manifest](validation/2026-10-13-xtts-portable-trial-manifest.json) records component sizes and inventory. The packaging copy excludes personal root state and downloaded model directories. The optional runtime remains opt-in; including it does not change initial settings.

The first assembly exposed expensive serial copying of many small installed-library files. Future builds use four copy threads by default, with an explicit limit of one to eight workers and at most 64 queued tasks. Copy failures propagate, and the portable manifest is published only after all copies succeed. Two real filesystem tests cover nested binary payloads across more than one task batch and an absent source. This uses the Python standard library. The already-running first assembly was allowed to finish serially; no speedup measurement is claimed for the new copy policy.

The live test uses the copied main Python executable, copied application code and copied isolated worker runtime. It supplies the existing source XTTS model directory explicitly and extracts a reference from the existing sample video. Model weights are not duplicated into the candidate. This verifies relocation with already available assets; it does not verify first-use model downloads or a clean machine.

The late lifecycle repair is copied into the owned QA distribution after initial assembly, through `dev/refresh_xtts_portable_trial.py`. That helper checks the target and trial manifest, refreshes only five changed application files, compares hashes and updates inventory sizes. Its [refresh receipt](validation/2026-10-13-xtts-portable-trial-refresh.json) separates this change from the initial assembly record. The earlier four-file refresh remains archived separately.

The test creates trial settings only inside the owned portable copy and removes that file afterwards. It retains a speech WAV as validation evidence. It then waits for a real generation token boundary, requests job cancellation, checks the call reports cancellation, verifies the previous successful output is preserved and cleans the job workspace. Actual results are recorded in [the portable live receipt](validation/2026-10-13-xtts-portable-trial-live.json).

The final relocated run passes **11 checks**, including actual speech, worker exit with the enclosing job still active, observed token-boundary cancellation and preserved output. The call returned from cancellation in 0.032 seconds. This is caller acknowledgement time, not a general worker-exit or rendering benchmark. Both worker/job cleanup and removal of the test-only settings file passed. No model weights were installed into the candidate. [Final live log](validation/2026-10-13-xtts-portable-trial-live-final.log).

## Validation and failures retained

- The earlier [complete backend suite](validation/2026-10-13-xtts-selection-backend-complete.log) passes 787 discovered tests. An intermediate lifecycle run passed 789. After the slow-shutdown fix and its new ownership test, [the final complete suite](validation/2026-10-13-xtts-selection-backend-final-shutdown.log) passes **790 cases**. It excludes the two previously identified standalone state-mutating/download scripts. Download-shaped messages in the unit logs belong to mocked fixture tests, not new model downloads.
- The [final focused regression](validation/2026-10-13-xtts-selection-packaging-final-focused.log) passes 217 cases. The [adjacent regression](validation/2026-10-13-xtts-selection-adjacent-final.log) passes 84 cases. These overlap the complete suite and are not added to its total.
- The [new selection/readiness run](validation/2026-10-13-xtts-selection-new-tests.log) passes 31 cases, including nine new acceptance cases. It also overlaps the complete suite.
- [Frontend production build](validation/2026-10-13-xtts-selection-frontend-build.log) passes. [Frontend lint](validation/2026-10-13-xtts-selection-frontend-lint.log) exits successfully with existing warnings retained. [Actual graph/control contracts](validation/2026-10-13-xtts-selection-graph-contracts.json) pass.
- The later [packaging module rerun](validation/2026-10-13-xtts-selection-packaging-copy-tests.log) passes 11 cases after the bounded-copy improvement. These cases also belong to the final complete run and are not counted twice.

The first affected backend run exposed a bridge test fixture that omitted Settings. An adjacent run exposed the same fixture omission in two runtime-probe cases. The production bridge creates Settings in its normal constructor. The fixtures were updated, the affected runs were repeated and the complete suite passed. The original failed logs remain separately retained as `xtts-selection-packaging-focused.log` and `xtts-selection-adjacent-regression.log`.

The first relocated run generated speech and stopped its worker but could not reach the subsequent cancellation token boundary. Inspection exposed the shared shutdown fallback that cancelled the enclosing job after a slow graceful exit. The new fallback matches the session's exact owned Popen invocation and stops that process tree without cancelling unrelated work. A real fixture that ignores its stop file verifies that another session remains alive and can answer a subsequent request in the same job. All eight [session tests](validation/2026-10-13-xtts-selection-shutdown-tests.log) pass.

The next live run confirmed the job remained active but still failed to observe a token boundary within the probe's 90-second startup window. The final probe provides a 240-second bounded startup allowance and captures worker diagnostics if it fails. It passed with the same production worker and adapter. The two unsuccessful receipts remain [first shutdown attempt](validation/2026-10-13-xtts-portable-trial-live-failed-shutdown.json) and [short startup-window attempt](validation/2026-10-13-xtts-portable-trial-live-failed-boundary.json); their logs are retained too. Successful later results do not erase these attempts.

Audio file-handle resource warnings, existing dependency deprecation warnings and frontend bundle/lint warnings remain visible. They are not suppressed or counted as resolved by this iteration. Backend and compiled frontend checks do not substitute for native interaction acceptance of the new selector.

The [final integrity receipt](validation/2026-10-13-xtts-selection-portable-integrity.json) binds final source hashes and records portable/live acceptance, original state/model preservation and the continued absence of the temporary Ollama trial. Read that receipt for the final measured component sizes and any unpassed gate.

All 12 final integrity checks pass. The refreshed inventory contains 70,550 files and measures 3,879,984,638 bytes total: 2,824,646,533 core bytes and 1,055,338,105 optional XTTS bytes. The 17 actual frontend graph/control contracts pass. All five protected original state files and eight original XTTS assets match their recorded baselines. The temporary Ollama folder remains absent. The QA distribution is retained for further native validation; it is not a published release.

## Remaining release work

This closes the developer-only runtime selection and missing portable dependency inventory gaps. It does not switch the application default, declare the historical shared runtime healthy or publish a release.

Still required: native UI and whole-app recovery acceptance; first-use gated models/download interruption/offline onboarding; a reviewed repair for the other runtime families; representative complete video/audio/subtitle and optional-stage workflows; measured memory/ETA/parallel limits; clean-machine Windows prerequisites; and the owner's license decision plus component/model/native redistribution material.

Linux and macOS remain experimental. The portable trial should be treated as QA evidence, with release eligibility false, until the outstanding gates pass.
