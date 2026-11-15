# Clean Windows desktop runtime proposal — 13 October 2026

## Outcome and authorization boundary

This pass prepared a concrete dependency proposal after the desktop import-boundary fixes. **No package or runtime was installed, no package source/wheel archive downloaded, no third-party code built, and no model downloaded or loaded.** Production code and protected user state/model hashes match the preceding boundary receipt. Only development planning scripts, offline tests and documentation were added/updated.

The target remains ordinary Windows x64 **CPython 3.13.16**, reusing the already validated embedded bootstrap from the isolated XTTS candidate. This proposes a separate owned `runtime_profiles/desktop-candidate` evaluation directory. It does not replace `build/windows-portable`, change defaults, launch a new native window, modify system Python/PATH/registry, or migrate the remaining AI workers.

The proposal is **not an installable lock**. A required source-only helper must first be built under separate approval and included in a genuine binary-only resolution. Actual archive bytes, installed metadata, native imports and application behavior then need verification. Windows release eligibility remains false.

## Why the desktop needs these packages

The GUI, state/credentials, queue, graph, cue review, telemetry, media preparation and download controls already use these interfaces. This retains the current framework rather than adding a new GUI or environment manager. Soundfile is included because native Hindi duration prediction reads reference audio properties in the parent process; its NumPy dependency is consequently retained. CFFI also supports the Windows CLR loader. Torch, Transformers, Coqui TTS, RVC, Demucs and visual model libraries are excluded from this desktop proposal; their selected worker routes need independent runtime acceptance. Their exclusion does not make all existing legacy routes functional in a small desktop environment.

## Resolution history and limitations

1. The guarded package-manager dry run used `--ignore-installed`, `--no-cache-dir`, binary-only artifacts and Windows CPython 3.13 target tags. It permits only PyPI index pages and separate wheel metadata; archive transfers/builds/installations are blocked.
2. The initial restricted-network run could not reach the index. Its log and receipt remain retained. A network-enabled metadata-only rerun read the proposed root metadata and found that `proxy-tools`, required by pywebview, has no published wheel. It stopped without fetching its source.
3. A separate JSON-only projection followed dependencies to a fixed point, propagated extras, evaluated Windows/Python 3.13 markers, checked version constraints and selected non-yanked target wheels. It permits a source artifact **only for proxy-tools**, recording that unresolved build explicitly. It does not substitute a fake wheel, remove the dependency, execute setup code or claim package-manager success.
4. This projection uses version-level PyPI dependency metadata. Archive-specific metadata and the source helper's built wheel must still be checked by the actual resolver after approval. Its source archive has no published dependency metadata; the upstream setup view is corroborating evidence, not verification of the archive's bytes.
5. Initial advisory lookup found 38 package/advisory matches across Pillow 11.3.0 (36) and Requests 2.32.5 (2). These are query matches, not 38 independently reproduced vulnerabilities or proof of exploitability. The proposal changes those roots to **Pillow 12.3.0** and **Requests 2.34.2**. Both original and revised projections/scans are retained. No installed version changed.

## Exact revised package proposal

All artifact URLs, published SHA-256 hashes, sizes, Python constraints, parents and dependency strings are recorded in `validation/2026-10-13-desktop-security-candidate-dependency-projection.json`. An index hash is not verification of downloaded bytes. The proposed local proxy-tools wheel will have its own measured size/hash after the separately approved build.

