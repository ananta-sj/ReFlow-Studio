# Reset and model-removal safety proposal — 2026-10-03

Status: subsequently approved and implemented; see
`RESET_MODEL_REMOVAL_REPORT_2026-10-03.md` for results and limits. No reset, model
removal, download, dependency restoration or production source change was
performed during preparation of the original proposal preserved below.

## Findings checked again

The render guards from the cancellation iteration are present. A03 remains
partially open because `add_local_model()` starts untracked background work and
reset/removal cannot determine whether it is still running. Repository downloads
also use an internal worker inside `download_hf_repo_with_progress()`; merely
closing its progress generator does not prove that worker exited.

For A28, `_remove_model_idle()` trusts `entry.local_path`, recursively deletes
directories without proving ownership, suppresses deletion errors, deletes the
credential first and removes the registry entry afterward. A malicious or
mistaken registry path can therefore name user files or shared storage. An entry
ID also contributes to `_downloads/<id>` without explicit path validation.

Factory reset invokes `Janitor.destroy_all_data()`, including name-based child
process killing, a shared-temp sweep, recursive project-wide pycache removal and
output deletion. Janitor prints warnings on failure but the bridge still returns
`ok: true`. The current UI asks a generic confirmation rather than showing the
concrete files affected. Marketplace Remove invokes deletion without a file
preview.

The RVC installer moves files into shared weights/log directories and can
overwrite an existing filename. Its returned local path does not establish
exclusive entry ownership, and archives can install more than the one returned
checkpoint. Existing shared RVC files must therefore not be assumed disposable
just because a registry entry points to them.

## Proposed implementation

1. **Track active download/install operations before starting the worker.**
   Release tracking only after transfer, installation and finalization finish.
   Handle failed thread startup. Block reset and removal while any managed
   Marketplace download/install or render is active. A common lifecycle lock
   prevents a new transfer/render from racing with deletion. Do not terminate
   downloads as part of this repair.
2. **Create a read-only operation preview.** Return candidate paths, file counts,
   sizes, protected/retained paths and reasons. Show it using the existing
   confirmation UI before execution. Preview does not authorize deletion by
   itself. Revalidate active work and the candidate inventory when executing;
   reject a stale preview instead of silently widening its scope.
3. **Restrict model deletion to provably entry-owned storage.** Validate the
   entry ID, canonical containment and reparse points. Permit deletion of its
   verified `_downloads/<id>` directory. Keep files outside that entry-owned
   directory, shared files, managed storage roots and unverified legacy RVC
   artifacts. Removing an unverified connection removes the registry entry and
   reports retained files; it does not delete those files. A future ownership
   manifest/installer migration is a separate scope.
4. **Make reset explicit and bounded.** Preview the contents of configured
   project temp/output roots and ordinary project pycache directories. Exclude
   runtime/build, virtual environments, Git/internal configuration, model storage
   and input/sample directories from cache traversal. Refuse unsafe, overlapping,
   out-of-project or reparse paths. Replace name-based process killing with an
   idle-work check. Keep the reset contract clear: its confirmed output files
   really are deleted, so the preview must name that consequence.
5. **Report partial failures honestly.** Do not report `ok: true` after a failed
   delete. Retain the model entry/credential when its planned owned-file deletion
   fails, and expose the failure/remaining paths for retry. Remove credentials
   only when no other entry uses the reference. Filesystem, registry and OS
   credential storage cannot be one atomic transaction; record partial outcomes
   rather than promising rollback.
6. **Test and document the boundaries.** Use disposable roots and simulated
   workers. Cover transfer startup/finalization, blocked deletion, unsafe IDs,
   external/root/shared paths, reparse refusal, stale previews, failure reporting,
   credential sharing and normal confirmed deletion. Never exercise reset against
   real project outputs. Rebuild/check the changed UI with the existing locked
   frontend packages, then clear temporary dependencies/cache again.

## Expected file scope

`bridge/api.py`, a small internal deletion/preview helper, the bridge API types,
Assets reset flow, Marketplace removal flow, focused regression checks, the
aggregate test runner and a detailed implementation report/evidence directory.
The reset bridge should stop calling the legacy unrestricted Janitor path;
standalone legacy Janitor callers can be reviewed separately.

No new dependency/framework/tool is required. Temporary restoration of existing
locked frontend dependencies is included only for build and verification.

## Explicit limits

This proposal concerns application behavior; approval to implement it does not
authorize deleting actual user outputs, models or credentials during development.
Tests use fixtures only. It does not repair download content validation, RVC
installer filename collisions, full registry atomicity, general installer
ownership manifests or concurrent external processes. A preview cannot prevent a
hostile filesystem actor from changing paths during deletion; containment and
reparse checks are defensive application checks, not an OS security boundary.

The conservative ownership rule may leave legacy model files on disk after
removing their connection. That outcome must be visible in the preview/result,
not described as disk space recovered. Verified cleanup of those files would
require a separate concrete inventory and user-approved deletion scope.
