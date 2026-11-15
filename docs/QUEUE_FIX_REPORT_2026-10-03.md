# Backend render queue repair — 2026-10-03

## Authorized scope

The user approved inspecting the queue before any edits, then approved a backend
repair, focused regression tests, and documentation. After discussing parallel
processing, the user chose **one active render** for this step. This repair adds
no tools, frameworks, dependencies, model weights, or downloads.

This report describes this step only. Earlier cleanup is documented separately
in `CLEANUP_REPORT_2026-10-03.md` and its follow-up clearance report. Existing
uncommitted changes were retained. No commit, push, release, or deployment was
performed.

## Confirmed problems before the repair

1. `_run_render_inner()` caught pipeline exceptions, emitted `render_error`,
   and returned normally. `_run_render()` interpreted that return as success,
   leaving the UI error and queue's `completed` status in disagreement.
2. Finishing without an output also emitted an error without propagating
   failure to the queue worker.
3. `QueueManager.get_next_queued()` returns a `QueueItem` object. The bridge
   indexed it like a dictionary, causing `TypeError` during auto-advance.
4. Even correcting the indexing would leave a second problem: the bridge
   attempted to call `start_render()` from the still-running worker.
   `start_render()` rejected that request because a render was already active.
5. Cancellation could leave a queue item in `processing`; output paths were
   not saved on successful queue items.
6. Exceptions during render-state clearing or optional temporary cleanup could
   prevent the subsequent queue job from being considered.

## Changes by file

### `bridge/api.py`

- Added a standard-library `threading.Lock` around checking and creating the
  render worker. Concurrent start requests cannot both pass the idle check.
- Kept the existing response for a rejected start: `{ok: false, message:
  "A render is already running."}`. An accepted start still returns `{ok: true}`.
- Changed `_run_render()` into a loop owned by one worker. It uses
  `QueueItem.input_path`, `.params`, `.template_id`, and `.id` to take the next
  pending job, rather than dictionary subscripting or creating another worker.
- Moved interrupted-render state recording into each iteration. Each active
  job gets its own recorded input, parameters, and template, then state cleanup.
  A failure to record that state becomes a render error rather than escaping
  the worker silently.
- When a queue job starts, reset its progress, old error, and old output path,
  and mark it `processing`.
- On success, save `output_path`, mark `completed`, and set progress to 100
  before emitting `render_finished`.
- On failure, save the error text and mark `failed` before emitting
  `render_error`. The worker then considers the next queued job, matching the
  previous intent to auto-advance after a failed job.
- On observed cancellation before a terminal result is recorded, mark the
  active item `cancelled` and leave remaining jobs queued. Emit no finished or
  error event for this cancelled render; the existing stop event handles the UI.
- Track whether a terminal result has already been recorded, so a stop request
  during subsequent cleanup does not relabel a completed job as cancelled.
- Catch render-state and temporary-cleanup errors separately, log warnings,
  and preserve the job's result and ability to consider the next job.
- Preserve queue pause semantics: pause prevents selection of the next job;
  it does not suspend the currently running pipeline. Unpausing does not launch
  an idle worker automatically, consistent with the previous API.
- Let pipeline errors propagate from `_run_render_inner()` to the worker,
  which now owns terminal status and event handling.
- Fail when the pipeline produces no result, or returns a path that is missing
  or points to an empty file. A nonempty file is a basic existence check; it
  does not prove that the media is valid or every pipeline stage succeeded.
- Close the pipeline generator when leaving `_run_render_inner()`, including
  cooperative cancellation, so generator cleanup blocks can execute.

### `dev/test_render_queue.py`

Added 14 regression tests using Python's existing `unittest` and mock facilities.
They call the actual bridge lifecycle methods and actual `QueueManager`, with
simulated pipeline generators and tiny temporary output files. They substitute
GUI event delivery, interrupted-render disk state, and Janitor operations.
Bridge construction is bypassed to avoid hardware, registry, and GUI startup.

