# Connected queue and render state — 2026-10-03

## Approved scope and outcome

The user approved `QUEUE_RENDER_STATE_PLAN_2026-10-03.md`, including temporary
restoration of existing locked frontend packages for verification. This iteration
connects UI video additions to the backend queue, adds accepted batch/pause/resume
operations, preserves render state across page changes/reconnection, and retains
input on rejected starts. It addresses A04, A05 and A06 in the historical audit.

No new dependency, state-management framework, runtime, model or service was
added. Tests used simulated render pipelines and existing synthetic-media
fixtures. No real user batch, cloud request, model inference or model download
was run. Existing unrelated working-tree edits remain; this document describes
this iteration rather than every change against Git HEAD.

## User-visible behavior

| Action or situation | Result |
| --- | --- |
| Add videos from Assets/Dashboard | Create backend draft records without starting inference. The same records appear across pages. |
| Start Video Batch | Confirm count/template/device/target/settings; backend accepts and claims the first job atomically. |
| Pending list changes while confirmation is open | Reject the stale list of job IDs and ask for another review; do not silently include extra files. |
| Two simultaneous batch starts | One is accepted; the other is rejected without consuming pending jobs. |
| Failure in a batch | Record that job's error and continue to the next accepted job. |
| Pause After Current | Let active work and cleanup finish; prevent claiming the next job. |
| Resume Batch | Start the remaining accepted queued jobs with their existing settings. New drafts remain unaccepted. |
| Stop | Request cancellation and wait for active work; cancel the current uncommitted job, pause the queue, and keep remaining accepted jobs. |
| Add another video while a batch runs | Add a draft; it does not silently join the accepted batch. |
| Remove active job, including after output publication while cleanup runs | Refuse removal. |
| Remove pending job | Remove its backend record by stable ID. |
| Clear Finished History | Remove terminal history while preserving pending jobs and the current job still finishing cleanup. |
| Rejected single start | Keep audio/subtitle selection and the current displayed job; show the refusal separately. |
| Accepted single start | Clear its local selection only after acceptance. Single jobs do not consume unrelated video queue entries. |
| Change page/experience level | Read the same shared render/queue store, including source feedback, output/error and Stopping. |
| Fresh frontend reconnect to the same backend | Subscribe, hydrate from a snapshot, and recover missed snapshot notifications on periodic reads. |
| Reconnect while a job is active | Do not offer that active job as a crash-interrupted restart. |
| Worker cannot start | Restore queue statuses/settings/pause state and previous displayed output; report rejection. |

The Assets page shows Ready to start/Waiting/Rendering/Completed/Failed/Cancelled,
per-job progress, output path or error, plus pause/resume/history controls. Video
start buttons and confirmations identify a batch. Dashboard retains explicit
single-job behavior for audio and subtitle templates.

## Queue authority and settings

`core/queue_manager.py` is the authority. Frontend use-queue no longer owns an
independent consumable path array. It selects pending backend records and sends
actions through the bridge. Stable UUID job IDs survive status transitions;
completed/failed/cancelled jobs remain history until explicitly cleared.

Draft jobs have no render parameters. Batch acceptance deep-copies current render
parameters into the drafts, snapshots graph cast selection when applicable and
marks them queued. Previously accepted queued jobs retain their prior parameters.
Parameter snapshots and returned records are deep copies: changes to a frontend
configuration or a caller's nested parameter dictionary do not rewrite jobs.
Provider/model-registry activation remains the preexisting runtime resolution;
this iteration does not freeze or clone every model/registry resource.

QueueManager uses an internal reentrant lock. `claim_next()` checks pause and
marks one queued record processing under that lock, returning a copy. Bridge
mutations/start/pause/claim decisions also coordinate with the render lifecycle
lock. Draft duplicate paths are suppressed while the same exact path is already
draft/queued/processing; terminal jobs can be added again explicitly. This is
string-path deduplication, not content-based media deduplication.

