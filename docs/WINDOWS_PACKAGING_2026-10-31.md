# Packaging handover — 31 October 2026

Prepared locally; nothing was pushed, uploaded, tagged or published on GitHub.

## Ready to review

- `dist/ReflowStudio-Windows-Executable-RC1-2026-10-31.zip` — 3,005,813,593
  bytes. Extract the entire archive and open `ReflowStudio.exe` inside its
  application folder. All 192,871 archive members were checked against their
  SHA-256 values, including the base and executable manifests.
- `dist/ReflowStudio-Windows-Executable-RC1-2026-10-31.SHA256SUMS.txt` — complete
  executable ZIP checksum:
  `4fc237ed2ec18bd0ac75ad783f648d39f503fa56f3afa73099b17816d157fd58`.
- `dist/github-windows-download/` — two verified parts, 1,900,000,000 and
  1,105,813,593 bytes, with a Windows reassembly script, instructions, manifest
  and checksums. Concatenating the parts reproduces the verified executable ZIP.
- `release-assets/ReflowStudio-source.zip` — 832 source files, 4,524,608 bytes,
  including the new root README, native workflow, packaging scripts and vendor
  source. SHA-256:
  `f962a04222084dbe773caba6b0b7e6e97294436f916c4b4ef4d717beee5b64a3`.
- `README.md` — new GitHub README, written after reviewing the existing project
  page and checking the current local implementation. It replaces the older
  interface/startup instructions and describes actual setup and platform scope.
- `.github/workflows/build.yml` — native Windows x64, Linux x64, macOS ARM64 and
  macOS Intel desktop preview jobs, plus a clean source export job.

The Actions workflow creates review artifacts only. It has not run on GitHub.
Its desktop previews are deliberately distinguished from this full local
Windows engine bundle: optional local AI runtimes and FFmpeg are not included
in those previews. See `docs/GITHUB_NATIVE_BUILDS.md` for requirements and limits.

## Checks completed

- The new executable ran the included Python and passed the offline package
  check and hidden Windows interface acceptance check. The interface/backend
  connection worked with no reported JavaScript errors.
- Relocated core startup, six bound modern runtime recipes, three prepared
  optional runtime selections, FFmpeg and FFprobe passed checks.
- Previously tested speech-repair source hashes were preserved. No audio
  generation code, model weights or working engine environments were changed.
- Sixteen new packaging contracts and eleven existing packaging regressions
  passed. The frontend TypeScript check and production rebuild passed.
- The actual generated Windows reassembly script rebuilt a small fixture ZIP
  correctly and refused to overwrite its existing ZIP. Its initial dependence
  on an unavailable shell cmdlet was replaced with built-in .NET operations.
- The source export was read back and checked. It includes real model-named
  source folders and nested vendor source; private state, media, downloaded
  weights, Git metadata, installed runtimes and logs are excluded.
- New Python syntax, workflow YAML structure, README relative links and
  `git diff --check` passed. Disposable test fixtures were removed.

The owner approved PyInstaller installation in the separate
`build/executable-tools-20261031` folder. PyInstaller 6.22.3 and its build-only
dependencies were installed there. The existing runtime was reused read-only;
no model was downloaded. Earlier base-assembly receipts predate that approval
and correctly describe their earlier no-install stage.

## Release work still open

This is a test candidate. A fresh Windows PC test, first-use model/reference
setup and representative complete media workflows on the final package remain.
The app license and component/model distribution review remain pending.
Linux/macOS native builds, engine execution and public distribution requirements
remain unverified. macOS writable-data/signing behavior needs further work;
its preview is not Developer ID signed or notarized.

Existing models, media, outputs, credentials and project state were preserved.
The standalone EXE depends on its companion folders; do not distribute it alone.

## Receipts

- `docs/validation/2026-10-31-packaging-summary.json`
- `docs/validation/2026-10-31-executable-archive.json`
- `docs/validation/2026-10-31-executable-core.json`
- `docs/validation/2026-10-31-executable-desktop.json`
- `docs/validation/2026-10-31-native-packaging-contracts.log`
- `docs/validation/2026-10-31-source-export.log`
- `docs/validation/2026-10-31-release-assembly-fixture.json`
