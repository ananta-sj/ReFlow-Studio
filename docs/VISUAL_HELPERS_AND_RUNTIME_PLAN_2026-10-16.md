# Visual helpers completed and separate runtime proposal — 16 October 2026

## Decision

The approved **BasicSR 1.4.2 and FilterPy 1.4.5 helper builds and dependency-lock preparation are complete**. Preparation acceptance passed all **18 checks**. No runtime was installed, model downloaded, or application default changed. Temporary build staging was removed; reviewed wheels, source/build notices, hashes and diagnostic evidence remain in `docs/validation`.

The proposed runtime is **not security-cleared or release-approved**. The advisory review found two records for **one distinct vulnerability**, CVE-2024-27763, in BasicSR's SLURM training launcher. A no-install guard prototype blocks that path; production integration and actual modern image inference remain future work. This finding is carried in the lock rather than hidden by the successful preparation result.

See [consolidated preparation acceptance](validation/2026-10-16-visual-helpers-acceptance.json), [prepared lock](validation/2026-10-16-visual-runtime-lock-review.json), and [the preceding approved scope](F5_STARTUP_REPAIR_AND_VISUAL_PLAN_2026-10-16.md).

## What was downloaded and built

| Approved source | Download bytes | Source SHA-256 | Built wheel bytes |
| --- | ---: | --- | ---: |
| BasicSR 1.4.2 | 172,524 | `b89b595a87ef964cda9913b4d99380ddb6554c965577c0c10cb7b78e31301e87` | 214,937 |
| FilterPy 1.4.5 | 177,985 | `4f2a4d39e4ea601b9ab42b2db08b5918a9538c168cff1c6895ae26646f3d73b1` | 110,628 |

The only downloaded package archives were those two approved sources: **350,509 bytes combined**. Other network transfers were package indexes, metadata, a wheel HEAD request, and public advisory records. The proposed runtime's other wheel archives have not been downloaded.

Builds reused Python 3.10.11 and existing setuptools 80.10.2/wheel 0.47.0. BasicSR declares setup requirements Cython, NumPy and Torch; existing versions 3.2.4, 1.23.5 and 2.1.2+cu118 satisfied those build requirements. No build dependency was installed. This build host is distinct from the proposed Python 3.13.16 runtime.

BasicSR's native extension branch is enabled only by `BASICSR_EXT=True`; the build explicitly set it to `False`. Build-process audit hooks rejected networking and child-process/shell execution. BasicSR's optional git lookup was inactive because the extracted archive contained no `.git` directory. It generated its normal `version.py` file during the build. No compiler was invoked and no source code in installed packages was edited.

Extraction rejected traversal, drive paths, links, case-insensitive duplicates and oversized archives. Each wheel's RECORD hashes and lengths were verified. The verifier byte-compared **128 Python source files** against the extracted build source trees and separately syntax-checked BasicSR's generated `version.py` file. Python 3.13 compiled all **129 files**. Both built wheels contain their package notices: BasicSR Apache 2.0 text and FilterPy MIT text. This notice collection does not clear all bundled third-party code/model redistribution rights.

Exact wheel hashes, requirements, inspected source hashes and included notice paths are in [the build receipt](validation/2026-10-16-visual-helpers/build-receipt.json). FilterPy's built wheel SHA-256 is `ae6f2793252a7a47587b18d09dc6b04c76153749797ea8b481c84d084c25aafa`; BasicSR's exact built hash is recorded alongside it. Generated build timestamps mean this run does not establish reproducible rebuilding.

## Real no-install checks

[Seven helper checks passed](validation/2026-10-16-visual-helpers-smoke.json) under actual **Python 3.13.16 / Torch 2.14.1+cpu**:

- Both wheel byte hashes matched, and all 129 source files compiled.
- FilterPy imported from the built wheel and performed a finite Kalman prediction/update with a measurement correction.
- BasicSR's unchanged CPU `upfirdn2d` operator, loaded independently from the wheel, preserved an identity-filter test image.

