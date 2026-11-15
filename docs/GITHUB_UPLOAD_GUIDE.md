# Publishing source from the consolidated checkout

Use the existing repository at `C:\Projects\Reflow Studio\Reflow Studio`.
Add that folder in GitHub Desktop; no second clone or source-copy folder is needed.
The development branch is `codex/episode-readiness`, based on the published `main`.
The native repository's former history is preserved on
`codex/native-history-before-consolidation`.

The development changes are currently uncommitted. The selected source files are
prepared in Git's staging area for your review and commit. No commit, push, tag
or release was performed by this work. Local experimental notes and media outside
the selected source inventory remain on disk and should not be added wholesale.

You may publish this as a development source update now, with the limitations in
the README. That does not make it a new tested executable or an episode-ready
release. Suggested commit title:
`Improve recovery, GPU routing, character review and development documentation`.

In a terminal opened in this folder:

```text
git diff --cached --stat
git commit -m "Improve recovery, GPU routing, character review and development documentation"
git push -u origin codex/episode-readiness
```

Use the staged selection; do not run `git add .` to include all local research
notes. In GitHub Desktop, inspect the selection before committing, since its
checkboxes can include additional unstaged/untracked files. After pushing, open a
pull request from this development branch to `main` if you want to merge it.

## Review what Git will publish

In this checkout, use `git status --short` and GitHub Desktop's Changes panel.
Application source belongs in `core/`, `bridge/`, `frontend/src/`, `packaging/`,
`.github/`, and the root source/launcher/license files. Reviewed tests and user
documentation are also source. Keep the existing vendor notices.

The ignore rules exclude models, installed runtimes, executables, release ZIPs,
temporary media, output/review/checkpoint data, personal settings, credentials,
personal samples, diagnostic archives and local validation receipts. Do not use
force-add to bypass these rules. `core/Wav2Lip/models/` is application code;
the root `models/` folder contains downloaded weights and remains excluded.

Refresh the source inventory with
`python packaging/create_source_archive.py --manifest-only` after final source
changes. This creates no release ZIP. The source archive exporter can produce a
separate source-only ZIP if needed, without copying installed engines or media.

Once the development has passed its acceptance checks, review the staged diff,
commit it on the development branch, push that branch and merge through GitHub.
Do not label the source episode-ready until continuous multi-character listening
and complete-episode checks have actually passed. Current published binaries do
not automatically include these source changes.

## Executables

Publish tested executable archives as GitHub Release assets, not as ordinary
repository files. Generate new platform builds from the final source revision;
do not reuse the old RC2 executable as evidence that this development was tested.
Keep Windows companion files together. Linux/macOS desktop previews still need
their own engine and fresh-machine validation.

See [checkout details](DEVELOPMENT_CHECKOUT.md),
[review workflow](REVIEW_WORKFLOW_2026-11-15.md) and
[cleanup policy](DISPOSABLE_CLEANUP.md).
