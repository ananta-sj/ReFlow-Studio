# Active worker, cancellation and recovery — 10 October 2026

## Outcome and scope

Three active-job display defects were repaired. The rebuilt Windows interface now identifies the active input rather than the next queued input, exposes the actual progress value to accessibility tools, and displays pending cancellation in Assets. Native cancellation and batch resume succeeded with the real bridge worker lifecycle and a synthetic payload. A separate two-process test preserved interrupted-render recovery across abrupt process exit and cleared it after successful restart.

This iteration did not run speech recognition, translation, speech synthesis, voice conversion, separation, enhancement, filtering or lip sync. The user’s boundary against live model calls remains in effect. No dependency, framework, model, service, download or paid call was added. No release-readiness claim follows from these results.

## Findings and production changes

| Finding | Cause | Repair | Evidence |
| --- | --- | --- | --- |
| ONE was processing, but the Input Video node displayed TWO | Nodes used the first pending queue item while the running item had already left that filtered list | `frontend/src/pages/Nodes.tsx` projects `render.inputPath` while running; idle projection still uses the pending input | Final native running capture shows ONE; actual-component contract covers active and idle projection |
| Visual progress showed 25%, but native accessibility reported zero | The progress component consumed `value` for the indicator transform without passing it to the Radix root | `frontend/src/components/ui/progress.tsx` forwards `value` | Final native progress indicator reports 25; contracts cover 0, 25 and 100 |
| Assets continued to say Rendering after Stop | The processing row retained its previous job message until cancellation finished | `frontend/src/pages/Assets.tsx` uses session stopping status and message for the active processing row | Native Assets shows Stopping and disables Resume until exit; after exit it shows Cancelled |

Nodes also explains during active work that controls and estimates configure future jobs and that accepted jobs retain their settings. This matters because the current editable graph configuration is not a complete frozen display of the running job’s accepted configuration. Resource estimates continue to describe future work. No estimate calibration or inference speedup was introduced.

No production backend code changed in this iteration.

## Native walkthrough and isolation

`dev/run_active_walkthrough.py` creates an owned temporary directory, redirects fixture configuration before bridge initialization, creates two one-second blue videos with existing FFmpeg, and starts the built frontend in a disposable private webview. Its `SyntheticBridge` replaces only `_run_render_inner`. The actual bridge outer worker, render context, queue transitions, cancellation event, session publication, recovery marker and workspace cleanup still execute.

The synthetic payload emits STT stage/progress events and waits at 25%. These events exercise display and lifecycle wiring; they do not mean Whisper ran. A release flag lets the second payload copy its input into an output file. The copied blue video contains no dubbed speech.

Two native runs were retained:

- Initial fixture: `temp/native-active-mjuz_m3j`. This revealed the three display defects while demonstrating the existing cancellation/resume lifecycle.
- Rebuilt final fixture: `temp/native-active-xeh2rkzd`. This confirmed the repairs and repeated cancellation/resume. Both processes closed while idle and exited with code zero.

Final sequence:

1. Start the accepted two-job batch through native controls. ONE is active at 25%, with the STT stage highlighted and ONE shown in the input node.
2. Press Stop. The worker observes cancellation but remains deliberately gated so that the pending-stop state can be inspected. Nodes shows “Stopping… waiting for active work to exit”; Stop is disabled.
3. Open Assets. ONE shows Stopping; TWO remains Waiting; Resume Batch is disabled.
4. Release the cancellation-exit gate. The real worker exits through cancellation handling, ONE becomes Cancelled, and Resume Batch becomes available. The cancelled workspace is removed.
5. Press Resume Batch. TWO starts using its accepted parameters, then completes after its release flag is written. ONE remains Cancelled, TWO becomes Completed, the queue is Ready, and the worker is no longer alive.
6. Close the idle fixture and inspect the persisted bridge receipt. Exactly one stopping, one stopped and one finished event are recorded. Only payload two completed. The recovery marker is cleared. The output hash matches the second synthetic input.

Native settings were not changed after batch acceptance in this run. Comparing worker payloads with final accepted queue parameters confirms retention for these jobs, but does not independently demonstrate a native mid-job configuration edit. Deep-copy/frozen-parameter behavior has focused backend coverage.

Completed workspace retention is expected because fixture `auto_cleanup_temp` is false. No native Remove, Clear Finished History, Discard or Factory Clean action was performed. No user media or state was deleted.