The BasicSR test deliberately exercises one real operator independently; it does not import the complete BasicSR/GFPGAN stack. No modern face-restoration inference, detector/parser model load, GPU operation or perceived image-quality approval is claimed. Existing legacy GFPGAN's preceding successful three-frame test remains historical evidence for that legacy environment only.

## Exact dependency closure and resolver

The proposed Python 3.13.16 CPU runtime has **55 packages and 96 active dependency edges**. Of those packages, **41 can be copied from the existing modern XTTS candidate**, **two are the approved built helpers**, and **12 require separately approved downloads**. The original runtime metadata and RECORD hashes are preserved.

The independent audit matches every resolver-selected version and artifact SHA-256 against its prepared source: established XTTS artifact lock for copied packages, built-wheel hashes for the helpers, and official artifact metadata/index hashes for proposed downloads. A genuine pip dry-run used the actual Python 3.13 target. A guarded network session allowed indexes/wheel metadata and explicitly blocked package archive downloads. [Resolver receipt](validation/2026-10-16-visual-runtime-resolution-receipt.json), [independent audit](validation/2026-10-16-visual-runtime-independent-review.json).

The declared `tb-nightly` dependency is retained as **2.21.0a20251023**, rather than silently replaced with another distribution. Its prerelease status is an upstream packaging constraint and a maintenance consideration. Optional native/JIT paths and training functions must remain disabled in the proposed CPU inference worker.

## Advisory finding and required mitigation

