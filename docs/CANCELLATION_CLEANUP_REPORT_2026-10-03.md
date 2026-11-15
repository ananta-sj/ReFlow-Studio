# Cancellation and cleanup implementation — 2026-10-03

## Outcome and scope

The user approved the cancellation and cleanup plan after the full project audit.
This iteration implements the lifecycle repair for audit finding A01, plus the
active-render guards required to keep reset and model removal from undermining
that repair. It introduces no framework, package, model, cloud service or
dependency version change. Existing unrelated working-tree edits remain present;
this report describes this iteration, not the entire diff against Git HEAD.

Stop now requests cancellation and leaves the UI busy with a **Stopping** message.
The backend waits for active work and registered subprocesses to exit before
cleaning the job's temporary directory and emitting the final stopped event.
Another render cannot start while the previous render is still active. Already
published valid outputs remain intact; an unpublished result is discarded when
cancellation wins the publication lock.

This is an implemented and regression-tested lifecycle repair, with the real
model, GUI and cross-platform acceptance work below still outstanding. It is
not evidence that every issue in the full audit has been fixed.

## Observable behavior

| Situation | Result |
| --- | --- |
| Stop during an owned subprocess | Request cancellation, terminate/reap the tracked process tree, then clean the job workspace. |
| Stop inside a native/in-process AI call | Show Stopping until the call returns; skip subsequent stages and discard uncommitted output. |
| Stop while waiting for an inference lock | Recheck cancellation after acquiring the lock; do not invoke the engine. |
| Stop during parallel segment work | Signal the shared job context, cancel pending futures at the cancellation boundary, and join running workers before cleanup. |
| Late progress or stage event while stopping | Keep the stopping state and its current progress. |
| Stop with no active job | Return an idle acknowledgment without sweeping temporary files or sending an unrelated stopped event. |
| Start another render while stopping | Reject the new start. |
| Reset or remove a model during an active render | Return a rejection message; the frontend displays it. |
| Cleanup detects unsafe paths, reparse points or an error | Retain the directory and report a warning with its path. |
| Owned processes cannot be confirmed stopped | Retain the workspace and active context, block restart, and avoid a false stopped event. |
| Stop after a result was already atomically published | Preserve that valid result. Cancellation does not undo a completed publication. |

“Stopping” permits active calls to finish writing inside their owned workspace.
It does not mean all writes cease at the instant the button is pressed. The
contract is that cleanup waits for those users to exit and cancellation prevents
later publication. Forcefully killing a Python thread inside a native library
would not be safe.

## Implementation inventory

