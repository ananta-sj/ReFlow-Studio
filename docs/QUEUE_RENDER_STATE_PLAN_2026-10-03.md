# Connected queue and render-state proposal — 2026-10-03

Status: subsequently approved and implemented; see
`QUEUE_RENDER_STATE_REPORT_2026-10-03.md` for results and verification limits.
Production source, runtime dependencies, actual queue, models and media were not
changed during preparation of the original proposal preserved below.

## Findings confirmed in current source

- **A04:** `frontend/src/lib/use-queue.ts` owns a module-local string array.
  Assets/ Dashboard populate it, but bridge API wrappers do not expose the
  backend QueueManager operations. Dashboard/Nodes start the first path as a
  standalone render. Backend auto-advance tests therefore do not establish
  end-user batch execution.
- **A05:** `useRenderJob()` starts each hook instance from INITIAL and subscribes
  only while mounted. Conditional page rendering and experience-level changes
  can discard progress, source feedback and output while the backend continues.
  The event dispatcher retains no history, and there is no render snapshot API.
- **A06:** `start()` consumes a backend rejection without returning its accepted
  result. Dashboard still pops the video queue or clears the audio/subtitle
  selection; Nodes also consumes its queue head. A rejected start can lose input
  selection and turn the displayed job into an error while another job is active.

The current backend queue has queued/processing/completed/failed/cancelled
states, a pause flag and auto-advance after success/failure. Its mutations and
next-item selection are not synchronized as one claim operation. Progress and
current source feedback also lack a backend state snapshot for UI reconnection.
Stop's deferred cleanup and reset/download guards from previous iterations must
remain intact through any queue integration.

## Proposed user-visible behavior

1. Adding videos creates backend-owned pending jobs that are visible on all
   pages. Adding files does not start inference or freeze incomplete settings.
2. A concrete **Start Batch** confirmation shows the pending file count and the
   current template/device/settings that will apply. The backend accepts the
   batch atomically and snapshots its settings. Later configuration edits do not
   silently change already accepted jobs.
3. Accepted jobs run once in queue order. Each has visible progress and a final
   completed/failed/cancelled result, including output path or error. One failed
   file advances to the next according to the existing backend contract.
4. **Pause after current job** lets active work finish and prevents claiming the
   next job. **Resume Batch** starts remaining accepted jobs when idle. Pause
   differs from Stop, which requests cancellation of the active job and leaves
   remaining jobs pending. Cancelled/completed jobs are not automatically rerun.
5. Pending jobs can be removed by ID; active jobs cannot be removed as if idle.
   Clearing history does not discard pending/active jobs. Completed history is
   visible rather than pretending those files vanished from the queue.
6. A rejected start leaves input selection and pending jobs intact and explains
   the refusal. It does not overwrite the active job's displayed state.
7. Navigating between Assets, Dashboard and Nodes, or changing experience level,
   retains active state, Stopping, source feedback, output/error and batch status.
   A fresh frontend reconnects to the same running backend using a snapshot.
8. Audio/subtitle single-job actions remain explicit single jobs. They do not
   silently start unrelated video drafts afterward.

## Implementation outline

Use the existing backend QueueManager as the job authority. Represent unstarted
UI additions as drafts until an accepted batch supplies a settings snapshot;
retain queued for accepted runnable jobs. Keep frontend state as a subscribed
view of backend records, not a second independently consumed path array.

Add narrow batch start/resume endpoints with atomic validation, claiming and
startup failure handling under the existing lifecycle coordination. Synchronize
queue mutations and return stable copies of job parameters/records. Preserve
individual job IDs through events, progress updates and terminal records. Do not
accidentally retry a completed job or advance after Stop.

Keep a backend render/session snapshot with ordered revisions. Subscribe before
requesting a snapshot and reject an older snapshot that arrives after newer
events. Maintain one shared frontend render/queue store across page remounts;
the existing React facilities and event bridge are sufficient. Ensure cleanup
and worker exit remain reflected in busy state: a final output event alone must
not imply that the backend is ready for another job while cleanup is active.

Make start operations return accepted/rejected results. Single-job selection
clears only after acceptance; backend-owned queue items transition in place
instead of being popped by the frontend. Wire Assets status/pause/resume/history
controls and Dashboard/Nodes batch start to the same records.

Preserve the interrupted-render mechanism as restart-from-the-beginning recovery.
This proposal does not add checkpoint resume or persistent batch storage across
backend process shutdown. A fresh frontend connected to a still-running backend
is a separate, supported case. Full disk queue persistence would be another scope.

## Expected files and verification

Expected changes: `core/queue_manager.py`, `bridge/api.py`, shared frontend
queue/render stores and types, the queue event integration, Assets/Dashboard/Nodes
controls, focused backend/frontend regressions, aggregate checks, production dist
and a detailed implementation report/evidence folder. Existing App startup
recovery wiring may need adjustment to hydrate the common render store.

Regression acceptance uses simulated pipelines and playable synthetic media:

- Three UI-equivalent additions become backend jobs and run exactly once in
  order, including a failure in the middle.
- Repeated/concurrent Start, paused queues and worker-start failures preserve
  queue/input state and do not create two active jobs.
- Pause during a job prevents the next claim; Resume runs remaining jobs; Stop
  retains its cancellation and scoped-cleanup guarantees.
- Active removal is refused; pending removal/history clearing affect the same
  backend records displayed by the UI.
- A rejected single start preserves selected input and the existing active
  display. Audio/subtitle jobs do not start unrelated video drafts.
- Subscription/remount/reconnect restores source feedback, busy/stopping state,
  current output/error and queue records. Delayed snapshot responses cannot
  regress state after newer events.
- The existing 298 backend checks, cancellation/source UI checks, new shared-store
  tests, TypeScript build and scoped lint pass. No real model inference or live
  cloud request is needed for these regressions.

No new state-management package or other framework/tool is required. Temporarily
restore the existing locked frontend packages to build and verify, then clear
node_modules and the task-specific cache again. Document exact results and
verification limits; do not claim interactive GUI/cross-platform acceptance from
programmatic checks alone.

## Separate follow-up observed during this review

The Nodes parallel-worker tooltip still claims CPU rendering is faster and only
GPU model calls are serialized. That wording predates the CPU safety repair and
is now inaccurate. The ETA helper also assumes a CPU worker-count speedup that
has not been benchmarked under serialized speech inference. Record this as an
A02 follow-up for a separately approved correction/estimate review; it is not
evidence against the verified locking behavior, and this proposal does not add
an unmeasured performance claim.