The 55-version OSV query completed on 16 October 2026. It returned **two advisory records, both aliases of CVE-2024-27763**, affecting BasicSR through 1.4.2. The reviewed [GitHub advisory](https://github.com/advisories/GHSA-86w8-vhw6-q9qq) describes command injection through a crafted `SLURM_NODELIST` environment variable in the training launcher. The approved source confirms `_init_dist_slurm` passes an interpolated value to `subprocess.getoutput`. [Saved full records](validation/2026-10-16-visual-GHSA-86w8-vhw6-q9qq.json), [alias record](validation/2026-10-16-visual-PYSEC-2026-1215.json), [raw query](validation/2026-10-16-visual-runtime-advisories.json).

This is a real finding; two records do not mean two distinct vulnerabilities. A point-in-time database query is not a general security certification. The raw upstream wheel remains affected, and the prepared lock explicitly records `security_clear=false`.

A [no-install prototype](validation/2026-10-16-visual-guard-prototype.json) compiles the reviewed `basicsr.utils.dist_util` source with `init_dist`, `_init_dist_pytorch` and `_init_dist_slurm` replaced by explicit rejection. All three entry points rejected execution with **zero shell calls**, including with SLURM environment variables present. Non-distributed `get_dist_info` and `master_only` behaviour remained functional. The source digest is `e6a6d7fced5146ff2e1f16cb0ce1c922171fe7e8b28c011178695ebed4f477b8`.

This prototype is not deployed mitigation. Before importing BasicSR in any new inference worker, an application-owned import guard must verify the exact installed version/source hash, apply these training restrictions, and fail on unexpected code or preloaded unguarded modules. A separate exact-source compatibility adaptation must replace the removed `torchvision.transforms.functional_tensor` import with the current `torchvision.transforms.functional` API. Installed upstream files and the approved wheels must remain unchanged. Tests must demonstrate both guards activate before engine import, preserve required inference helpers, reject source drift, and block shell/compiler execution. A guard failure must stop inference rather than fall back to an unguarded import.

## Retained failures and corrections

1. The first BasicSR build stopped while setuptools enumerated an unnamed distribution in the existing build host. The corrected temporary child filters only unnamed metadata entries during discovery. It still checks actual installed build requirements, and networking/child execution remain denied. No installed metadata was deleted or changed. Initial failure logs are retained alongside the successful build log.
2. The first metadata-only resolver ran under Python 3.10 with target flags. Pip evaluated a conditional dependency using the running interpreter and added `tomli`, which the actual Python 3.13 target does not require. The exact-set assertion failed. The final resolver now requires actual Python 3.13 and reuses existing pure-Python pip tools without installation. The historical host-marker report/receipt/log are retained; the final exact-set check passes with 55 packages.
3. Initial finalisation required zero advisory matches and correctly stopped after the BasicSR finding. It did not delete staging or write an installable approval. Finalisation was revised to require verified advisory records/alias interpretation and the guard prototype, while retaining the negative security/release flags. The initial security-stop log remains available.

Python 3.13 reported upstream invalid-escape SyntaxWarnings in old FilterPy documentation strings. Source compilation and exercised functions passed; package sources were not rewritten to hide those warnings.

## Preservation and cleanup

All 18 consolidated checks passed. Protected user state matches the established baseline. Latest F5 and preceding visual/RVC cancellation repair sources, tested F5 model/upstream sources, the built frontend, copied package metadata/RECORD files and all five established isolated runtime identities remain preserved. These are explicit scoped checks, not a fresh exhaustive inventory of every model in the project.

After verified wheels/metadata/notices/evidence were retained, cleanup removed **2,771,202 bytes** of owned staging. Cleanup checked the fixed resolved workspace path, ownership marker, all descendant paths and absence of links/junctions. No working runtime, source video, output media or model was removed. `runtime_profiles/visual-candidate` does not exist.

No production code changed in this iteration. The previous **907-test backend run** remains the last production regression result; it was not rerun or presented as a new test run. This preparation used actual builds, seven helper checks, independent dependency/artifact validation and the separate launcher-guard prototype.

## Separate proposed installation and acceptance scope

**Not yet authorised.** Create `runtime_profiles/visual-candidate` with the complete locked inventory below, reuse existing Python/model files, copy the 41 established package payloads, use the two retained built wheels, and download the 12 pinned wheels. Download bytes: **64,466,647** (about **61.48 MiB**). Estimated copied package payload: **864,580,519 bytes** (about **824.53 MiB**), plus **22,062,412 bytes** of Python bootstrap (about **21.04 MiB**) and the unpacked new wheels. This is an estimate, not a final installed size; temporary extraction also needs space. Measure final storage and remove installer staging after acceptance.

| Proposed new download | Version | Bytes | Why it is present |
| --- | --- | ---: | --- |
| addict | 2.4.0 | 3,832 | BasicSR configuration helper |
| facexlib | 0.3.0 | 59,624 | Face detection/parsing/restoration support |
| future | 1.0.0 | 491,326 | BasicSR compatibility helpers |
| gfpgan | 1.3.8 | 52,176 | Existing face-restoration engine |
| imageio | 2.38.1 | 328,389 | scikit-image image I/O dependency |
| lmdb | 3.0.0 | 188,317 | BasicSR's declared data-store dependency |
| opencv-python | 5.0.0.93 | 44,000,345 | Image/video operations required by the engine stack |
| scikit-image | 0.26.0 | 11,906,770 | BasicSR image-processing utilities |
| tb-nightly | 2.21.0a20251023 | 5,525,812 | Upstream declared logging dependency; retained explicitly |
| tifffile | 2026.10.15 | 276,988 | scikit-image TIFF I/O dependency |
| torchvision CPU | 0.29.1+cpu | 1,376,910 | Vision operations compatible with existing Torch metadata |
| yapf | 0.43.0 | 256,158 | BasicSR's declared configuration-formatting dependency |

Exact URLs, metadata and artifact hashes for all packages are in the prepared lock. No new engine, compiler, AI model, API service or framework is proposed.

Required implementation and acceptance after separate approval:

1. Install the new candidate separately, without changing existing defaults/runtimes. Preserve upstream wheel/source bytes. Add the exact-source training/compatibility guards described above and test rejection paths before engine imports.
2. Inspect all installed package requirements/origins and payload hashes; collect notices and carry the advisory finding/mitigation evidence. A missing wheel, unexpected requirement or need for an additional package stops this scope for discussion.
3. Reuse existing `GFPGANv1.4.pth`, parser and detector weights, recording their before/after hashes. Deny model recovery/network access during real inference. Start with real CPU face restoration on the existing short fixture and verify actual face-model forwards, output decoding, failure preservation and owned-worker cancellation/cleanup.
4. Connect an explicit CPU trial selection through saved/frozen settings, preflight/readiness/probe, worker execution, manifest evidence and portable inventory. Keep the current engine/default route available. A failed guard or unavailable candidate must produce a clear error.
5. Run appropriate focused and full backend regressions after production edits, native selector checks, then produce an acceptance report with measured disk use and remaining quality/performance/security/redistribution limits.

This scope excludes RVC and Wav2Lip/MuseTalk runtime migrations, new model downloads, GPU deployment and default promotion. Those remain separate engine work. Hindi/full-video quality, broad resource/parallel acceptance, fresh portable/clean-machine/manual checks and owner licensing decisions remain release gates.

## Complete proposed package inventory

The following table is generated from the prepared lock; source categories are part of the proposal, not evidence of installation.

| Package | Version | Proposed source |
| --- | --- | --- |
| absl-py | 2.5.1 | copy-existing |
| addict | 2.4.0 | published-wheel-pending-approval |
| basicsr | 1.4.2 | approved-built-wheel |
| certifi | 2026.7.22 | copy-existing |
| charset-normalizer | 3.5.2 | copy-existing |
| colorama | 0.4.6 | copy-existing |
| contourpy | 1.4.0 | copy-existing |
| cycler | 0.12.1 | copy-existing |
| facexlib | 0.3.0 | published-wheel-pending-approval |
| filelock | 4.1.1 | copy-existing |
| filterpy | 1.4.5 | approved-built-wheel |
| fonttools | 4.66.1 | copy-existing |
| fsspec | 2026.9.0 | copy-existing |
| future | 1.0.0 | published-wheel-pending-approval |
| gfpgan | 1.3.8 | published-wheel-pending-approval |
| grpcio | 1.84.0 | copy-existing |
| idna | 3.20 | copy-existing |
| imageio | 2.38.1 | published-wheel-pending-approval |
| jinja2 | 3.1.6 | copy-existing |
| kiwisolver | 1.5.1 | copy-existing |
| lazy-loader | 0.6 | copy-existing |
| llvmlite | 0.46.0 | copy-existing |
| lmdb | 3.0.0 | published-wheel-pending-approval |
| markdown | 3.11 | copy-existing |
| markupsafe | 3.0.4 | copy-existing |
| matplotlib | 3.11.2 | copy-existing |
| mpmath | 1.3.0 | copy-existing |
| networkx | 3.7 | copy-existing |
| numba | 0.63.1 | copy-existing |
| numpy | 2.3.5 | copy-existing |
| opencv-python | 5.0.0.93 | published-wheel-pending-approval |
| packaging | 26.3 | copy-existing |
| pillow | 12.3.0 | copy-existing |
| platformdirs | 4.13.0 | copy-existing |
| protobuf | 7.36.2 | copy-existing |
| psutil | 7.2.2 | copy-existing |
| pyparsing | 3.3.3 | copy-existing |
| python-dateutil | 2.9.0.post0 | copy-existing |
| pyyaml | 6.0.3 | copy-existing |
| requests | 2.34.2 | copy-existing |
| scikit-image | 0.26.0 | published-wheel-pending-approval |
| scipy | 1.16.3 | copy-existing |
| setuptools | 84.0.0 | copy-existing |
| six | 1.17.0 | copy-existing |
| sympy | 1.14.0 | copy-existing |
| tb-nightly | 2.21.0a20251023 | published-wheel-pending-approval |
| tensorboard-data-server | 0.7.2 | copy-existing |
| tifffile | 2026.10.15 | published-wheel-pending-approval |
| torch | 2.14.1+cpu | copy-existing |
| torchvision | 0.29.1+cpu | published-wheel-pending-approval |
| tqdm | 4.70.1 | copy-existing |
| typing-extensions | 4.16.0 | copy-existing |
| urllib3 | 2.8.0 | copy-existing |
| werkzeug | 3.1.9 | copy-existing |
| yapf | 0.43.0 | published-wheel-pending-approval |
