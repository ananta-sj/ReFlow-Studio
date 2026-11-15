# Saved-state safety implementation report

Date: 2026-10-03. A07 saved-state foundation implemented and verified locally.
The user approved the proposal, then extended authorization to continue auditing
and repairing the rest of the project. This report records this completed scope;
later architecture work has its own evidence and does not retroactively change
these results.

## Result and previous failure modes

Model registrations, backend settings, the hardware cache and the interrupted-job
marker now publish complete JSON files through a shared helper. Failed saves
leave the prior destination and committed in-memory state unchanged. Cooperating
threads and processes reload the latest file while holding the store lock before
applying a mutation. Returned registry entries and hardware profiles no longer
give callers a reference they can use to modify stored state accidentally.

Previously each store opened its destination directly for writing, truncating
the old file before the new JSON was complete. Registry/settings/hardware changes
also reached memory before persistence succeeded. Download/UI threads and separate
instances could overwrite updates; loaders accepted wrong shapes or silently
fell back after corruption. Settings displayed a change before its save succeeded.

## Implementation by file

| File | Change and reason |
| --- | --- |
| core/json_store.py | New internal helper: canonical per-path RLock, the existing filelock process lock, reload/validate/mutate/publication transaction, atomic replacement, exact-byte corruption backups, and defensive copies. |
| core/model_registry.py | Structural registry validation; updates reload under the store lock; memory is committed only after saving; list/get/active/add/update results are detached copies. Unknown optional metadata remains supported. |
| core/settings.py | Validates current known setting types, priority 0–100, texture quality 1/2/4, supported Whisper sizes and search providers, and nonempty language/voice/host. Partial valid settings receive defaults when read; unknown stored keys survive ordinary updates. Reset retains its existing defaults-only behavior. |
| core/hardware_profile.py | Validates CPU/device structure and finite nonnegative capacities; capture/refresh commits memory only after publication; get/capture return copies; invalid cache is preserved and can be detected again. |
| core/render_state.py | Atomic marker publication and structural input/params/template/timestamp validation. Clearing an absent marker is idempotent; other deletion errors now propagate. Reading retains the existing one-time-offer behavior for this scope. |
| bridge/api.py | Queues corruption warnings for existing log events, retries failed warning delivery on later reads/session polls, and handles persistence errors in active-model/instruction responses. Failed marker publication no longer triggers deletion of the previous marker. Failed download-thread startup returns the updated copied registry entry; failure to save that error status is reported separately. |
| frontend/src/lib/settings-save.ts | Small promise queue preserves submission order for rapid setting edits and reset; one rejection cannot block subsequent saves. |
| frontend/src/pages/Settings.tsx | Shows returned persisted values after a successful save, reports load/save/reset failures through the existing confirmation alert, and routes edits/resets through the queue. |
| dev/test_persistence_safety.py | 27 new disposable-file/subprocess/integration checks. No real models, cloud calls or credentials. |
| dev/test_suite.py | Registry smoke check now uses disposable storage, avoiding a lock file or other incidental state in the real user registry location. |
| dev/run_cleanup_checks.py | Includes the new persistence suite in the aggregate backend runner. |
| frontend/dev/verify-settings-save.mjs | Six checks against the production save queue and page source using the existing TypeScript runtime. No new testing framework. |

## Exact save and recovery policy

1. Canonicalize the store path. Acquire its shared thread lock, followed by a
   reentrant process file lock, with a 30-second process-lock timeout.
2. Read the latest destination. Only an absent file is normal first-run state.
   Permission/read failures propagate rather than being treated as empty data.
3. Decode and validate JSON, including rejecting non-finite values and numeric
   overflow. Invalid old bytes are preserved before defaults are allowed.
4. Build a private candidate and validate it. Serialize the complete candidate
   before creating the publication temporary file; reject unserializable or
   non-finite new values before replacing any good destination.
5. Write to a uniquely named same-directory `.tmp`, flush and fsync the file,
   then use os.replace. On ordinary failure, remove only that owned temporary
   file. Publish the corresponding in-memory snapshot after success.

Corruption backups use `<original>.corrupt-<SHA256-of-original-bytes>.bak`.
Their exact bytes are verified if a copy already exists. Identical corruption
does not create repeated copies; changed corrupt bytes get another recovery copy.
A failed backup prevents replacement. Read-only recovery leaves the malformed
original in place; a later accepted mutation may replace it with valid state.
Backups are retained for manual inspection/recovery, and warnings identify the
store, cause and copy path without logging the file's contents. Repeated identical
warnings are suppressed within one helper instance. Render-marker helpers are
short lived, so deduplication is not guaranteed across separate calls/restarts.

