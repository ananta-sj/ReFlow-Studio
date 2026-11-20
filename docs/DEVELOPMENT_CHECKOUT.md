# Use the current checkout

The active source is the Git checkout containing this document. The maintainer currently works in the GitHub/ReFlow-Studio checkout, on main, using GitHub Desktop to review, commit and push. Locate the actual folder in GitHub Desktop with **Repository -> Show in Explorer**; do not recreate the deleted former app directory or follow an old branch name from a historical report.

Before work, inspect the current branch, git status and latest commit. Preserve uncommitted changes. External contributors may use their own forks/branches as described in CONTRIBUTING.md; that does not authorize an agent to create branches in the maintainer's checkout.

The earlier checkout-consolidation notes described a previous arrangement and are historical. This document replaces those operational instructions. Do not assume the old backups, model files or runtime environments still exist.

Only source is recoverable from GitHub. Ignored models, runtime profiles, media, credentials, settings, outputs and job checkpoints need their own intentional backups if the owner wants to retain them. Do not delete them merely because source is pushed.

See README.md for setup, OPTIONAL_RUNTIME_SECURITY.md for isolated engine recipes, and NEXT_CHAT_HANDOFF.md for the next testing session. Packaging/create_source_archive.py exports selected source while excluding private/generated content. Refresh the inventory rather than copying one from an old release.
