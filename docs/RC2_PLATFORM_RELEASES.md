# Four platform releases — v0.7.0-rc.2

The displayed application release version is **`v0.7.0-rc.2`**. RC2 means Release
Candidate 2. Publish four distinct GitHub **pre-releases**, targeting the same
uploaded source commit. Each release needs its own tag and platform-specific assets.

| Folder under `release-assets/Releases/RC2/` | Suggested tag | Release title |
| --- | --- | --- |
| `Windows-x64` | `windows-x64-v0.7.0-rc.2` | ReFlow Studio v0.7.0-rc.2 — Windows x64 |
| `Linux-x64` | `linux-x64-v0.7.0-rc.2` | ReFlow Studio v0.7.0-rc.2 — Linux x64 Desktop Preview |
| `macOS-Apple-Silicon` | `macos-arm64-v0.7.0-rc.2` | ReFlow Studio v0.7.0-rc.2 — macOS Apple Silicon Desktop Preview |
| `macOS-Intel` | `macos-x64-v0.7.0-rc.2` | ReFlow Studio v0.7.0-rc.2 — macOS Intel Desktop Preview |

Open a platform folder and read its `RELEASE-DETAILS.md`. Copy the supplied title,
tag and description into GitHub, then attach **only the files inside that
platform's `Upload-to-GitHub` folder**. Select **This is a pre-release** on each.
Do not upload the parent folder or another platform's files.

The Windows release uses the fuller engine-bundle parts and assembly script.
Its complete large ZIP is retained under `Windows-x64/Local-only`; that ZIP is
for local use and is not in the GitHub upload set. Linux and both Mac downloads
remain desktop previews requiring separate AI runtimes/models and FFmpeg.
All archive bytes are preserved from the verified builds.

Each set includes its own checksum list, current project README, platform test
guide and feedback template. GitHub also offers source archives for the selected
tag; an additional manual source ZIP is not required among these binary assets.

Platform-prefixed tags keep the common version while distinguishing the four
release records. The current workflow automatically builds tags starting with
`v`; these platform-prefixed publication tags do not start four duplicate full
builds. Manual Actions runs remain available. If application code changes, run
and validate fresh native builds before publishing changed binaries.

The older combined upload set is retained under `_reference` for rollback. Use
the four platform folders for this release. Publish the updated README/source
before selecting the source commit for the four tags. No tags, pushes or releases
are created by these preparation scripts.

This is a volunteer-testing pre-release, not production certification. Native
CI desktop checks passed, but real-machine GUI/model workflows remain under
evaluation. Application/component licensing review remains pending.
