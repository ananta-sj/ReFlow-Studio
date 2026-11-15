# Desktop helper build and dependency-lock completion — 13 October 2026

## Outcome and scope

The user explicitly approved **only the proxy-tools helper build, testing without installation, and desktop dependency-lock preparation**. That work is complete. No desktop runtime was installed, no working environment upgraded, no application default changed, and no model downloaded or loaded. No new framework, compiler, package manager or system integration was introduced.

The proposed target remains Windows x64 CPython 3.13.16, using the already-owned embedded bootstrap. A genuine binary-only metadata resolver now completes with the approved local helper. The independently checked target lock contains **31 packages and 22 satisfied active dependency links**. This is package preparation, not native application or clean-machine release acceptance. Release eligibility remains false.

## Approved source and inspection

The fetched `proxy_tools-0.1.0.tar.gz` was exactly **2,978 bytes**, matching SHA-256 `ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010`. Extraction checked resolved destinations within the owned temporary directory, archive member count and total size, and rejected links/devices/non-file types. The original archive is retained unchanged for reproducibility.

Actual setup inspection confirmed a single Python package, `proxy_tools`, an empty `install_requires` list and no declared native extension or setup dependency. The `nose` reference is test metadata; nose was neither needed nor installed. The module implements deferred Python proxy objects used by the existing pywebview dependency chain. No speech model or new application framework is involved.

The first inspection assumed the archive included `LICENSE`, but it does not. That inspection failed before building; its temporary directory was removed and its failure log retained. The corrected inspection retained the actual setup/module files and exposed a genuine notice discrepancy: setup/package metadata says MIT, while the module header says BSD and credits Armin Ronacher (2013) and Jonathan Tushman (2014).

## Supplemental notice and unresolved labels

