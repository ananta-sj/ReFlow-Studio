# Reset and model-removal safety — 2026-10-03

## Approved scope and outcome

The user approved `RESET_MODEL_REMOVAL_PLAN_2026-10-03.md`, including temporary
restoration of existing locked frontend dependencies for verification. This
iteration implements preview-confirmed, bounded reset/removal and download
lifecycle guards. It addresses the remaining application paths identified in
audit findings A03 and A28. No new package, framework, model or service was added.
The historical audit remains unchanged; evidence records follow-up status.

No actual user reset, model deletion, credential deletion, model download or AI
inference was performed during development. Destructive regressions used
disposable storage and mocked credentials. The only actual clearance was of the
temporary frontend dependencies/cache restored for this approved build.

## Before and after

| Trigger | Previous behavior | Current behavior |
| --- | --- | --- |
| Marketplace Remove | Delete stored local_path and download directory, suppress errors, then remove connection. | Preview first; delete only verified entry storage; retain unverified/shared files; report failures. |
| Reset | Generic confirmation; broad Janitor reset with process-name killing and recursive caches; bridge returned success despite warnings. | Show concrete root paths/counts/sizes; require preview token; execute bounded deletion while idle; report partial failures. |
| Active download/install | Not tracked for reset/removal; removal could abandon repository progress while its worker continued writing. | Track before worker starts through finalization; reject reset/removal until tracked work finishes. |
| Files change after confirmation preview | No inventory to compare. | Reject changed file metadata/tree or model registry and require another preview. |
| Another operation starts during deletion | Downloads and registry additions were not synchronized with deletion. | Lifecycle lock excludes new render/download starts and bridge registry mutations until deletion/finalization exits. |
| Credential referenced by two models | Remove selected credential regardless of other references. | Keep shared references; use strict confirmation of unshared credential deletion. |
| Unavailable OS credential store | Credential helper silently returned. | Strict model removal reports incomplete finalization; legacy helper callers retain their default behavior. |

## Ownership policy

Model removal validates a UUID model ID and canonical project containment. The
only automatically deletable model tree is `models/_downloads/<model-id>` under
the configured project model root. The helper checks path ancestors and tree
entries for symlinks/Windows reparse points. Storage roots and paths outside the
project cannot become deletion candidates.

If another registry entry references that tree or an ancestor containing it,
the tree is retained. A local_path outside the entry's tree, including legacy
RVC weights/logs or a user-supplied external model, is retained. The UI explains
retained paths before confirmation and reports them afterward. Removal may
therefore remove a connection without recovering space from its legacy model.
The code does not infer ownership of RVC sibling indexes/configuration files.

Reset includes the configured project temp and output trees plus eligible project
`__pycache__` trees. It rejects overlapping roots and roots overlapping protected
storage. Cache traversal excludes build/runtime, virtual environments, Git and
internal configuration directories, model storage, sample/input directories,
FFmpeg, node_modules and task-specific npm caches; it also skips reparse
directories. Temp/output roots are recreated after successful removal.

Reset still intentionally deletes the **confirmed output files** when a user
executes it. This iteration did not execute it against the real project. The
existing function name remains for compatibility, but its UI describes bounded
cleanup rather than implying every project setting/model is erased.

## Preview and execution contract

The bridge exposes `preview_model_removal(model_id)` and
`preview_factory_reset()`. A successful response includes an opaque token,
candidate paths, counts/bytes and retained-path reasons. The token identifies a
server-side operation/model/fingerprint; the frontend never supplies deletion
paths. Only one preview is retained per bridge instance, so a newer preview
invalidates the older one. Tokens are consumed on execution attempts after the
idle check and cannot be reused or exchanged between models/operations.

`remove_model(model_id, preview_token)` and `factory_reset(preview_token)` require
that preview. Old callers without one receive a refusal. Execution repeats the
busy check, recomputes the plan/fingerprint, and rechecks each candidate tree
immediately before deleting it. Inventory fingerprints use canonical path,
directory/file type, size and nanosecond modification time; they do not hash file
contents. A same-size rewrite with deliberately preserved timestamps is not
detected. Filesystem inspection/deletion is not atomic against external actors.

The lifecycle lock is held through deletion and connection/credential
finalization. Bridge additions, instructions and active-model mutations also
use that lock. Download work itself runs outside the lock, while the tracked
active set prevents destructive actions. Failed thread startup releases tracking
and marks the entry as an error. Transfer completion alone does not release the
guard: installation and finalization must finish first.

The download progress producer is drained even if progress notification fails
or its registry entry disappears. This lets an internal repository-download
worker finish before the tracked guard is released. It deliberately waits;
there is no newly introduced download cancellation or force-kill behavior.
Unregistered download leftovers are retained for verified cleanup rather than
silently removed by a registry-derived path in a finally block.

## Failure semantics

Deletion returns `ok: false`, diagnostic text, processed paths and unfinished
candidate paths on errors. A recursive delete can fail after deleting some
files; the result warns about partial removal instead of promising rollback.
Failure to recreate a cleared root also reports the already processed root.
If planned model-file deletion fails, credential/connection removal is skipped.

