# Durable batch queue and recovery — 10 October 2026

## Problem and resulting behavior

The previous iteration demonstrated cancellation and recovery of the current render, but the queue itself was held only in memory. A process crash could therefore lose accepted jobs waiting behind the current job, drafts and terminal history. Resuming an interrupted batch render through the old standalone start action also had no durable queue identity to update.

The production bridge now supplies an app-owned `queue_state.json` path to `QueueManager`. Accepted settings, item IDs, order, inputs, templates, pause state and terminal results are persisted through the existing `JsonStore`. No dependency, framework, model or service was added. Live model calls, downloads and paid calls remain deferred.

On restart, previously processing jobs return to queued status with zero progress and an interrupted message. Pending work is restored paused. Loading saved data never starts a worker. Accepted parameters stay frozen; drafts still require acceptance. The existing Assets view receives the restored queue through the session snapshot.

This stores future queue changes. It cannot reconstruct batches already lost by earlier versions that never persisted them.

The recovery dialog now sends the offered recovery token to the backend, which reads the saved record itself. For a linked batch job, it restarts that original queue item once and leaves the remainder paused. The user can explicitly resume the remainder afterward. Standalone recovery records and older records without a queue ID remain supported.

Final acceptance passed **763 backend tests across 44 modules in 112.496 seconds**, **25 frontend contracts**, production frontend build/lint, the two-process batch recovery test and source/state/video integrity. Fifteen tests were added: thirteen durable-queue/recovery cases and two cue-publication/read-lock cases. Existing build/lint warnings remain. Five root saved-state files and the previously accepted video are unchanged. No fresh native walkthrough or real model execution was performed in this iteration.

## Changes by file

| File | Change and purpose |
| --- | --- |
| `core/queue_manager.py` | Optional durable storage, schema validation, paused restoration, atomic outer mutations and rollback; grouped batch acceptance/claim and grouped recovery preparation; emergency in-memory pause after worker storage errors |
| `core/render_state.py` | Optional `queue_item_id` in current-render markers, included in the recovery token and validated when present |
| `bridge/api.py` | Production queue path; token-checked recovery endpoint; queue-linked discard; suppression of already-terminal recovery offers; halted batch advancement on otherwise unhandled worker errors |
| `frontend/src/lib/api.ts` | Typed `resume_interrupted_render` endpoint and wrapper |
| `frontend/src/App.tsx` | Recovery Resume uses the offered token; description explains that other restored batch jobs remain paused |
| `dev/test_durable_queue.py` | Thirteen storage/recovery regression tests against owned temporary files and synthetic pipelines |
| `dev/verify_worker_recovery.py` | Optional `--batch` two-process crash/restart validation, preserving the earlier standalone mode |
| `dev/verify_recovery_frontend.cjs` | Actual App recovery handler checks token forwarding; optional receipt output path |
| `dev/verify_dialogue_backend.py` | Durable-queue receipt label and source coverage for changed persistence files |
| `core/cue_review.py` | Shared stable read/write transaction lock; standalone review publication uses the fsynced atomic-byte writer and bounded Windows sharing retries; unsafe-path diagnostics retain both lexical and resolved paths |
| `dev/test_cue_review.py` | Regressions for transient sharing denial and readers waiting for the transaction lock |
| `.gitignore` | Root queue data, lock and corruption backups excluded from version control |

## Persistence contract

The queue file has schema version 1, an items array and a boolean paused field. Validation rejects invalid item shapes, duplicate IDs, unsupported templates/statuses, invalid parameter shapes, invalid progress/timestamps and more than one processing item. Existing `JsonStore` rejects non-finite JSON numbers, publishes through atomic file replacement, retains corrupt bytes as a recovery backup and reports invalid saved data.

An outer mutation holds the queue lock and snapshots the in-memory state. Nested changes commit once at the outer boundary. A failed save restores that snapshot and raises the failure; it does not acknowledge a successful durable change. Batch draft acceptance and first-job claim share one commit, avoiding a partially accepted batch when that write fails. Recovery pause and claim also share one commit.