| Check | Expected result |
| --- | --- |
| Successful queued render | Completed, progress 100, output saved, one finish event |
| Pipeline exception then next job | Failed with error; next job completes |
| Generator finishes without output | Failed with one error event |
| Missing output file | Failed |
| Empty output file | Failed |
| Two queued jobs on a real worker thread | Input order preserved; same thread processes both |
| Paused queue | Active job completes; next stays queued |
| Stop during a generator | Active job cancelled; next stays queued; generator closes |
| Stop as generator finishes | Cancelled; no success event |
| Temporary cleanup raises | Job results preserved; next job runs |
| Render-state cleanup raises | Next job runs |
| Stop during post-success cleanup | Completed result preserved; next stays queued |
| Direct render without queue ID | Existing finish event preserved |
| Start while a worker is active | Rejected; a later start works after the worker exits |

These are lifecycle tests, not AI quality or full media-render tests.

### `dev/run_cleanup_checks.py`

Added the new queue test module to the existing nondestructive backend runner.
The runner now checks 36 cases: 14 existing backend checks, 8 model-recovery
checks, and 14 new render queue checks. Destructive Janitor and credential-store
tests remain excluded.

### This report

Added `docs/QUEUE_FIX_REPORT_2026-10-03.md` as the review and validation record.
No frontend, dependency manifest, queue-manager source, pipeline engine, or
model configuration was edited during this step.

## Validation and reproduction

Validated using the bundled Windows portable CPython 3.10.11 interpreter.
Bytecode generation was disabled to avoid repopulating caches.

Run from the project root in PowerShell:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

Final result: **36 tests passed**, approximately 3.1 seconds of reported test
execution time, with exit code 0. No real models were downloaded or invoked.
Temporary fixtures were removed; the workspace `temp` directory was empty
after validation.

The first standalone invocation via `python -m unittest dev.test_render_queue`
could not locate `dev` under the embedded interpreter's isolated search path.
Running the test file directly works because it adds the project paths itself;
the existing aggregate runner also adds them.

The first aggregate run passed all new queue tests but failed the existing
mocked model-download atomic replacement test with Windows access denied in
the sandbox's external temporary directory. Re-running with the workspace
temporary directory passed all 36 checks; no model-recovery implementation
change was needed.

`git diff --check -- bridge/api.py` passed. The whole-workspace check still
reports the previously documented trailing whitespace in
`core/hardware_monitor.py:310`; that unrelated user change was preserved.
Git also reports its configured future LF-to-CRLF conversion notices.

## Behavior deliberately left for a separately approved step

- The React video list (`frontend/src/lib/use-queue.ts`) remains separate from
  the Python batch queue. This backend repair does not wire the Dashboard list
  into automatic batch execution or add queue controls to the UI.
- Jobs execute sequentially. Existing within-render segment-worker settings
  remain unchanged; independent videos do not render in parallel.
- The queue remains in memory. Interrupted-render recovery restarts one job
  from the beginning; it is not persistent batch or stage checkpoint recovery.
- Cancellation remains cooperative at pipeline yields. It does not immediately
  interrupt an in-process model call. Existing subprocess termination and
  temporary cleanup in `stop_render()` were retained, including their current
  limitations.
- Shared UI progress events remain untagged by job ID. Full frontend batch
  integration will need to associate progress and outcomes with individual jobs.
- No new queue admission validation or atomic claim/removal mechanism was
  introduced. Concurrent edits to queue items and invalid caller-supplied queue
  IDs remain outside this lifecycle repair.
- Engine code that silently returns fallback text/audio, produces stale files,
  or ignores subprocess failures still needs a separate error-propagation
  review. Checking a nonempty output path cannot detect all such failures.
- No complete AI render, GUI interaction, fresh installation, Linux/macOS run,
  GPU run, or release packaging validation was performed.

## Suggested next approval

Inspect and propose fixes for hidden pipeline failures, particularly unchecked
FFmpeg exits and TTS errors that currently allow rendering to continue. This
should be discussed and approved before changing those stages. Frontend queue
integration and parallel processing are separate product decisions.
