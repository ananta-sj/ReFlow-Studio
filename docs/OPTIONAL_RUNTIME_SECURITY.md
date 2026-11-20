# Isolated engine security setup

The desktop preview and optional AI environments are separate. The old all-in-one `portable_requirements.txt` now forwards to the desktop-only manifest; it no longer installs outdated AI libraries into the GUI environment. Existing environments are not automatically removed or upgraded.

## Reviewed MuseTalk CPU environment

The current recipe targets **Windows x64 / CPython 3.11.18**, with a complete hash-locked package set in `packaging/optional/musetalk.lock.txt`. It passed offline imports, native operators and synthetic forward checks. Trained-model output and GPU acceptance are separate; this does not establish lip-sync quality or GPU support.

1. Read `packaging/optional/python-runtime.json`. Download its exact archive from the recorded URL to `build/optional-python/`, using the recorded filename. Do not substitute a floating release. Setup verifies its size and SHA-256 before extraction.
2. From the source checkout, run:

   ```powershell
   & .venv\Scripts\python.exe dev\prepare_optional_runtime.py musetalk --python-archive build\optional-python\cpython-3.11.18-windows.tar.gz --install
   ```

3. Setup refuses to overwrite an existing profile. Preserve any old profile before preparing a replacement; an interrupted install may use `--resume` only with the same reviewed bootstrap.
4. Verification checks the installed dependency set and records the actual interpreter version. Workers use isolated Python startup. They do not inherit user-site or environment package paths. A changed dependency lock invalidates old readiness until the profile is verified again.

The setup command intentionally installs software; it is not run during dubbing or normal UI startup. No model weights are included or downloaded by profile preparation.

## Reviewed F5 CPU setup

The updated F5 recipe targets the same Windows x64 / CPython 3.11.18 bootstrap, with a separate complete 148-package hash lock. Its offline checks passed local cache/lock handling, guarded API import, a small random-weight DiT forward, and synthetic WAV decoding. **No trained speech or GPU acceptance is implied.** A fresh end-to-end installation from the public recipe still needs a separate clean-machine check.

The upstream cache package caps filelock below the patched major version. ReFlow's explicitly identified compatibility wheel changes only its distribution metadata; upstream implementation and licence files remain unchanged. Do not substitute a differently built wheel or install with `--no-deps`.

1. Obtain the reviewed Python archive as above.
2. Obtain the upstream cache wheel using `packaging/optional/cached-path-compat.json`. Build its reproducible compatibility wheel:

   ```powershell
   & .venv\Scripts\python.exe dev\build_cached_path_compat.py <downloaded-upstream-wheel>
   ```

   The builder checks both the upstream and output SHA-256 identities. Its default output directory is `build/optional-wheels`.
3. Obtain and extract the shared FFmpeg archive recorded in `packaging/optional/ffmpeg-shared.json`, using an extractor already installed on your system. Setup checks each required DLL, README and licence against the reviewed sizes/hashes, and copies only those files into the new profile. A static `ffmpeg.exe` alone is insufficient. Setup does not install an extractor or change system FFmpeg.
4. Prepare the profile explicitly:

   ```powershell
   & .venv\Scripts\python.exe dev\prepare_optional_runtime.py f5 --python-archive build\optional-python\cpython-3.11.18-windows.tar.gz --ffmpeg-directory <extracted-ffmpeg-package-root> --install
   ```

   `--wheelhouse` can specify an alternate directory containing the exact reviewed compatibility wheel. Existing profiles are preserved. Resume requires the reviewed interpreter; mismatched existing decoder files are preserved and rejected.

F5 and MuseTalk stop with a setup error when their isolated profile is missing, outdated or unverified. They do not fall back to importing those engines in the desktop runtime. Verification checks isolated startup, actual Python version, bootstrap provenance, exact package inventory and feature probes before recording readiness. Engine setup remains explicit; it never runs during a dub.

## Legacy enhancement and security alerts

BasicSR has no patched upstream release for the distributed-training command-injection advisory. ReFlow's isolated face-enhancement worker disables those exact-source training launchers, blocks shell/network access and verifies its runtime/source recipe before use. That is an application mitigation, not a claim that upstream BasicSR 1.4.2 is patched. Shared automatic installation of optional engines through the desktop integrity helper is prohibited.

Dependency updates require review and checks; no automatic PR merge is configured. Keep alerts visible until remediation or a documented reachability assessment is verified. No scan result guarantees that a project is vulnerability-free.