| File | Change in this iteration | Purpose |
| --- | --- | --- |
| `core/render_context.py` | New job context, thread-local binding, cancellation exception, publication lock, owned process runner and scoped cleanup. | Coordinate work, output commitment and cleanup under one job owner. |
| `bridge/api.py` | Active context lifecycle; stop request/final acknowledgment separation; generator checks before advancing; restart/reset/removal guards. | Prevent early idle/cleanup and new work during cancellation. |
| `core/pipeline.py` | Job-specific temp directory, explicit worker context propagation, cancellation boundaries, executor joining, owned media commands and guarded output publication. | Apply the same lifecycle to sequential and parallel pipelines. |
| `core/pipeline.py` | Forward the actual source reference explicitly to speech synthesis. | Preserve reference availability after moving extracted audio out of shared temp. |
| `core/audio_separator.py` | Job-specific separator output and owned subprocess execution. | Keep separation artifacts and execution under the render job. |
| `core/lipsync_handler.py` | Job-specific Wav2Lip artifacts, absolute input/script paths, owned subprocess and work-directory argument. | Retain required imports while isolating generated files. |
| `core/Wav2Lip/inference.py` | Optional `--work_dir`; temporary video and clean-audio paths use it. | Isolate intermediates written by vendored inference code. |
| `core/providers/lipsync/musetalk_local.py` | Job-specific config/results and owned subprocess. | Isolate MuseTalk output, including its result-relative artifacts. |
| `core/providers/stt/whisper_local.py` | Owned process and job-local temporary transcription directory. | Keep Whisper worker artifacts inside the job workspace. |
| `core/enhancer.py` | Cancellation checks in frame processing and before result acceptance. | Stop additional enhancement work at safe boundaries. |
| `core/providers/filter/nudenet_local.py`, `vision_classifier_local.py` | Frame-loop cancellation boundaries. | Stop further moderation-frame work after cancellation. |
| `core/providers/cloud_rest_common.py` | Checks around requests and interruptible polling waits. | Avoid another poll/stage after stop while preserving existing request timeouts. |
| `core/model_assets.py` | Checks around asset selection, transfer chunks and replacement. | Cancel partial download work without replacing a valid model after stop. |
| `core/llm_translator.py` | Checks during discovery/request handling; interruptible retries; cancellation rethrown from fallback handlers. | Avoid translation retry/fallback work after stop. |
| `frontend/src/lib/render-state.ts` | New production event-state reducer and shared busy-state predicate. | Keep Stopping authoritative until the final backend event. |
| `frontend/src/lib/use-render.ts` | Use the reducer; retain busy state while stop is pending. | Remove the previous immediate transition to idle. |
| `frontend/src/lib/api.ts` | Stop acknowledgment and rejected reset/removal response types. | Describe the changed bridge contract. |
| `frontend/src/pages/Dashboard.tsx`, `Nodes.tsx` | Disable repeated Stop while stopping. | Make pending cancellation visible and avoid repeated requests. |
| `frontend/src/pages/Assets.tsx`, `frontend/src/lib/use-marketplace.ts` | Show reset/removal rejection messages. | Explain why a destructive action is blocked during a render. |
| `dev/test_cancellation.py` | Twenty focused cancellation/ownership regressions. | Exercise lifecycle races, output preservation and real process behavior. |
| `dev/test_render_queue.py` | Adapt lifecycle expectations and isolate fixture workspaces. | Preserve queue/error semantics under deferred cleanup. |
| `dev/run_cleanup_checks.py` | Include cancellation tests in the existing aggregate. | Keep the new regressions in repeatable verification. |
| `frontend/dev/verify-cancellation.mjs` | Twelve checks against the production state reducer. | Verify stopping, late events, final acknowledgment and normal completion. |
| `frontend/dist/` | Rebuilt production assets. | Supply the changed UI to the portable app. |

Direct stage/CLI callers without a job context retain their previous default
directories and subprocess behavior. This iteration does not claim to convert
all standalone commands into cancellable jobs.

## Ownership and synchronization details

Each bridge-managed job owns `temp/jobs/job-<unique-name>/`. Pipeline scratch
files, separation output, Whisper temporary JSON, Wav2Lip intermediates and
MuseTalk config/results use that job directory. Model storage and final output
directories remain outside it. Normal bridge-managed renders no longer sweep
the entire shared temp root. Successful jobs retain or clean scratch data
according to the existing auto-cleanup setting; cancelled jobs attempt scoped
cleanup after active users have exited.

Process launch and cancellation share the context lock: a launched process is
registered before a stop request can pass that lock. The runner polls for
cancellation and timeout, retains discovered descendant identities, escalates
termination when necessary and waits for exit. A failure to confirm exit retains
ownership rather than allowing cleanup. Unrelated processes are not targeted.

Final output replacement and cancellation also share a lock. If stop wins, the
replacement is refused and existing output survives. If replacement wins, the
newly published valid file survives. Pending output staging is removed through
the existing staged-output cleanup path.

Workspace cleanup validates canonical containment and refuses symlinks and
Windows reparse points before recursive deletion. This protects against ordinary
misrouting/tampering; it is not an atomic filesystem security boundary against a
hostile process changing paths during deletion.

## Verification and evidence

- **262 backend tests passed in 19.904 seconds**, including the previous 242
  checks and 20 cancellation regressions. Full output:
  `validation/2026-10-03-cancellation-checks.log`.
- Real disposable Python processes verified success/nonzero exit, timeout
  reaping, cancellation, owned-descendant termination and preservation of an
  unrelated process. Tests also cover cancellation before launch.
- A blocked-call barrier verified that the temporary workspace and recovery
  marker remain intact while work is active; restart is rejected; after release,
  the cancelled item is recorded, the next queued item remains queued, cleanup
  completes and exactly one stopped event appears.
- Tests covered thread-local binding, unsafe cleanup paths, reparse refusal,
  registered-process cleanup refusal, preserved sibling/output files, publication
  ordering, pending-output removal, interruptible polling, waiting-inference
  cancellation and reset/model-removal guards.