QueueManager is marked non-serializable to pywebview's recursive API discovery,
so internal checkpoint/claim helpers are not exposed as nested JS methods.
Supported UI actions use the coordinated bridge endpoints. Other legacy nested
objects/API surfaces are not claimed to have been redesigned.

## Render snapshots and ordering

`core/session_state.py` retains render display state in memory. Snapshots include
backend session ID, increasing revision, render fields, queue records, paused
flag, busy flag and last render-event timestamp. Legacy progress/source/stage/
terminal events remain available; the new UI uses the authoritative
`session_state` snapshot notification and `get_session_state()`.

Queue updates and render events publish a new revision. Render busy remains true
through output publication and cleanup, until worker coordination finalizes. A
finished display/output event alone therefore does not enable Start. Retained
owned-process failures retain blocked/busy ownership as in the cancellation
repair; this iteration adds no automatic recovery monitor for that condition.

`job-store.ts` retains one shared frontend state. `use-jobs.ts` subscribes before
hydration and polls the snapshot every five seconds as recovery for missed
notifications. React's existing useSyncExternalStore provides the page hooks;
no new state package is used. Older same-session revisions are ignored. Retired
backend sessions cannot overwrite a replacement, and an in-flight response from
an unknown old session is refused when newer events have arrived. A genuinely
newer same-session response remains usable after a concurrent event.

Job actions return accepted/rejected results and then hydrate the backend state.
They do not optimistically pop a job or replace active progress with a rejection
error. Transport failures retain the last authoritative state and return an
error for the calling UI to display. There can be an initial hydration delay or
a five-second recovery delay after a missed snapshot notification; this is not
instant delivery guaranteed under disconnection.

## Startup, stop and recovery details

Batch start checkpoints queue records/pause state before freezing/claiming. A
thread construction/start failure restores that checkpoint and the prior render
display. Input is considered accepted only when worker startup succeeds.
Legacy queued start validates the queue ID/path/status and uses the stored job
parameters rather than unrelated replacement parameters.

Auto-advance happens only for queue-associated work, using atomic claims. A
standalone render cannot trigger unrelated accepted/draft video jobs afterward.
Pause prevents the next claim; it does not terminate the active model call. Stop
pauses the queue and preserves the existing deferred cancellation/owned-workspace
cleanup contract. Terminal publication already committed before Stop remains
completed and its output survives.

The worker wrapper finalizes busy state after render/cleanup coordination. A
new start also checks the live worker handle, preserving restart exclusion.
Clearing history/removing records cannot erase the current job while it finishes
cleanup, even though its output is already marked completed.

The existing interrupted-render disk marker still supports restarting a single
interrupted job from the beginning. The App startup path now routes that action
through shared job hydration and reports a rejected restart. An active backend
suppresses the interrupted-job prompt on frontend reconnection.

## File inventory

| File | Change in this iteration |
| --- | --- |
| `core/queue_manager.py` | Drafts, protected history clearing, deep copies, locking, atomic claim, settings freeze/checkpoint/restore and private pywebview exposure. |
| `core/session_state.py` | New in-memory render snapshot/revision holder with stopping and terminal transitions. |
| `bridge/api.py` | Draft/batch/resume/snapshot APIs; coordinated mutations/claims; progress records; startup rollback; busy finalization; reconnect-aware interrupted recovery. |
| `frontend/src/lib/api.ts` | Queue/session/action types and bridge wrappers, including confirmed pending IDs. |
| `frontend/src/lib/job-store.ts` | Shared version-filtered production store and accepted/rejected action handling. |
| `frontend/src/lib/use-jobs.ts` | One event subscription, snapshot hydration/recovery polling and React shared-state hook. |
| `frontend/src/lib/use-queue.ts` | Replace browser path array/pop with backend actions and record selectors. |
| `frontend/src/lib/use-render.ts` | Read shared render state, return start outcomes, support batch start and report stop failures. |
| `frontend/src/pages/Assets.tsx` | Backend job status/history/output/error and pause/resume/removal controls. |
| `frontend/src/pages/Dashboard.tsx`, `Nodes.tsx` | Confirm batch IDs/settings, keep rejected inputs, consume backend records and show batch action. |
| `frontend/src/App.tsx` | Initialize shared store at boot and report interrupted-job restart rejection. |
| `dev/test_queue_session.py` | Twenty-one focused queue/snapshot/startup/recovery regressions. |
| `dev/test_render_queue.py` | Preserve legacy source-event check while also verifying the retained feedback snapshot. |
| `dev/run_cleanup_checks.py` | Include the new regressions. |
| `frontend/dev/verify-job-store.mjs` | Thirteen checks against the actual production shared-store code. |
| `frontend/dist/`, plan/report/logs/evidence | Deliver rebuilt UI and retain the verification trail. |