| Package | Exact version | Published artifact bytes | Why included | Declared notice/license |
| --- | --- | ---: | --- | --- |
| audioop-lts | 0.2.2 | 30,503 | pydub audio operations removed from Python 3.13 | PSF-2.0 |
| bottle | 0.13.4 | 103,807 | Required by pywebview | MIT |
| certifi | 2026.7.22 | 136,983 | Required by requests | MPL-2.0 |
| cffi | 2.0.0 | 183,402 | Native-call helper for soundfile and CLR loader | MIT |
| charset-normalizer | 3.5.2 | 206,489 | Required by requests | MIT |
| clr-loader | 0.3.1 | 55,730 | Required by pythonnet | Metadata unspecified; inspect wheel/source notices |
| colorama | 0.4.6 | 25,335 | Required by tqdm | Metadata unspecified; inspect wheel/source notices |
| filelock | 3.20.3 | 16,701 | Existing JSON state locking | Unlicense |
| idna | 3.20 | 69,583 | Required by requests | BSD-3-Clause |
| jaraco-classes | 3.4.0 | 6,777 | Required by keyring | Metadata unspecified; inspect wheel/source notices |
| jaraco-context | 6.1.2 | 7,871 | Required by keyring | MIT |
| jaraco-functools | 4.6.0 | 11,677 | Required by keyring | MIT |
| keyring | 25.7.0 | 39,160 | Existing Windows credential storage | MIT |
| more-itertools | 11.1.0 | 72,226 | Required by jaraco-classes, jaraco-functools | MIT |
| numpy | 2.5.4 | 12,566,113 | Required by soundfile | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| packaging | 26.0 | 74,366 | Existing version/metadata validation | Apache-2.0 OR BSD-2-Clause |
| pillow | 12.3.0 | 7,239,691 | Tray icon/image support | MIT-CMU |
| proxy-tools | 0.1.0 | 2,978 | Required by pywebview | MIT |
| psutil | 7.2.2 | 137,737 | Owned process cleanup and hardware telemetry | BSD-3-Clause |
| pycparser | 3.11 | 51,178 | Required by cffi | BSD-3-Clause |
| pydub | 0.25.1 | 32,327 | Existing audio preparation and mixing | MIT |
| pystray | 0.19.5 | 49,068 | Existing tray menu | LGPLv3 |
| pythonnet | 3.1.0 | 1,644,898 | Windows .NET bridge for pywebview | MIT |
| pywebview | 6.2.1 | 525,463 | Existing desktop HTML interface | BSD-3-Clause (metadata text) |
| pywin32-ctypes | 0.2.3 | 30,756 | Required by keyring | BSD-3-Clause |
| requests | 2.34.2 | 73,075 | Existing HTTP/model discovery and downloads | Apache-2.0 |
| six | 1.17.0 | 11,050 | Required by pystray | MIT |
| soundfile | 0.13.1 | 1,019,162 | IndicF5 reference metadata and native duration estimation | BSD-3-Clause; bundled libsndfile notice review pending |
| tqdm | 4.67.3 | 78,374 | Existing download/integrity helper imports | MPL-2.0 AND MIT |
| typing-extensions | 4.16.0 | 45,571 | Required by pywebview | PSF-2.0 |
| urllib3 | 2.8.0 | 135,717 | Required by requests | MIT |

The revised projection contains **31 packages and 22 active dependency links** satisfying their declared target constraints. Published artifact sizes total **24,683,768 bytes (23.54 MiB)**, including the 2,978-byte source helper rather than a built wheel. This is neither the final download budget nor an extracted installation size. The already-owned interpreter bootstrap totals **22,062,362 bytes** across the captured top-level files; no interpreter download is proposed. Its candidate path configuration would be created separately, without copying XTTS's site-packages.

The revised OSV query completed for all 31 packages with **0 current package advisory matches** at `2026-10-13T15:54:39.066812+00:00`. This does not certify native bundled components, model assets, .NET/WebView2, application code or future advisories. Source/wheel notice verification and native dependency review remain necessary.

## Required helper build: narrow next approval

