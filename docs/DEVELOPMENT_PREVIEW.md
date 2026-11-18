# Automatic development previews

Pushing application/build changes to `main` starts **Build native desktop candidates**.
A shared source job first validates the frontend lockfile with a clean-install dry run. Native jobs wait for this gate. After the source checks and all four native package/smoke jobs pass, the workflow
creates a new versioned public **Desktop Preview** release:

https://github.com/ananta-sj/ReFlow-Studio/releases/latest

The target platforms are Windows x64, Linux x64, macOS Apple Silicon (ARM64), and
macOS Intel (x64). The same release also includes a clean source ZIP, build manifest
and SHA-256 checksums. It is published as a regular GitHub release and marked Latest, with Desktop Preview
in its title. Historical RC2 downloads remain separate releases. Tags increment the patch number in the current 0.7 series: `v0.7.1-desktop-preview`, `v0.7.2-desktop-preview`, etc. The publisher checks existing tags and release drafts before choosing the next unused number. Reserved/failed versions can leave gaps. Source version constants are not rewritten by publication. Release notes include the ten
most recent commit summaries, source links and the matching build.

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
  manually build/publish a new preview even after documentation-only changes.
- A `v*` tag: retain the existing candidate build behavior; this does not publish
  a stable release automatically.
- Manual runs on other branches build candidates but cannot publish a preview.

## Publication and recovery behavior

Only the publish job receives `contents: write`; build jobs remain read-only.
The built-in `GITHUB_TOKEN` is used. No personal access token, local GitHub CLI
login, local model installation or additional Node package is required.
Repository/organization policies must permit Actions and that write permission.

The publisher downloads only this run's candidate artifacts. All four platform
archives and the source archive must be present, nonempty, below the individual
asset size limit, and match their builder-generated SHA-256 sidecars. Unexpected
files fail validation. Private recovery data is not selected for publication.

Downloads include a commit/run/attempt suffix. A new release is prepared as a draft, and its uploads must pass size/digest checks before it is published as a regular Latest release. Release titles include the readable version and **Desktop Preview**. The Latest link follows the newest successful publication. Earlier releases, including the old `development-preview` release and historical RC2 releases, are preserved with their downloads.

The publisher recognizes its own interrupted draft using an exact workflow-run, attempt and source-commit marker. Verified uploads on an owned unpublished draft are reused; matching files with missing or incorrect size/digest are replaced only within that draft. An already published build is left alone, including immutable releases. No existing version tag is force-moved. A conflicting tag fails safely; new numbering considers both repository tags and release drafts. All tags/releases are paginated, so history beyond the first100entries is included. Protecting a tag name/ruleset may still require maintainer action if GitHub refuses creation.

An outdated main build skips publication. Runs for the same ref are serialized without canceling an active publisher. Main is checked before and after uploads. A push after the last check can briefly leave an older preview Latest until the next successful build publishes. No stable/version tag is moved.

Failed checks/builds never reach publication. Failed uploads/promotion clean only this build's unpublished uploads and, when verified safe, its newly created tag. Earlier releases are never cleaned or replaced. An interrupted run may retain a draft for inspection. If a publication response is lost, the publisher checks GitHub before cleanup; uncertain outcomes preserve potentially published files and tags. This is not a GitHub-wide atomic transaction. Inspect failed jobs if cleanup cannot be confirmed.

## After pushing this change

1. Open the repository's Actions tab and select the new run.
2. Confirm source plus Windows/Linux/both Mac jobs succeed.
3. Confirm the publish job succeeds, then open the Desktop Preview release.
4. Choose your platform and the commit/run set identified in its notes. Compare
   its downloaded archive's SHA-256 with the matching SHA256SUMS file.
5. Test a small disposable sample and report the precise build/OS/engine setup.

The automation was locally tested with fixture packages and mocked GitHub API
responses. The real hosted platform builds/upload can only be verified after the
maintainer pushes the workflow. Local validation does not claim a live release.