## Validation results

**319 backend tests passed in 40.747 seconds**: the prior 298 plus 21 new checks.
The full log is `validation/2026-10-03-queue-state-checks.log`.

New tests cover a three-file ordered batch with a middle failure; immutable
settings/records; new drafts during a batch; pause/resume; Stop/resume; repeated
and simultaneous starts; stale confirmation IDs; startup rollback/retained prior
output; invalid/empty starts; missed snapshot notifications; active/pending
removal; protected history during cleanup; single audio isolation; reconnect
recovery; source feedback/revisions; legacy queued-start settings; concurrent
unique claims; draft deduplication and stopping-state protection in both the
render display and queue progress record.

Frontend checks passed: **13 shared-store**, **26 source-language**, **12
cancellation-state** and **8 deletion-preview** checks, **59 total**. Shared-store
tests cover remount retention, delayed/retired-session reads, returned rejection,
retained input/active state, transport failure, output/cleanup busy separation and
newer responses after concurrent events. These are simulated/programmatic checks,
not interactive browser tests.

The production TypeScript/Vite build passed with Vite 8.1.5, **2,854 modules in
3.83 seconds**. Five delivered dist files total **1,021,920 bytes**. The preexisting
large-chunk warning remains. Scoped frontend lint passed without diagnostics;
six changed Python files parsed, new module whitespace and scoped tracked-file
diff checks passed. The existing portable Python used was **3.10.11**.

## Dependency restoration and clearance

189 existing locked frontend packages were restored temporarily in 36 seconds.
No package/version changed; package.json and package-lock SHA-256 hashes match
the prior evidence. After verification, node_modules and `.queue-npm-cache` were
removed, including generated shared-store and SSR fixtures. Clearance checked
absolute workspace containment and reparse entries. Source checks, production
dist, logs and documentation remain.
The cleared directories contained **12,335 files totaling 202,632,863 bytes**
(202.6 MB decimal). This was temporary build/test storage, not a runtime-size
reduction. The original 500 MB portable distribution goal remains unresolved.

Exact removed-file counts/bytes and artifact/package hashes are in
`cleanup/2026-10-03-queue-state/FRONTEND_AND_CLEARANCE.json`. Backend source/log
hashes, check totals and A04/A05/A06 follow-up are in `BACKEND_AND_FOLLOWUP.json`
in that directory. No test job directories remained under the real temp/jobs.
User inputs/outputs/models/runtimes/Git history were not clearance targets.

## Limits and remaining audit work

Queue and session records are intentionally in memory. Navigation and frontend
reconnection to a living backend are supported; backend process shutdown loses
the batch queue/history. Full persistent batch recovery or mid-stage checkpoint
resume is not implemented. Real-model batching, GUI clicks/remounts, cloud
providers and Linux/macOS behavior remain unverified. Large-queue snapshot/polling
overhead is not benchmarked. Output naming/model-registry resolution remain the
existing pipeline behavior.

A04/A05/A06 are implemented with synthetic/programmatic verification; their
interactive/real-provider acceptance remains pending. The historical audit is
preserved and no other finding is closed by this iteration.

The previously observed A02 follow-up remains separate: Nodes' parallel-worker
tooltip and ETA multiplier still make CPU speed assumptions predating serialized
inference. This iteration did not change those estimates or claim a real-model
speedup. That wording/estimate correction needs its own approved scope.