**Package:** `proxy-tools==0.1.0`, an existing pywebview dependency that supplies Python proxy objects, not an AI model or new framework. [Published source metadata](https://pypi.org/pypi/proxy-tools/0.1.0/json).

- Published source: `proxy_tools-0.1.0.tar.gz`, **2,978 bytes**.
- SHA-256: `ccb3751f529c047e2d8a58440d86b205303cf0fe8146f784d1cbcd94f0a28010`.
- Published archive URL: `https://files.pythonhosted.org/packages/f2/cf/77d3e19b7fabd03895caca7857ef51e4c409e0ca6b37ee6e9f7daa50b642/proxy_tools-0.1.0.tar.gz`.
- Upstream setup lists a Python package and an empty installation-requirements list. It does not declare a native extension; the archive must confirm that before any build. The `nose` entry is a test helper, not an installation dependency. No nose installation, compiler or new build tool is proposed. [Upstream setup](https://raw.githubusercontent.com/jtushman/proxy_tools/master/setup.py).
- Proposed action: download only that hash-bound source, check extraction paths/links/counts/size, inspect its setup and license, and build a wheel using existing owned packaging tools in a temporary workspace directory. Do not enable automatic build isolation or download build dependencies.
- Validate the wheel's name/version/tags, module/source content, safe paths, RECORD hashes and notices; test proxy behavior on the existing owned Python 3.13 interpreter without installing into that runtime.
- Retain the reviewed source, built wheel, notice, hashes and logs as reproducibility evidence. Remove owned temporary build files. Then rerun genuine binary-only metadata resolution with that approved wheel and repeat closure/advisory checks.

**This helper approval would not authorize installing the 31-package desktop candidate.** A later request must present the final resolved artifact list and measured cost, with original runtime/default preservation and native/app acceptance tests. No application license is selected by this proposal.

## Native and licensing acceptance still needed

The Windows backend uses Python.NET and WinForms, with Edge WebView2 selected when its native prerequisites are available. Package wheel compatibility alone cannot prove that a native window launches, renders or handles events on the target computer. Verify Python.NET/CLR loading, WebView2 availability and required native DLLs, then the application controls, state persistence, recovery, batch behavior and graceful unavailable-engine errors. A clean Windows machine remains a separate acceptance gate. [Pinned pywebview Windows backend](https://raw.githubusercontent.com/r0x0r/pywebview/6.2.1/webview/platforms/winforms.py), [Python.NET runtime behavior](https://pythonnet.github.io/pythonnet/python.html).

Declared license labels above are inventory information, not completed distribution review. In particular, pystray metadata declares LGPLv3; certifi and tqdm include MPL labels; soundfile, NumPy and Pillow may bundle native components with additional notices. Read the actual selected artifacts, collect notices/source obligations and resolve the owner's application license before publishing. Unspecified CLR-loader/Colorama/jaraco-class metadata must be checked rather than assigned an assumed license. Existing FFmpeg/model and prior third-party obligations remain open.

## Validation and preservation

Five offline planning tests passed: correct Windows/Python target wheel choice, rejection of yanked/incompatible artifacts, explicit source exception, propagation of dependency extras/target markers, and rejection of direct dependency URLs. These are five new planning-tool checks; the preceding **800-test production backend acceptance is historical and was not rerun**, because no production code changed in this pass. No native UI or new runtime acceptance is claimed.

All eight final planning integrity checks passed, including production/boundary source preservation, five saved user-state hashes, eight original XTTS asset hashes, satisfied projected links, completed advisory scan with zero current matches, planning test success and continued absence of the owned Ollama trial. The prior portable QA artifact and its historical receipts were not refreshed.

## Retained evidence

- `validation/2026-10-13-desktop-candidate-resolution.log` and `...-resolution-receipt.json`: initial restricted-network failure.
- `validation/2026-10-13-desktop-candidate-network-enabled-resolution.log` and matching receipt: genuine binary-only resolution stopped at proxy-tools.
- `validation/2026-10-13-desktop-candidate-dependency-projection.json` and `...-advisories.json`: original package projection and 38 advisory matches.
- `validation/2026-10-13-desktop-security-candidate-dependency-projection.json` and `...-advisories.json`: revised complete metadata projection and point-in-time scan.
- `validation/2026-10-13-desktop-dependency-projection-tests.log`: five offline tests.
- `validation/2026-10-13-desktop-runtime-plan-integrity.json`: source/state/model checks and reusable interpreter bootstrap file hashes/sizes.

Release work after the helper/desktop candidate remains: clean remaining AI workers, actual supported-runtime/native/portable validation, representative full workflows, resource/parallel calibration and licensing. Windows portable is first; Linux/macOS remain experimental.