Progress-only/status-message ticks update live memory without forcing an atomic disk write for every event. Lifecycle changes persist their complete snapshot. Progress is not a stage checkpoint; a previously processing job resets to zero after restart.

Normal completion, failure, cancellation, explicit removal and finished-history clearing preserve their queue transitions on disk. This implementation does not automatically prune history or remove user media. The queue file is first written on a mutation; an empty fresh installation does not need an initial saved queue.

The storage locking protects atomic file publication. It does not establish supported simultaneous independent Reflow application instances: each manager holds its own in-memory snapshot. Concurrent application-instance reconciliation remains a release/design gate.

The existing Windows portable builder uses an explicit root-file allowlist, which excludes root queue state. Its source was inspected; no new portable package or clean-machine installation was produced here.

## Recovery identity and crash windows

New batch render markers identify their queue item. Resume validates the current token and confirms that the original queued item still has the saved input, parameters and template. Stale tokens, changed settings, missing jobs and terminal jobs are rejected. A rejected worker-thread start preserves the offer and restores the queue checkpoint.

Explicit recovery Discard marks only the linked queued job Cancelled, leaves other jobs queued and publishes the resulting session. Dismissing the dialog preserves the offer, as before. No native Discard/delete action was performed in this iteration; discard behavior was verified against owned fixtures.

Queue state and current-render markers are separate atomic stores, rather than one transaction. The following windows have explicit behavior:

- Crash after a queue claim but before a marker is written: the processing queue item restores as queued and can be explicitly resumed through Assets.
- Crash during payload work: the token identifies the original queue item; current-job Resume runs it, while the rest remain paused.
- Crash after terminal queue commit but before marker cleanup: the already-terminal item suppresses a duplicate recovery offer. A leftover marker may remain on disk until a later marker write/cleanup or explicit backend discard; it is not offered as unfinished work.
- Storage failure during terminal recording: the outer worker must not skip the unsaved job and advance. The worker reports an error and pauses in memory. Any still-processing item becomes queued for review before retry. This emergency fallback is explicitly not claimed to have been saved; the last committed processing record also normalizes to queued on restart.

If media was produced but its completion record could not be saved, retry can repeat that work. Exactly-once media generation across arbitrary filesystem failures is not claimed. User review is needed in that situation.

## Two-process crash, pause and failure validation

The final owned fixture is `temp/worker-recovery-putntd56`. It contains binary synthetic payloads, not dubbed media. The headless bridge uses the real queue, outer worker, session state and render marker, with only the inner render payload substituted.

1. The first process accepts three jobs and starts the first. It records its recovery offer and exits abruptly with code 73 through `os._exit`, bypassing normal cleanup.
2. A fresh second process loads all three jobs as queued, paused and idle. IDs, order and accepted parameters are retained. The recovery offer/token matches the pre-crash offer.
3. Token-based Resume completes only the interrupted first job. The other two remain queued and paused; the current-render marker clears.
4. Explicit batch Resume starts job two, which deliberately raises `QA synthetic failure`. Its failed state is recorded; the real outer worker advances to job three and completes it.
5. Final statuses are Completed, Failed, Completed. The process exits zero. The successful first output matches its source bytes. No model-stage checkpoint reuse was exercised.

Existing focused tests also cover Pause After Current, cancellation, frozen settings, failed starts and failure advancement. This iteration adds durable storage and process-restart evidence; it does not add a fresh native walkthrough of pause/failure buttons or the new recovery endpoint.

## Tests, evidence and limits

New tests cover restored identity/settings/drafts, atomic-write rollback, corrupt-byte preservation, durable terminal history/removal, deferred progress writes, single-commit claims, atomic batch acceptance, token-linked resume, stale/changed offers, failed thread starts, explicit fixture discard, terminal-marker duplication and disk-full completion halting.

All evidence uses the `docs/validation/2026-10-10-durable-queue-` prefix:

- `tests.log`: 13 new tests passed in 1.106 seconds.
- `focused.log`: an earlier focused pass of 78 existing tests, before the final worker-error adjustment; the final complete-suite receipt is authoritative for final code.
- `frontend.json`/`.log`: eight actual confirmation/App recovery contracts.
- `graph-contracts.json`/`.log`: seventeen existing actual-module/component graph/progress/Assets contracts against current source.
- `recovery.json`/`.log`: final two-process crash/restart result and source hashes.
- `backend-initial.json`/`.log`: preserved first full-suite attempt, including sandbox failures and source changes during that run.
- `backend-sharing-lock.json`/`.log`: second attempt, with 761 tests and one competing cue-save sharing-lock failure.
- `backend-read-race.json`/`.log`: third attempt, with 762 tests and a competing reader/path-check failure.
- `backend-utf8-fixture.json`/`.log`: fourth attempt, with 763 tests and only the already-loaded regression fixture's missing UTF-8 decoding; corrected before the final stable rerun.
- `sharing-lock-test.log`: new standalone sharing-lock regression passed in 0.142 seconds.
- `competing-save-final.log`: five competing-save runs passed; the added publication regression initially needed an explicit UTF-8 read in its fixture assertion.
- `cue-regressions.log`: both final publication/reader-blocking regressions passed in 0.712 seconds.
- `backend-complete.json`/`.log`: final complete-suite result on stable code.
- `build.log`, `lint.log`: frontend build/lint results; existing warnings remain recorded.
- `integrity.json`: final source/receipt, five saved-state files and accepted-video hash comparison.

The first complete-suite attempt ran 760 tests and encountered four sandbox-denied operations: three fixture-only local HTTP connection tests and the existing synthetic OS credential roundtrip. It also overlapped the final worker-error change, so its source-integrity result cannot establish final-code acceptance. The final rerun was approved outside that restricted sandbox for those local fixture operations. No real API inference was involved.

The second run passed the restricted operations but exposed a transient Windows `WinError 5` during competing cue-review saves. The standalone save branch used a direct `os.replace`, bypassing the existing retry-capable JSON writer. That branch now uses `atomic_bytes`, retaining the review revision lock while writing/fsyncing and replacing with bounded retries. The job-bound branch continues to use its cancellation-aware publication. The new regression simulates a denied first replacement, verifies the old revision remains readable, then verifies the successful new revision and pending-file cleanup. Both failed full-suite attempts are retained, and final acceptance requires the subsequent stable-code run.

A third full run exposed an unsafe-path rejection during competing reads/saves. Reads previously did not participate in the publication transaction, and resolving the replaceable target before acquiring a lock left a race. Reads and writes now use a stable `review-transaction.lock` identity within the owned review folder. Target-path checks and revision reads happen after acquisition; save uses an internal already-locked read to avoid nested process-lock acquisition. Link/reparse/path checks remain enforced. This changes the review lock filename; simultaneous old/new application versions are not validated. The old lock file is not deleted.

Five subsequent competing-save cases passed. A fixture assertion then exposed Windows' default text decoding on Hindi JSON; adding explicit UTF-8 fixed that assertion. The production JSON write/read paths already use UTF-8. The two final regression cases verify publication and reader blocking independently.

A recovery contract command initially used an output argument unsupported by the old utility and overwrote its historical default receipt. The historical receipt was restored from its original JSON log, and the utility now accepts an explicit output path. New results are stored under the durable-queue prefix.

Final counts and integrity are recorded in the machine-readable receipts; this report must be read with those results. There are no new speech or video-quality claims from synthetic work.

The final backend receipt has zero failures and zero errors, with tested source unchanged throughout that run. The integrity receipt confirms the 763/44 backend counts, 25 frontend checks, preserved queue identity/settings and final idle worker state. The accepted video's SHA-256 remains `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2` at `docs/validation/2026-10-09-budgeted-hindi-review-6608ce68/REVIEWED_VIDEO_20618a51d72d.mp4`. Root queue files/lock/backups match the new Git ignore entries.

## Remaining release gates

Native validation of restored queue/recovery controls and pause/failure advancement is next. Real provider/subprocess cancellation, actual model-stage checkpoint reuse, measured resource estimates, optional-engine/download acceptance, fresh complete-video quality and clean Windows/Linux/macOS packaging remain open. Concurrent application instances and exactly-once publication during filesystem failures are not validated. Release readiness remains pending.