The upstream repository supplies `LICENSE.txt` with the matching copyright holders and BSD terms. Its content was retained from pinned commit `db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6`, with SHA-256 `a428fb8a2e762af3eb0a6edbbb88e9b42ccfee80fd9b423958bcacf9b9abbfe4`. [Pinned upstream notice](https://raw.githubusercontent.com/jtushman/proxy_tools/db43f1e35d4f90a65c5a4d56d9e9af88212ec6e6/LICENSE.txt).

A supplemental `LICENSE.upstream.txt` was added only to the temporary packaging tree and explicitly included through a `setup.cfg` metadata addition. The Python module and original archive were not rewritten. The built wheel retains the existing MIT metadata and BSD module attribution rather than concealing the disagreement. Its receipt marks distribution notice review incomplete. Retaining the upstream notice helps preserve attribution; it does not resolve the contradictory labels or choose a license for Reflow. This remains a distribution review item before publishing.

## Build and real Python 3.13 acceptance

The build used the existing Python **3.10.11**, setuptools **80.10.2** and wheel **0.47.0**. It invoked the source's ordinary `bdist_wheel` setup through a controlled wrapper, without build isolation or dependency installation. The wrapper blocks DNS, socket connection/bind and datagram sends during setup; environment settings also disable package-index use. Temporary paths remained inside the owned build directory.

The resulting universal wheel is:

- File: `proxy_tools-0.1.0-py3-none-any.whl`.
- Size: **3,956 bytes**.
- SHA-256: `96819a976602a3c8147a9575fb3765a507341244431567a3292cc838886082c5`.

Validation checked safe wheel paths, package name/version, absence of runtime dependencies, byte equality between the original module and wheel module, included supplemental notice, and every hashed RECORD entry's content and size. A real subprocess using the existing owned **Python 3.13.16** interpreter imported the module directly from that wheel on its process-local import path. Dictionary lookup, forwarding mutation and length assertions passed. Its printed module path confirms that the tested code came from the new wheel, not an installed copy. The wheel was not installed into either runtime.

Existing packaging tools emitted setup.py/license-classifier deprecation warnings, and byte compilation was disabled. These warnings did not fail the wheel or target execution checks. No new packaging tool was installed to suppress them.

The owned temporary build directory was removed. The approved source, built wheel, source inspection, original setup/module, supplemental notice, build output and smoke receipt remain under `docs/validation/2026-10-13-proxy-tools-helper` as intentional reproducibility evidence, not an installer cache.

## Genuine resolution and target closure

The resolver verified the local helper hash before using it alongside the reviewed desktop roots. It retained `--dry-run`, `--ignore-installed`, `--no-cache-dir`, `--only-binary=:all:` and explicit Windows CPython 3.13 target parameters. Its network guard allowed public index pages and separate wheel metadata, blocked remote archive transfers, and permitted no source build within resolution. No installation took place despite the package manager's `Would install` output.

The raw resolver selected 34 packages because some dependency markers are evaluated against its Python 3.10 host. Independent checking used Windows/Python 3.13 markers, propagated extras/reachability to a fixed point, checked root pins and version constraints, verified target wheel tags and Python ranges, and reconciled artifact filenames/URLs/hashes/sizes against published version metadata. It correctly excluded:

- `importlib-metadata` and its `zipp` dependency, not required for the target by keyring's older-Python marker.
- `backports-tarfile`, not required for the target by jaraco.context's older-Python marker.

The resulting target lock has **31 packages and 22 active links**. The actual resolver selected `more-itertools==11.2.0`, whereas the preceding JSON projection had selected 11.1.0. The final artifact metadata and dependency constraints were verified for 11.2.0, and the advisory query was repeated for all final versions. No projected version was silently substituted after locking.

## Final reviewed artifacts and cost

The complete names, versions, parents, dependency strings, target environment, URLs and hashes are in [the final lock review](validation/2026-10-13-desktop-candidate-lock-review.json). [The hash-bound review lock](validation/2026-10-13-desktop-candidate-review.lock.txt) contains the exact artifact references; it is not authorization to install them. Package reasons and initial notice inventory remain in [the desktop proposal](DESKTOP_RUNTIME_PROPOSAL_2026-10-13.md), with the more-itertools correction above.

All root versions retain the revised proposal: pywebview 6.2.1, Python.NET 3.1.0, psutil 7.2.2, pydub 0.25.1, audioop-lts 0.2.2, soundfile 0.13.1, CFFI 2.0.0, Requests 2.34.2, filelock 3.20.3, packaging 26.0, keyring 25.7.0, pystray 0.19.5, Pillow 12.3.0 and tqdm 4.67.3. The remaining packages are required support dependencies, including NumPy 2.5.4 for soundfile, the approved proxy helper, CLR loading, credential helpers and HTTP/text dependencies.

Final artifact sizes total **24,686,927 bytes (23.54 MiB)**:

- Remote wheels still to download after installation approval: **24,682,971 bytes**.
- Already-built local helper: **3,956 bytes**, reused without another source download.
- Already-owned interpreter bootstrap: **22,062,362 bytes**, copied into the candidate with checked hashes, without copying XTTS's package environment.

These are artifact/bootstrap measurements, not extracted installation size or complete portable-app footprint. Remote hashes are verified published values; remote wheel bytes have not yet been fetched and hashed. The local helper's actual bytes have been verified. The final OSV query completed on 13 October for all 31 packages with **zero current package advisory matches**. That is a point-in-time query, not certification of native libraries, .NET/WebView2, source code, models or future advisories.

## Preservation and final checks

All **12 consolidated checks passed**: helper build/target smoke, helper/lock hash agreement, retained notice, owned workspace cleanup, valid target closure, final advisory acceptance, previous production/boundary source preservation, five original saved-state hashes, eight original XTTS asset hashes, original bootstrap hashes, unchanged isolated XTTS runtime identity and continued absence of the owned Ollama trial.

The earlier 800-test backend run remains historical acceptance of unchanged production source. It was not rerun for this packaging-only pass. The previous portable QA artifact and historical evidence were not refreshed. No native window, full video, new desktop environment or clean-machine behavior was tested here.

Added/updated development tools: `build_approved_proxy_helper.py`, `prepare_desktop_runtime_lock.py`, `check_desktop_candidate_lock.py`, `audit_desktop_dependency_projection.py` and `verify_desktop_helper_lock_completion.py`. Their current hashes and final lock hash are bound in the completion receipt. Production settings, defaults, model registry and media assets were not edited.

## Concrete next installation proposal

The next request is separately bounded: create **only** `runtime_profiles/desktop-candidate`, copy the verified existing Python 3.13.16 bootstrap, download and verify the **30 remote wheels** from the final 31-package lock, and reuse the verified local proxy wheel. Install/extract only that exact package closure into the owned candidate, preserving all current environments and application defaults. No AI model, API call, compiler, new package manager or system-wide runtime/PATH/registry change is included.

Acceptance should check duplicate metadata, target dependency closure, import origins and versions, Python.NET/native desktop prerequisites, startup/bridge/template/state controls, audio decoding/metadata and selected isolated-worker routing. Use disposable state and existing media. Remove owned installer staging after verification; retain the candidate and evidence for comparison. Report native or engine failures rather than claim complete app acceptance.

This desktop evaluation does not migrate Whisper/NLLB/Demucs/RVC or other legacy workers. Remaining supported-runtime migration, native clean-machine/full workflow acceptance, resource/parallel calibration and owner/third-party/model licensing remain release gates. The proxy notice-label conflict also remains visible for distribution review.

## Evidence

- Initial missing-license inspection failure: `validation/2026-10-13-proxy-tools-source-inspection.log`.
- Corrected actual-source inspection: `validation/2026-10-13-proxy-tools-source-inspection-corrected.log`.
- Approved helper files, build/smoke logs and receipt: `validation/2026-10-13-proxy-tools-helper/`.
- Resolver report/log/network guard receipt: `validation/2026-10-13-desktop-candidate-with-approved-helper-resolution-*` and matching resolution log.
- Target closure/budget: `validation/2026-10-13-desktop-candidate-lock-review.json`, `...-review.lock.txt`, `...-lock-check.log`.
- Final exact-version advisory receipt: `validation/2026-10-13-desktop-resolved-lock-advisories.json`.
- Final source/state/model/bootstrap and identity checks: `validation/2026-10-13-desktop-helper-lock-integrity.json`.
