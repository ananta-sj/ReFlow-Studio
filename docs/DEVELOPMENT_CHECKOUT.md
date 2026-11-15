# One development checkout

Use `C:\Projects\Reflow Studio\Reflow Studio` for development and Git. This folder contains the active models/runtimes and is now based on the published GitHub history at `origin/main`.

The development branch is `codex/episode-readiness`. Its unstaged changes include the developments made after the published version. No changes have been committed or pushed as part of consolidation. Review source changes before publishing.
Local push settings publish the current development branch under its own name; they do not map it onto `main`. GitHub Desktop should offer to publish this development branch once its changes have been committed.

The native repository's former history is preserved on `codex/native-history-before-consolidation`. The published history is also retained under `github-local/main` and `origin/main`. Working files were kept in place when the index was aligned with the published baseline.

The separate folder `C:\Projects\Reflow Studio\Github\ReFlow-Studio` was an older, clean copy. It has been retired after a complete ZIP backup and checksum readback. The parent folder contains a pointer to this canonical checkout. The local backup and receipt are in `docs/diagnostics/checkout-consolidation`; the source comparison is in `docs/diagnostics/checkout-consolidation.json`. Keep the backup until the consolidated development has been reviewed and committed.

In GitHub Desktop, add the existing repository at the development path above. Existing model weights, runtimes, outputs, temporary files and personal samples remain excluded from Git. Source archive creation uses `packaging/create_source_archive.py`; source manifests should be regenerated with each archive, not copied from an old release.

Episode readiness remains under development. A passing unit test or recovered job is not evidence of a natural full-episode dub. Require a continuous multi-character listening test and a complete episode with no unresolved spoken cues before describing this version as episode-ready.
