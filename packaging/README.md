# Windows portable test candidate

For the native executable, cross-platform Actions workflow and source export,
see [the native build guide](../docs/GITHUB_NATIVE_BUILDS.md). The steps below
describe the verified Windows base assembly used by the executable candidate.

The four volunteer-testing releases for `v0.7.0-rc.2` are described in
[the platform release guide](../docs/RC2_PLATFORM_RELEASES.md). After placing the
downloaded native artifacts and check ZIPs in `release-assets/Releases`, the
development helpers `prepare_tester_releases.py` and `split_platform_releases.py`
validate/copy them and generate the four upload sets. These helpers refuse
existing output directories; they do not publish releases or install engines.

This workflow uses installed local files. It does not install dependencies,
download models, change application defaults or publish a release. The current
Windows source launcher and Python 3.10 desktop runtime are retained. Eight
prepared optional runtimes are included separately; experimental IndicF5 and
IndicTrans2 evaluation profiles and the proposed desktop replacement are omitted.
See `START_HERE.txt` for the resulting package's limits.

Run from the project root with the existing portable Python:

```powershell
.\build\windows-portable\python.exe -B -u packaging/prepare_windows_candidate.py --build
.\build\windows-portable\python.exe -B packaging/check_windows_candidate.py dist/ReflowStudio-Windows-RC1-2026-10-31 --report docs/validation/2026-10-31-portable-core.json
```

The builder refuses an existing candidate directory. It validates the modern
runtime recipes, copies the selected installed files and verifies each copy's
SHA-256. `portable-manifest.json` binds the assembled files to those hashes.
Installer provenance (`direct_url.json`), logs, backups, cache directories,
personal state and downloaded model trees are excluded. Engine-supplied bundled
assets and third-party license files are retained. The original builder's old
500 MB observation is not used as a release gate.

Run the existing hidden desktop acceptance check with the **candidate's** Python,
offline settings and its FFmpeg on PATH:

```powershell
$env:REFLOW_OFFLINE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PATH = "$PWD\dist\ReflowStudio-Windows-RC1-2026-10-31\ffmpeg\bin;$env:PATH"
.\dist\ReflowStudio-Windows-RC1-2026-10-31\build\windows-portable\python.exe -B dev/verify_portable_desktop.py dist/ReflowStudio-Windows-RC1-2026-10-31 docs/validation/2026-10-31-portable-desktop.json
```

Do not pass the historical helper's `--all-pages`/`--cue-review` options here:
those synthetic fixtures are restricted to its older dedicated QA directory.
The default hidden check loads the actual interface and exercises its bridge.
Checks may require normal Windows desktop/file permissions. They do not certify
a clean PC, model inference or visual layout.

Inspect generated files in the candidate after checks and remove only its owned
test state. Keep source workspace settings and media untouched. Then archive:

```powershell
.\build\windows-portable\python.exe -B -u packaging/archive_windows_candidate.py dist/ReflowStudio-Windows-RC1-2026-10-31 --core-report docs/validation/2026-10-31-portable-core.json --desktop-report docs/validation/2026-10-31-portable-desktop.json --report docs/validation/2026-10-31-portable-archive.json
```

The archiver requires passing startup receipts for this candidate, archives only
manifest-listed files, reads every ZIP member back and checks it against the
assembly SHA-256. It refuses to replace an existing ZIP/checksum. A failure is
reported; an interrupted/failed ZIP must not be distributed as a verified one.

The resulting ZIP has one top-level application folder. A separate SHA256SUMS
file verifies the complete ZIP. No application license is selected by this
workflow. Public release, component/model distribution review, fresh-PC testing
and representative complete media workflows remain separate release work.
