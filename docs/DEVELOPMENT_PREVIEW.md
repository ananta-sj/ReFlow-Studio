# Automatic development previews

Pushing application/build changes to `main` starts **Build native desktop candidates**.
After the source checks and all four native package/smoke jobs pass, the workflow
updates one public **Development Preview** pre-release:

https://github.com/ananta-sj/ReFlow-Studio/releases/tag/development-preview

The target platforms are Windows x64, Linux x64, macOS Apple Silicon (ARM64), and
macOS Intel (x64). The same release also includes a clean source ZIP, build manifest
and SHA-256 checksums. It is explicitly not marked Latest and does not replace RC2
or stable releases. The application version is not automatically incremented.

## What is bundled

These are desktop previews: application/interface plus Python and desktop packages.
They do **not** reproduce the former local Windows engine bundle. AI environments,
weights, voice references, credentials and FFmpeg/FFprobe need separate setup.
Windows also requires WebView2/Visual C++ prerequisites. Mac previews are not
Developer ID signed or notarized. Successful compilation and model-free smoke
checks are not proof of engine setup, accurate dialogue or full episode quality.
Runtime/model distribution licensing review remains pending.

## Triggers

- Code/build changes pushed to `main`: build and, if successful/current, publish.
- Markdown, README.txt, source-inventory-only, and historical audit/cleanup changes:
  no automatic rebuild when those are the only changes. Runtime lock JSON changes
  still trigger builds.
- Actions → Build native desktop candidates → Run workflow → choose `main`:
  manually rebuild/publish even after documentation-only changes.
- A `v*` tag: retain the existing candidate build behavior; this does not publish
  a stable release automatically.
- Manual runs on other branches build candidates but cannot update the preview.

## Publication and recovery behavior

Only the publish job receives `contents: write`; build jobs remain read-only.
The built-in `GITHUB_TOKEN` is used. No personal access token, local GitHub CLI
login, local model installation or additional Node package is required.
Repository/organization policies must permit Actions and that write permission.

The publisher downloads only this run's candidate artifacts. All four platform
archives and the source archive must be present, nonempty, below the individual
asset size limit, and match their builder-generated SHA-256 sidecars. Unexpected
files fail validation. Private recovery data is not selected for publication.

Downloads include a commit/run/attempt suffix. New files upload without overwriting
the previous download set. The release notes identify the valid set; pending files
can temporarily appear during an upload. Only after all new uploads verify does
the publisher move the lightweight preview tag and update the release notes.
Older generated assets are then removed; manually attached files are kept.

An outdated main build skips publication. Runs for the same ref are serialized
without canceling an active publisher. Main is checked before and after uploads;
a push after the last check can briefly leave an older preview until its next
successful build. An older build is not blindly promoted over a newer observed
main commit. No stable/version tag is moved.

Failed checks/builds never reach publication. Failed uploads leave existing files
and notes intact and attempt to clean their new uploads. Metadata-update failures
are reconciled where possible, with best-effort tag rollback/cleanup. If network
failure prevents confirmation, both asset sets are retained for inspection rather
than deleting potentially published downloads. This is not an atomic GitHub-wide
transaction. Inspect the failed job and release if cleanup cannot complete.

The first release is prepared as a draft until uploads pass. A failed first run
can leave a draft for a rerun/maintainer to inspect. An existing stable, unowned,
or immutable release at `development-preview` is refused. This rolling release
requires mutable releases; immutable-release policies need a different versioned
release design, not weaker checks.

## After pushing this change

1. Open the repository's Actions tab and select the new run.
2. Confirm source plus Windows/Linux/both Mac jobs succeed.
3. Confirm the publish job succeeds, then open the Development Preview release.
4. Choose your platform and the commit/run set identified in its notes. Compare
   its downloaded archive's SHA-256 with the matching SHA256SUMS file.
5. Test a small disposable sample and report the precise build/OS/engine setup.

The automation was locally tested with fixture packages and mocked GitHub API
responses. The real hosted platform builds/upload can only be verified after the
maintainer pushes the workflow. Local validation does not claim a live release.
