# Cancellation and cleanup implementation plan — 2026-10-03

Status: subsequently approved and implemented. See
`CANCELLATION_CLEANUP_REPORT_2026-10-03.md` for results and verification limits.

This original proposal addresses A01 from the full audit and the lifecycle protections needed
to make that repair reliable. The user approved preparing this plan. Current
source was inspected again; no production files, dependencies, models or user
outputs were changed during preparation of the proposal. The sections below
preserve the proposed scope; the implementation report records the subsequent work.

## User-visible contract

Pressing Stop should request cancellation immediately, show **Stopping…**, and
prevent another render from starting until the current worker and its owned
children have stopped. The app must not claim that it is stopped or that cleanup
is complete while work is still running.

Subprocess work can be interrupted through its registered process handles.
An in-process model call or synchronous third-party download may have to return
before cancellation can finish. Python cannot safely terminate an arbitrary
thread executing Torch or another native library. This repair will wait for such
a call, discard its uncommitted result, and skip later stages. It will not promise
instant interruption of every AI call. Moving inference into separately
terminable processes would be a larger, separately approved architecture change.

Cleanup must remove only the cancelled/completed job's owned temporary files,
after their users have exited. It must preserve user media, valid outputs,
model storage, Marketplace downloads and other jobs' temporary files.

## Why the current implementation violates that contract

1. `PythonBridge.stop_render()` sets `_render_killed`, clears recovery state,
   kills selected descendants, and immediately calls `Janitor.sweep()`.
2. `Janitor.sweep()` deletes the entire shared `config.TEMP_PATH` directory.
3. `_run_render_inner()` checks the flag at generator yields. A model call,
   frame loop or HTTP request between yields can still be active.
4. Parallel segment futures share that directory. Cancelling a future does not
   terminate one that is already running; executor shutdown can wait for it.
5. Frontend `useRenderJob.stop()` resets to idle immediately after the stop
   request returns; `render_stopped` is also emitted before worker termination.
6. Demucs, Wav2Lip and MuseTalk have their own shared filenames/directories;
   Whisper uses a system temporary directory. Isolating only pipeline.temp_dir
   would leave some work outside the job's ownership boundary.
7. XTTS reference fallback searches the old shared temp path. Moving extraction
   into a job directory requires forwarding the real reference explicitly.

## Proposed implementation

### 1. One cancellation context for each job

Introduce a small internal helper using the standard library and existing
psutil. It holds a job ID, a cancellation event, owned workspace paths, and
registered child-process handles. Define a specific cancellation exception so
normal cancellation is distinguished from engine failure.

The bridge owns the active context under its existing render lock. Stop signals
that context and requests termination of its registered subprocesses; it does
not remove files or clear the recovery marker. Repeated Stop is idempotent.
Stop with no active job does not perform unrelated cleanup.

Segment workers receive the same context explicitly. Checks run before starting
new work, after blocking calls, before mixing and before publication. Pending
futures are cancelled; already running futures are allowed to exit safely and
are joined before workspace cleanup. Cancellation must propagate through broad
provider/segment exception handlers rather than become an ordinary render error.

The helper is internal coordination code, not a new framework or dependency.
Direct CLI/provider callers retain existing defaults when no job context exists.

### 2. Isolate and track temporary artifacts

Use `temp/jobs/<unique-job-id>/` for pipeline-owned working files. Inputs remain
read-only and final outputs remain under the existing output directory.

Adapt separation output, Whisper temporary JSON, Wav2Lip input/output files and
MuseTalk config/results to a job-specific workspace. Account for vendored
inference code's own intermediate paths, not only the wrapper's final result.
Preserve required script working directories/import behavior while redirecting
artifacts. Send the extracted/source reference to XTTS explicitly so it does not
look for another job's `original_audio.wav` in shared temp.

Do not move checkpoint/model caches into the temporary job workspace. Partial
on-demand model downloads are managed by their existing locked recovery helper;
add cancellation checks where safe, preserving existing valid assets.

The regular render lifecycle must stop calling a global temp sweep. Scoped
cleanup verifies resolved path containment and ownership, avoids following
reparse points/symlinks outside the workspace, and cannot delete the temp root,
outputs, models or another job's directory. Cleanup failures are reported with
the retained directory path; they must not be described as successful cleaning.

### 3. Register and interrupt only this job's subprocesses

Replace render-stage subprocess calls with a small owned-process runner while
preserving their current command arguments, output encoding, diagnostic limits
and stage timeouts. Cover FFmpeg/FFprobe, Whisper, Demucs, Wav2Lip and MuseTalk.

Register the handle immediately when a process is created. Coordinate launch
and cancellation so a process started at the same instant as Stop is still
terminated and reaped. Stop the owned process tree with a bounded termination
grace period and kill escalation, then wait for exit. Unregister completed
handles. Do not identify targets merely by matching all descendant process names.

Avoid unmanaged helper threads/processes left writing into a removed workspace.
Tests must cover child processes as well as direct processes and prevent PID
reuse from expanding the kill target. Cross-platform process semantics need
implementation-aware tests; this Windows run cannot certify Linux/macOS behavior.

### 4. Add cooperative checks around work that cannot be forcibly stopped

Check the context around translation, speech/voice calls, audio transforms,
enhancement/filter frame loops and final assembly. Check before acquiring a
shared inference lock and again after acquiring it so queued workers do not
start another model call after Stop.