Persistent `.lock` files are intentionally retained. Deleting a lock file can
split the lock domain while another process is using it. They are coordination
files, not model/download caches. A force-exit can leave a tiny owned `.tmp`;
such files are never treated as live state and are not automatically swept.

## Verification and compatibility findings

- Initial targeted suite: **26 checks passed in 58.517 seconds**.
- First aggregate run: **345 checks**, one failure. A download-thread startup
  response relied on the old registry dictionary alias being mutated in place.
  The bridge now returns the explicit update result instead. That failure was
  corrected; it was not waived or hidden by changing the assertion.
- Final aggregate run: **345 checks passed in 89.337 seconds**.
- Additional temporary-file creation/write failure check added afterward:
  **1 check passed in 0.024 seconds**. This added test changed no production code.
  Together, **346 distinct backend checks passed**, including all 27 new cases.
- Frontend: **65 checks passed**: six settings-save, 13 shared-job-store,
  26 source-language, 12 cancellation and eight deletion-preview checks.
  These are programmatic/source checks, not native GUI acceptance.
- TypeScript and Vite **8.1.5** production build passed, **2,855 modules**, build
  phase **6.20 seconds**. The existing bundle-over-500-KB warning remains.
- Scoped frontend lint produced no diagnostics. Nine changed Python files parsed;
  scoped tracked-file whitespace checks passed (only existing CRLF conversion
  notices). The portable Python remains **3.10.11**.

Coverage includes 40 threaded additions across four distinct registry instances,
36 additions across three subprocesses, abrupt child exits immediately before
and after replacement, serialization/create/write/fsync/replace failures,
failed settings reset and hardware refresh, exact corruption preservation,
backup/read failures, nested defensive copies, invalid structures and settings,
marker clearing errors, failed marker integration, and warning-delivery retry.
All test state was disposable. The forced-exit fixture retained one temporary
file within its disposable directory, and fixture cleanup removed that directory.

Evidence logs: docs/validation/2026-10-03-persistence-{targeted,checks,final-check,
settings-ui,job-ui,source-ui,cancellation-ui,deletion-ui,build,lint,diff-check}.log.
The final aggregate log contains the passing rerun; the failed initial outcome
and its repair are explicitly recorded above.

## Dependencies, build storage and clearance

No package, framework, runtime version or dependency manifest changed. The
already declared filelock package supplies process coordination. Frontend
verification temporarily restored **189 existing locked packages in 34 seconds**
after the sandbox network attempt failed; the retry used permitted network
access. package.json and package-lock.json SHA-256 values match previous evidence.

Removed temporary frontend storage: **12,338 files, 202,776,268 bytes**
(202.8 MB decimal), comprising node_modules and `.persistence-npm-cache`, including
generated verification fixtures. Absolute containment and reparse-point checks
preceded deletion. This is build/test storage clearance, not a runtime-size
reduction. Five final frontend dist files total **1,022,261 bytes**. User models,
inputs, outputs, portable runtimes, developer environment and Git history were
not deletion targets. No real temp/jobs directories remained after verification.

Exact package/dist hashes and clearance counts are in
docs/cleanup/2026-10-03-persistence/FRONTEND_AND_CLEARANCE.json. Source/log hashes
and the A07 follow-up are in BACKEND_AND_FOLLOWUP.json in the same directory.
No commit, push or release was performed.

## Limits and next architecture work

Atomic replacement and cooperating locks are file-level protection, not a
transaction spanning credentials, model files and registry entries. Arbitrary
external editors that ignore the lock can still race the app. Directory fsync
and guaranteed durability under every hardware/power failure are not claimed.
Linux/macOS, real providers and interactive GUI behavior remain unverified.
Settings/registry structure checks do not validate every provider-specific
configuration or pipeline parameter; those belong to the continued architecture
repair. Locks can wait up to 30 seconds when another process holds the store.

The interrupted offer still consumes its marker on reading; durable restart
acknowledgment needs a separate repair. Parallel ETA/tooltips, cross-stage/model
compatibility, stage failures, downloads and other historical audit findings are
not closed by this report. A07's shared saved-state foundation is implemented;
the historical audit remains unchanged, with this report supplying its follow-up.
The broader user authorization now permits continuing those remaining repairs.
