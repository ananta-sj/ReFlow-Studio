# Saved-state safety review and proposed iteration

Date: 2026-10-03. Status: A07 saved-state foundation implemented; see
PERSISTENCE_SAFETY_REPORT_2026-10-03.md for final behavior and verification.
Related historical finding: A07, priority P1.

## Review scope and evidence

This review inspected the local implementation after the queue/session repair.
It did not change executable code, load or rewrite real user state, install
packages, delete files, or run real-model jobs. Findings below are established
by source inspection; failure-injection and concurrency verification are
proposed acceptance checks, not checks already passed in this iteration.

| Store | Current implementation | Consequence |
| --- | --- | --- |
| Model registrations, core/model_registry.py | _save opens models.json with mode w; mutations change internal entries/active selections before saving; no store-level lock | Opening truncates the previous file. An interrupted write can leave partial JSON. Failed saves leave memory ahead of disk. Concurrent download/UI updates can interleave. |
| Backend preferences, core/settings.py | _save directly overwrites settings.json; update/reset change memory first | A failed write can lose saved preferences and still change what the current process displays. |
| Interrupted-job marker, core/render_state.py | mark_started directly overwrites render_state.json | The crash-recovery record can itself be incomplete after a crash. |
| Hardware cache, core/hardware_profile.py | capture replaces self._profile before directly overwriting hardware_profile.json | Failed refresh can leave the cache on disk inconsistent with the profile in memory. This cache is recomputable. |

All four loaders lack complete structure validation. For example, a registry
whose JSON root is a list reaches data.get and can raise AttributeError.
Settings may accept values with the wrong type. Hardware data can pass loading
yet fail when consumed. Malformed JSON and some read errors are silently treated
as empty/default state; the original cause is not communicated to the user.

Registry list/get/add/update results also expose internal dictionaries. A caller
can modify an entry without going through validation, locking or a save. Returning
a new outer list does not protect nested entry dictionaries or metadata.

The bridge lifecycle lock protects some recently repaired operations, but it
does not supply a complete store transaction boundary for every caller. The
registry needs its own synchronization, including download-thread updates.

## Proposed next implementation scope: A07 saved-state foundation

1. Add one small internal JSON persistence helper. Serialize the candidate
   completely before publication; write a uniquely named temporary file in the
   destination directory; flush and sync it; replace the destination atomically.
   On a failed write/replacement, preserve the existing destination and clean
   up only the helper's own temporary file. Preserve Unicode data.
2. Serialize reads and mutations using a consistent lock order and canonical
   per-path thread synchronization. Use the already declared filelock dependency
   for cooperating processes; both requirements.txt and portable_requirements.txt
   already include it and core/model_assets.py already uses it. No new dependency,
   tool or framework is proposed. Mutations must reload the latest valid disk
   state under the lock before applying a change, so separate store instances
   cannot overwrite another instance's update with stale memory.
3. Build changes on a private candidate. Validate and persist it before replacing
   the in-memory state. Failed persistence must leave memory and disk unchanged
   and return a useful error through existing bridge handling. Return defensive
   copies from public registry/settings/hardware reads and mutation results.
4. Validate each store's root shape and required fields before using it. Preserve
   supported optional metadata and existing valid identifiers/paths. Reject
   newly submitted malformed values before writing. Add settings type/range
   checks based on the current UI/API contract, without inventing new settings.
5. Preserve malformed existing bytes in a uniquely named recovery copy before
   allowing replacement. Report the file and reason through existing warning/error
   surfaces. If preservation fails, refuse replacement. A missing file is normal
   first-run state; permission/read errors must not be treated as a missing file.
   Do not automatically delete recovery copies. Use defaults/empty state only
   with an explicit corruption warning and successful preservation; hardware
   cache corruption can instead trigger detection again.
6. Migrate writes for all four stores to the shared helper. Keep normal
   render-marker clearing idempotent for an absent file, but surface other
   removal errors so the bridge's existing warning handler can report them.
7. Document final behavior, compatibility changes, exact checks, evidence and
   remaining limits. Preserve the original audit as a historical snapshot.