## Abrupt process exit and restart

`dev/verify_worker_recovery.py` launches two independent embedded-Python processes against an owned fixture (`temp/worker-recovery-lc1jv487`). It exercises the real outer worker and persisted interrupted-render record, with a synthetic inner payload.

The first child exits abruptly using `os._exit(73)` after starting work and writing the recovery record. This bypasses normal finally cleanup. The second child retrieves the same recovery offer, including its token, and starts work with the recorded input, parameters and template. It completes and exits zero. The record survives the first exit and disappears after successful completion; synthetic output matches input. Tested source and saved user state hashes remain unchanged.

This is a headless process-restart test. It does not establish native recovery-dialog interaction after a real model crash, remaining batch persistence across restart, or checkpoint reuse inside an actual model stage. The receipt explicitly records `stage_checkpoint_reuse_exercised: false`. Earlier native recovery-dialog dismissal and rejection checks remain separate evidence.

## Verification and receipts

| Check | Result | Evidence under `docs/validation/` |
| --- | --- | --- |
| Frontend actual-module/component contracts | 17 passed | `2026-10-10-active-worker-contracts.json`, `.log` |
| Render queue, queue session and stage checkpoint tests | 54 passed in 2.737 seconds | `2026-10-10-active-worker-backend-focused.log` |
| Production frontend build | Passed, exit zero | `2026-10-10-active-worker-build.log` |
| Frontend lint | Passed, exit zero | `2026-10-10-active-worker-lint.log` |
| Native initial and repaired runs | Both completed cancellation/resume, exit zero | `2026-10-10-active-worker-initial-ui.json`, `-final-ui.json`, `-initial-bridge.json`, `-final-bridge.json` |
| Abrupt exit/restart | Passed, expected exits 73 then 0 | `2026-10-10-active-worker-recovery.json`, `.log` |
| Evidence/source/state/video verification | Passed | `2026-10-10-active-worker-integrity.json` |

`dev/verify_graph_controls.cjs` now checks the active input, accessible progress and stopping row alongside the previous graph contracts. `dev/verify_active_worker_evidence.py` checks source hashes, captured native text, worker receipts, terminal events, queue state, workspace cleanup and copied-output integrity. It does not run models. Native process exit codes and test counts in its receipt summarize separately observed command results.

The focused backend tests include owned worker threads, cancellation/pause/resume, accepted parameter copying, simultaneous-start protection and stage checkpoint validation with fixtures. They do not establish real provider throughput or natural speech. The historical full suite of 748 tests was not rerun because production backend code did not change.

Build retains existing large-chunk and ineffective-dynamic-import warnings. Lint diagnostics are retained in its log. These were not silently reclassified as fixed. Initial native failures are preserved as findings rather than removed from the evidence.

One evidence-save attempt used an incompatible existing Node `fs` binding and failed before writing or closing the window. Retrying with an explicit `node:fs/promises` import saved the observations and closed the idle fixture successfully. This did not alter production code or user state.

## User data integrity

The five root state files (`models.json`, `settings.json`, `graph.json`, `hardware_profile.json`, `ui_preferences.json`) match the recorded previous-iteration hashes. The accepted video remains unchanged:

`docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4`

SHA-256: `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`.

Fixture directories and receipts are retained for review. The iteration performed no broad cleanup, repository reset, commit or deployment.

## What remains

1. Exercise native pause-after-current, automatic batch advancement and failure advancement independently; focused backend coverage already exists, but this native run used explicit cancellation and resume.
2. Verify cancellation during actual provider inference and owned FFmpeg/subprocess work, close while real work is active, and stage checkpoint reuse after an actual interrupted model stage. Synthetic waiting cannot establish those behaviors.
3. Verify or design durable recovery of the remaining accepted batch across process restart. Recovery of the current render record alone does not prove recovery of all queued jobs.
4. Test concurrent graph mutations and additional window sizes/scaling. Native removal/deletion remains subject to action-time confirmation.
5. Measure resource estimates against real workloads; validate optional runtime readiness, model download failure/retry and engine execution.
6. Run a fresh full-video model workflow and review meaning, natural delivery, synchronization, background preservation and absence of source-language leakage when live execution is authorized.
7. Validate installation and packaging on clean Windows, Linux and macOS environments before declaring a release ready.

The next useful development slice is batch pause/failure/advancement and durable queue recovery auditing, while retaining the current restriction on live model calls.