- **12 frontend cancellation-state checks** and **26 existing source-language
  UI checks** passed. These are programmatic checks, not browser interaction.
- Production frontend build passed: Vite 8.1.5, 2,851 modules, 2.01 seconds.
  The existing large-chunk warning remains; bundle splitting is outside this
  iteration. The five delivered dist files total **1,017,883 bytes**.
- Scoped frontend lint passed; 17 changed Python files parsed successfully.
  The scoped final diff whitespace check passed after two trailing spaces were
  removed. This does not claim all preexisting repository lint issues are fixed.
- `package.json` and `package-lock.json` SHA-256 hashes stayed unchanged.
  File hashes, artifact sizes and exact temporary clearance totals are recorded
  in `cleanup/2026-10-03-cancellation/VERIFICATION_AND_CLEARANCE.json`.

The existing portable Python used for verification is **3.10.11**. No Python
upgrade or runtime/dependency repair was performed in this iteration.

## Temporary dependency restoration and clearance

The existing locked frontend packages were restored solely to build and verify
the approved UI change. The first network attempt failed with DNS resolution
errors. A sandbox-escalated retry restored 189 existing packages successfully.
No manifest/lockfile versions changed and no package was added to the project.

After verification, `frontend/node_modules` and the task-specific
`frontend/.cancellation-npm-cache` were removed. The deletion checked absolute
workspace containment and rejected reparse entries. Generated UI test fixtures
inside node_modules were removed with it. Sixteen empty job directories from an
early test fixture were individually verified empty and removed without
recursive deletion. The evidence JSON records exact file counts and bytes.
The two temporary dependency/cache directories contained 12,332 files totaling
**202,764,082 bytes** (202.8 MB decimal); the empty test directories added zero
file bytes.

The production dist, source checks, validation log and documentation are retained.
User inputs, samples, outputs, model storage, portable Python, FFmpeg, `.venv`
and Git history were not clearance targets in this iteration. The original
500 MB distribution goal remains separate and has not been achieved by this fix.

## Verification limits and remaining work

1. No real TTS/RVC/F5/Whisper/Demucs/lip-sync/enhancement/moderation inference,
   live cloud request or model download was exercised. Those require an approved
   representative test set and actual provider resources. The backend tests mock
   model boundaries; they cannot establish real engine behavior or speed.
2. Validation ran on Windows. Linux and macOS cancellation, subprocess and
   portable launch behavior remain unverified.
3. Native inference, synchronous HTTP and a blocking third-party/file-lock
   acquisition can delay cancellation until they return or time out. The UI
   remains stopping; this implementation does not promise instant termination.
4. Descendants are discovered through psutil polling, not a Windows Job Object
   or POSIX process group. A very short-lived parent/reparented child can escape
   discovery. The real descendant regression verifies the covered behavior;
   it does not prove containment of every possible provider process tree.
5. If termination fails, retained ownership intentionally blocks another render.
   There is no new automatic recovery monitor. Resolve the owned process and
   restart the app before retrying; investigate the retained workspace first.
6. Factory reset and model removal now have active-render guards. Their broader
   download concurrency, affected-file preview and deletion ownership problems
   from A03/A28 are not fully resolved.
7. This does not repair shared CPU speech-engine concurrency (A02), hook state
   loss after navigation, output stems, visual/moderation failure policy,
   download integrity in other installers, registry consistency, packaging,
   environment conflicts or the other full-audit findings.

The original audit and issue register are preserved as the historical snapshot.
The follow-up status file in this iteration's evidence directory records A01 as
implemented with acceptance limitations and A03 as partially addressed. It does
not mark the other findings closed.

## Reproducing checks

Run the existing portable Python with `-B dev/run_cleanup_checks.py` from the
project root, with TEMP/TMP directed at the project's temp directory. No model
download or inference is needed for that aggregate. It excludes destructive
reset/keyring tests.

For frontend checks, restoring the existing locked packages is required again:
run the production build, `node dev/verify-cancellation.mjs`, and
`node dev/verify-source-language.mjs` from frontend. The temporary generated
fixture files go beneath node_modules. Dependency restoration and any further
fix scope remain subject to the user's request for approval before new actions.