Likely production files: a new helper under core, core/model_registry.py,
core/settings.py, core/render_state.py, core/hardware_profile.py, and narrowly
scoped bridge error/warning handling if necessary. Existing test fixtures that
depend on modifying returned registry dictionaries will need explicit fixture
setup rather than bypassing the repaired public API.

Locks and replacement protect cooperating callers. They do not promise an
all-or-nothing transaction across the registry, credential service and model
files, nor guaranteed survival of every hardware/power failure. Cross-store
transactions, network filesystem guarantees and persistent batch queues remain
outside this proposed iteration.

## Acceptance and verification plan

Use disposable state files and the existing portable Python/test runner.
Do not use actual models.json/settings.json or real credentials as fixtures.

| Scenario | Required result |
| --- | --- |
| Serialization, temporary-write or replace failure | Prior destination bytes and in-memory state stay unchanged; error is reported; no owned temporary-file leak. |
| Concurrent independent mutations | Same-process threads, separate store instances and cooperating subprocesses preserve all accepted updates in valid JSON. |
| Termination before/after publication | Destination is a complete prior or complete new JSON record; any crash-left temporary artifact is documented and cannot be read as live state. |
| Malformed JSON or wrong structure | Original bytes remain recoverable; warning identifies the affected store; replacement is blocked if preservation fails. |
| Invalid new settings/entries/profile/recovery record | Mutation is rejected without changing disk or memory. |
| Returned entry or nested metadata modified by caller | Stored state remains unchanged. |
| Existing valid data and first-run missing files | Existing supported values load correctly; defaults remain compatible. |
| Existing queue, deletion and cancellation suites | Previously repaired behavior remains intact. |

Run the aggregate backend checks after targeted checks pass. Restore only
existing locked frontend packages if frontend changes are actually required;
then run the relevant existing checks/build and clear that temporary tooling
storage with the previously established containment checks. Record actual
results in a separate implementation report; no test totals are claimed here.

## Additional findings requiring separate approval

### Interrupted-render offer is consumed before acceptance

core/render_state.py::get_interrupted reads and then immediately clears the
record. frontend/src/App.tsx asks the user about restarting only after that
call. If the app closes while the dialog is open, or startRender refuses the
restart, the saved record has already disappeared. clear also currently
suppresses removal errors, potentially producing the opposite behavior: an
old offer can reappear without an explanation.

Atomic saving alone does not fix the early-consumption behavior. A separate
follow-up should make reading non-destructive, add explicit discard/acknowledgment
with a record identity so stale dialogs cannot clear a newer job, and retain
the old recovery record until a replacement job is durably recorded. An accepted
worker-thread start alone is insufficient if it subsequently fails before saving
the new marker. Test rejected starts, dialog reloads, failed marker writes,
explicit discard and newer-record protection. This remains restart from the
beginning, not continuation from a pipeline checkpoint.

### Parallel-worker guidance and ETA assumptions are stale

frontend/src/pages/Nodes.tsx still describes CPU inference as genuinely faster
through concurrent model calls. bridge/api.py::_parallel_speedup_factor still
assumes a CPU inference advantage: four workers apply approximately 0.339 times
the baseline TTS/RVC stage cost. The earlier speech repair now serializes managed
model inference on CPU and GPU; work outside inference can still overlap.

A separate small follow-up should correct the tooltip and remove unsupported
worker-count speed discounts until representative measurements justify them.
The existing helper test only checks both factors exceed 0.1; it does not verify
an estimate against measured execution. No real-model speed claim is justified
by the current synthetic checks.

### A08 activation compatibility remains separate

Structural validation must not be described as fixing provider compatibility.
Wrong-stage activation and adapter/availability checks need their own approved
behavior and acceptance cases. This proposal does not close A08.

## Authorization boundary

The latest approval authorized reviewing the next issue and preparing this
proposal. No runtime implementation has been changed by this review. Requested
next approval is the A07 saved-state foundation above. Interrupted-offer behavior,
parallel guidance/ETA corrections and activation compatibility are recorded
follow-ups rather than silently included changes.