For synchronous HTTP calls, preserve bounded timeouts and check before/after;
polling helpers check cancellation between requests and use interruptible waits.
Streamed model recovery checks between chunks and before asset replacement.
Opaque third-party initialization/downloads may still have to finish or fail
before stopping completes. This limitation must be visible in status and docs.

This batch will not repair provider languages, cloud request schemas, CPU model
thread safety or stage-quality failures identified elsewhere in the audit.

### 5. Make final output publication cancellation-aware

Use the existing staged-output mechanism, with a cancellation check coordinated
with the final replacement. If Stop is accepted before publication, discard the
pending artifact and preserve any previous valid destination.

An output already atomically published is preserved. A completed terminal record
must not be retroactively changed by Stop during cleanup. Define exactly one
terminal event/queue state under the lifecycle lock; do not emit both cancelled
and completed for the same job. Cancellation of an active job prevents advancing
to the next queued job; untouched queued jobs remain queued.

This batch does not fix the separate stem-export defect or create a multi-file
output transaction. Tests and documentation must distinguish publication timing
from terminal completion and must not promise deletion of an already published
artifact merely because a late Stop arrived.

### 6. Report the true lifecycle in the interface

Stop acknowledgment means **cancellation requested**, not **worker exited**.
Expose a stopping event/status. The render hook stays busy until the backend
emits the final stopped event after generator closure, executor/child completion,
scoped cleanup attempt and recovery-marker handling.

While stopping, disable additional starts and repeated destructive controls;
show that the current engine may need to finish its active call. The backend
continues to enforce this even if the frontend misses events or remounts.

Full persistent render state/navigation recovery (A05) remains a separate issue;
this batch fixes the stop acknowledgment semantics in the mounted interface.
Do not present a failed cleanup as “System Cleaned.”

## Expected affected files

Exact helper layout will be settled during implementation, within this scope.

| Area | Expected files / purpose |
| --- | --- |
| Lifecycle | `bridge/api.py`, new internal cancellation/process helper: context ownership, stop/start coordination and terminal events |
| Workspaces/cleanup | `core/pipeline.py`, `core/janitor.py`: job paths, scoped cleanup, staging checks; preserve explicit global maintenance functions separately |
| Subprocess stages | `core/audio_separator.py`, `core/providers/stt/whisper_local.py`, `core/lipsync_handler.py`, `core/providers/lipsync/musetalk_local.py`: owned process execution and isolated artifacts |
| Vendored workers | Relevant temporary-path options in `core/Wav2Lip/inference.py`, `core/MuseTalk/scripts/inference.py` and their actually used helper paths |
| In-process stages | Speech/voice handlers, enhancement/filter loops and translation boundaries as needed to observe cancellation; no model/provider replacements |
| Network boundaries | `core/model_assets.py`, `core/providers/cloud_rest_common.py`, affected local LLM calls: safe checkpoints and polling cancellation |
| Frontend | `frontend/src/lib/use-render.ts`, `lib/api.ts` and Dashboard/Nodes stop controls/messages: stopping lifecycle |
| Verification/docs | Existing lifecycle/media/speech tests, focused new cancellation tests, aggregate runner and detailed implementation report |

The frontend changes require temporarily restoring **existing locked frontend
build dependencies** to compile and verify the updated UI. No dependency entries
or framework choices are proposed. Remove restored node_modules and the scoped
download/build cache after validation, retaining the built frontend and evidence.
That temporary restoration is included explicitly in the implementation approval
question; it has not been performed while preparing this plan.

## Required acceptance checks

- Stop during a blocked fake in-process engine returns a request acknowledgment,
  retains busy state and workspace, then cleans only after the call exits.
- Stop during a controlled disposable subprocess terminates and reaps only its
  registered process tree; an unrelated process/download is unaffected.
- Cancel before and during process launch, while a worker waits for inference
  lock, during frame processing, between translation lines and during polling.
- Parallel cancellation prevents additional queued inference, waits for running
  workers, emits no late progress/success, and cleans no live segment directory.
- A cancellation before final replacement preserves a seeded valid output.
  A late Stop preserves an already completed result and emits one terminal state.
- A cancelled queued job leaves following jobs queued; normal success/failure
  retains previously tested auto-advance behavior.
- Repeated Stop, idle Stop, immediately repeated Start, and cleanup errors produce
  consistent backend state and truthful messages; no global sweep from Stop.
- Workspace path tampering, sibling paths, symlinks/reparse points and deletion
  failures cannot escape job containment. User samples, outputs and models stay
  untouched by cancellation cleanup.
- Every affected stage receives its workspace/context, and default direct callers
  retain compatible behavior. XTTS uses the actual source reference after path
  relocation; vendored intermediates are accounted for.
- Existing aggregate backend checks pass; changed frontend builds and scoped lint
  pass. Use deterministic events/barriers for race tests, not timing-dependent
  sleeps. Real synthetic-media/process checks supplement mocks where useful.
- Record test results, remaining model/GUI/OS limitations, dependency restore and
  clearance sizes, and exact files changed in the implementation report.

No real model download, live cloud call, real user render, factory reset, release
build, commit or publishing is required to verify this first repair. If real
engine/GUI verification becomes necessary beyond available capabilities, report
that gap instead of claiming it passed.

## Approval requested

Approve implementing the cancellation/workspace/process lifecycle changes above,
the necessary stop-status UI change, regression verification and documentation,
plus temporary restoration/clearance of existing frontend build dependencies.
Other audit fixes and any new tool/framework/dependency remain separately scoped.