After files are processed, an unshared credential is deleted in strict mode,
then the connection is removed. A failure during finalization returns a partial
failure with the processed paths. Already-absent credentials are idempotent;
unavailable stores and a failed delete leaving a secret are errors. Shared
credential references are retained. Filesystem, OS credential store and JSON
registry changes are not one transaction. The preexisting non-atomic registry
save remains a separate audit issue; partial registry mutation on save failure
is not claimed to be repaired here.

## File inventory

| File | Change |
| --- | --- |
| `core/deletion_plan.py` | New containment/reparse checks, model/reset inventories, fingerprints, public previews and bounded execution. |
| `bridge/api.py` | Preview endpoints/token storage; download tracking/draining; lifecycle serialization; replace unrestricted removal/reset bridge paths. |
| `core/credential_store.py` | Optional strict deletion behavior, used by model removal; other callers retain default semantics. |
| `frontend/src/lib/api.ts` | Preview/result types and token-bearing bridge methods. |
| `frontend/src/lib/deletion-preview.ts` | Shared production preview/result text formatting. |
| `frontend/src/pages/Assets.tsx` | Reset preview, confirmed token execution and success/partial-failure feedback. |
| `frontend/src/lib/use-marketplace.ts` | Preview-confirmed connection removal and retained-file/result feedback. |
| `frontend/src/lib/use-confirm.tsx` | Scrollable multiline description so paths and retention reasons remain readable. |
| `dev/test_deletion_safety.py` | Thirty disposable safety and lifecycle regressions. |
| `dev/run_cleanup_checks.py` | Include those regressions in the existing aggregate. |
| `dev/test_model_download.py` | Adapt the opt-in live/manual check to preview removal; remove its old large-model mid-download deletion assumption. Not executed. |
| `frontend/dev/verify-deletion-preview.mjs` | Eight production text-formatting checks. |
| `frontend/dist/` | Rebuilt portable-app UI assets. |
| Plan, report, logs and evidence | Record approved scope, verification, hashes and clearance. |

The legacy `core/janitor.py` was not rewritten. The bridge reset no longer calls
its unrestricted `destroy_all_data()` path. Independent legacy callers require
separate review and are outside this repair's guarantee.

## Validation

**298 backend checks passed in 26.720 seconds**, including the previous 268
and 30 new safety checks. The full log is
`validation/2026-10-03-deletion-safety-checks.log`.

The new regressions cover missing/wrong/reused previews, invalid IDs,
owned-directory deletion, preserved siblings/external/root/shared paths, changed
files/registry, new outputs after reset preview, reparse refusal, reset exclusions,
partial file/recreation/credential failures, shared credentials, idle guards,
download startup/failure/finalization, notification-error producer draining and
new-download exclusion during deletion. No reset or removal touched real media.

Frontend verification passed **8 deletion-preview checks**, **12 cancellation
state checks** and **26 source-language UI checks**. The production TypeScript/Vite
build passed with Vite 8.1.5, 2,852 modules in 8.08 seconds. Delivered dist comprises
five files totaling **1,019,254 bytes**. The existing large-chunk warning remains.
Scoped lint returned exit 0 with the preexisting only-export-components warning
in use-confirm.tsx. These checks do not constitute interactive GUI validation.

Six changed Python files parsed successfully; new helper/test whitespace and
scoped tracked-file diff checks passed. The existing portable interpreter is
Python **3.10.11**. No runtime repair or upgrade was made.

## Dependency restoration, clearance and evidence

189 existing locked frontend packages were temporarily restored in 33 seconds.
`package.json` and package-lock SHA-256 hashes stayed unchanged. No package/version
was added or changed. After verification, frontend/node_modules and the task's
`.deletion-npm-cache` were removed, including the generated UI test fixtures.
Removal verified absolute containment and refused reparse entries.
The two temporary directories contained **12,331 files totaling 202,624,221
bytes** (202.6 MB decimal), all cleared after verification.

Exact removed-file counts/bytes and dist/package hashes are in
`cleanup/2026-10-03-deletion-safety/FRONTEND_AND_CLEARANCE.json`. Backend results,
source/log hashes and audit follow-up are in the same directory's
`BACKEND_AND_FOLLOWUP.json`. Source checks, built assets, report and validation
logs remain available. The 500 MB portable distribution target is not achieved
by this safety repair.

## Remaining acceptance work

Validation was on Windows with synthetic/local fixtures. Real OS credential
stores, real repository downloads/installations, interactive confirmation dialogs
and Linux/macOS behavior remain untested. Large-inventory preview responsiveness
has not been benchmarked; scanning is synchronous and deletion holds the lifecycle
lock. The UI should be exercised with a representative large disposable dataset
before claiming it is responsive at every project size.

A03's bridge render/download exclusions and previews are implemented; A28's
bridge deletion ownership restrictions are implemented. Their real-environment
acceptance is pending. General installer ownership manifests, RVC installer
collisions, download content validation, registry atomicity, external processes
and other audit findings remain separate work. No other findings are closed here.
