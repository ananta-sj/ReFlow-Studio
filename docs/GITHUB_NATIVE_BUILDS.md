# Native builds and source downloads

The GitHub Actions workflow is `.github/workflows/build.yml`. It runs manually
from **Actions → Build native desktop candidates → Run workflow**, or when a
`v*` tag is pushed. It builds on native runners: Windows x64, Linux x64, Apple
Silicon macOS and Intel macOS. A separate job exports the source archive.

This change prepares workflow code only. No workflow was dispatched, repository
pushed, tag created, source uploaded or release published from this chat.

## Downloads and current scope

Each successful native job saves a candidate download and SHA-256 checksum in
its Actions artifacts. Windows uses ZIP; Linux and macOS use tar.gz to retain
executable permissions and links. Macs get an `.app` bundle. The source artifact
is `ReflowStudio-source.zip`, with source files, build scripts, tests, interface
inputs and the bound runtime recipe documents. Local media, downloaded models,
working Python environments, credentials, settings and diagnostic logs are not
exported. Real source directories such as `core/Wav2Lip/models` are retained.

**CI outputs are desktop previews, not the full locally tested Windows engine
bundle.** They include native relocatable Python and the desktop dependencies.
Optional local AI engine environments, model weights, voice references and
credentials require separate platform-specific setup and acceptance. FFmpeg and
FFprobe must currently be available separately on PATH in those CI previews.
The locally assembled Windows candidate additionally contains FFmpeg and eight
prepared engine environments; it does not require system Python.

The executable is a PyInstaller launcher for the included Python application.
It keeps inference in the existing separate runtimes and preserves the reviewed
audio code. Keep all companion files; the EXE alone is not the application.

## What the workflow checks

- Interface dependencies are installed from the existing npm lockfile and built.
- Packaging contracts check launcher behavior, source exclusion rules, checksum
  rejection and protection against archive traversal.
- A platform/architecture-specific Python archive is downloaded from the pinned
  upstream release and checked against its recorded SHA-256 before extraction.
- Desktop packages are installed in that bundled Python; `pip check` must pass.
  The exact resulting versions are retained in a separate check artifact.
- The native executable runs an offline, model-free check using its own included
  Python. This checks core libraries, the interface files, relocated application
  paths, worker selection, empty model connections and duplicate-launch locking.
- Generated test state is removed before the candidate is archived. Archives
  are read back and whole-download checksums are generated.

The workflow has read-only repository permissions and uploads Actions artifacts.
It has no step that publishes or modifies a GitHub Release. Build tools and
desktop dependencies are installed on disposable GitHub runners, not into the
owner's working audio environments. The Python runtime source URLs and hashes
are recorded in `packaging/ci_runtime_sources.json`.

## Validation still required before release

The new workflow has been checked locally for Python/YAML syntax and packaging
contracts, but has not run on GitHub. A successful future CI job is not a clean
machine or complete media workflow certification. Test native GUI startup,
model/reference setup, real inference, exports, long jobs, cancellation/recovery,
GPU routes and distribution prerequisites on each supported target.

Linux uses Qt for the preview; distribution-specific native dependencies still
need acceptance. The macOS app is only ad-hoc signed for development, not
Developer ID signed or notarized. Its writable application-data layout and
signing/update behavior require further work before treating it as a public Mac
release. Neither platform is promoted to release-ready by these build scripts.

The app's license choice and component/model distribution review remain pending.
`LICENSE.txt` currently contains Python's license/history; this workflow does
not select an application license or grant redistribution rights.

GitHub documents a limit of **under 2 GiB per Release asset**. The local Windows
engine bundle is larger, so it needs smaller parts or separately packaged
optional engines before upload. Source files belong in the repository; generated
runtime binaries belong in Release downloads, not regular Git history.

The local `dist/github-windows-download-RC2` folder prepares two verified parts of
the Windows executable ZIP. Download both parts and `Assemble-ReflowStudio.cmd`
into one folder, run that script, then extract its reconstructed ZIP. The script
uses built-in Windows tools, checks each part and the complete ZIP, and refuses
to overwrite an existing complete ZIP. This prepares files for future upload;
it does not upload them.

## Upstream references

- [PyInstaller platform build requirements](https://pyinstaller.org/en/latest/)
- [Native Python release and asset hashes](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026)
- [GitHub runner architectures](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Release asset limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [pywebview platform prerequisites](https://pywebview.flowrl.com/guide/installation.html)
