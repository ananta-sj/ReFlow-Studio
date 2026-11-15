# Approved Demucs helper builds and prepared CPU runtime lock

Date: 16 October 2026. Decision: the approved helper-build and dependency-lock preparation is complete. No separation runtime is installed; existing application defaults remain unchanged.

## Approval and scope

The user explicitly approved helper builds and dependency-lock preparation for Demucs 4.0.1, dora-search 0.1.12, julius 0.2.7 and antlr4-python3-runtime 4.9.3. This follows [the real separation boundary audit](SEPARATION_RUNTIME_AUDIT_2026-10-16.md), which found that background preservation works with the original portable interpreter but fails in the clean desktop interpreter.

This iteration downloaded only those four package source archives, **1,476,709 bytes total**. It inspected their packaging code, built wheels with existing tools, verified their contents and hashes, exercised bounded Python 3.13 checks, prepared a genuine resolver-checked dependency lock and removed temporary staging. The six other proposed package archives were not downloaded. Existing models were reused for preservation checks only; no new model or application dependency was installed.

## Build provenance and verification

All four source sizes and SHA-256 values matched the hashes recorded before approval. Extraction rejected links, unsafe paths, duplicate destinations, special files and excessive expansion. Copies of setup/configuration/notice files are retained under [the helper evidence directory](validation/2026-10-16-separation-helpers/).

The unchanged original build tools were Python **3.10.11**, setuptools **80.10.2** and wheel **0.47.0**. [Recorded tool versions and origins](validation/2026-10-16-separation-build-tools.json). These packages build pure-Python wheels; the results were separately checked using existing Python **3.13.16**. No compiler, build isolation environment, package upgrade or automatic build dependency fetch was used.

The build wrapper initialized the existing packaging tools, then blocked Python socket operations and child-process launches before executing package setup code. It used the existing no-index configuration and did not install the wheels. These are process-level guards, not a claim of a complete operating-system sandbox. Original third-party package sources were not edited.

| Built package | Wheel bytes | Verified Python source files |
| --- | ---: | ---: |
| antlr4-python3-runtime 4.9.3 | 144,613 | 56 |
| demucs 4.0.1 | 78,551 | 24 |
| dora-search 0.1.12 | 75,319 | 38 |
| julius 0.2.7 | 22,018 | 8 |
| Total | 320,501 | 126 |

Each wheel's package name/version, archive paths and hashed RECORD entries were checked. Every included Python source file matched its original extracted source byte-for-byte. Wheel hashes are retained in [the build receipt](validation/2026-10-16-separation-helpers/build-receipt.json), and the wheels themselves remain in their per-package evidence folders for the next approved build.

## Actual checks and compatibility limits

The final helper smoke passes **14 assertions**, including all 126 source files compiling in Python 3.13.16, exact wheel hashes/origins, actual ANTLR input/token handling, the Demucs package version and real Julius resampling under existing Torch 2.14.1+cpu. The test used the wheel files directly on its process import path; they were not installed. [Smoke receipt](validation/2026-10-16-separation-helpers-smoke.json) and [complete log](validation/2026-10-16-separation-helpers-smoke-complete.log).

The actual Demucs audio writer uses `torchaudio.save`. Current TorchAudio requires TorchCodec for that path, even though its declared hard requirements do not supply it. The initial 31-package proposal/resolver result omitted this operational dependency. The final proposal explicitly adds the already-existing **TorchCodec 0.17.0+cpu**, producing a **32-package** lock. Initial proposal and resolver receipts remain retained with `initial`/`31-packages` names.

An actual write/decode roundtrip succeeded using existing TorchAudio/TorchCodec, the existing shared FFmpeg DLL directory and SoundFile: stereo audio with 4,410 frames at 44,100 Hz. The future worker must initialize that DLL directory. TorchAudio warns that `encoding` and `bits_per_sample` are not fully supported by its TorchCodec writer. The roundtrip proves playable dimensions/rate; it does not establish exact requested PCM encoding. The runtime acceptance must inspect the emitted encoding and decide whether a narrowly scoped writer adapter is necessary.

Full Demucs separation imports, Dora imports with all future dependencies, loading the checkpoint in a modern separation candidate, actual separation quality, GPU operation, pipeline routing and portable relocation have **not** been accepted. The helper smoke is not a replacement for those tests. No full backend rerun was necessary because production source files did not change in this preparation iteration; the preceding 878-test backend result remains historical evidence, with its current production hashes rechecked.

## Prepared lock

The [final prepared lock](validation/2026-10-16-separation-runtime-lock-review.json) contains:

- **32 exact packages**, with **36 active declared dependency links** verified for CPython 3.13.16 on Windows x64.
- **22 distributions** copied in a future build from the existing validated modern CPU runtime, without modifying that source runtime.
- **Four already-built helper wheels** described above.
- **Six published wheels**, requiring **365,848 bytes** (about 0.35 MiB) of additional transfers if a runtime build is approved.
- Existing embedded Python and the existing `models/uvr/955717e8-8726e21a.th` checkpoint; no model transfer.

| Pending published wheel | Version | Transfer bytes | Purpose |
| --- | --- | ---: | --- |
| lameenc | 1.8.1 | 152,020 | Demucs audio encoding helper; native CPython 3.13 Windows wheel |
| omegaconf | 2.3.0 | 79,500 | Configuration objects used by Demucs/Dora |
| openunmix | 1.3.0 | 40,047 | Audio separation/filtering support imported by Demucs |
| retrying | 1.4.2 | 10,859 | Dora support dependency |
| submitit | 1.5.4 | 76,043 | Dora execution/checkpoint support dependency |
| treetable | 0.2.6 | 7,379 | Dora configuration/reporting support dependency |

The exact copied-package graph, bootstrap hashes, six official artifact URLs/hashes and four local wheel hashes are in the lock. The projected copied package payload is **590,012,495 bytes**, plus **22,062,412 bytes** of bootstrap: about **584 MiB** before unpacked new wheels, RECORD/entrypoint overhead and any runtime-generated cache. The exact installed size will be measured after a separately approved build. Shared FFmpeg and the large existing Demucs checkpoint are outside this new profile estimate and remain existing application assets.

Genuine pip `--dry-run` resolution used the four local wheels, exact pins, target Windows/Python tags, and metadata-only network access. Remote archive and source-build requests were blocked. Its resolved package set exactly matches the plan. The independent review also matched all 32 resolver artifact hashes to the reviewed source lock/published artifacts/built wheels, checked the copied packages' METADATA and RECORD hashes, and validated active requirements using resolver metadata. [Resolver receipt](validation/2026-10-16-separation-runtime-resolution-receipt.json), [full report](validation/2026-10-16-separation-runtime-resolution-report.json), [independent review](validation/2026-10-16-separation-runtime-independent-review.json).

The public OSV exact-version query completed for all **32 packages**, with **zero matches** at the recorded time. This is a point-in-time package advisory lookup, not security certification of the model, native libraries, FFmpeg or unreported defects. [Advisory receipt](validation/2026-10-16-separation-runtime-advisories.json).

## Notices

Three helper wheels include license files. The approved ANTLR source archive and resulting wheel omit the LICENSE.txt referred to by source headers. A separately retained [official ANTLR 4.9.3 release notice](https://raw.githubusercontent.com/antlr/antlr4/4.9.3/LICENSE.txt) supplements that gap; its URL, 2,699-byte size and SHA-256 are recorded in [the notice receipt](validation/2026-10-16-separation-antlr-notice.json). The wheel was not silently repackaged. The full upstream notice includes additional project material; this receipt preserves provenance rather than making a legal coverage decision. Owner licensing, model conditions and final distribution preparation remain open.

## Failed attempts retained

The first helper build blocked a Windows version query while importing the existing packaging tools. The corrected wrapper initializes those tools before applying the package-source execution guard. The first smoke encountered the analogous version query in the unchanged Torch loader; the corrected test initializes existing Torch before restricting helper execution. These failures and initial JSON receipts remain retained, alongside successful final results.

The first independent review read pip's UTF-8 report with the Windows default codec and failed. Explicit UTF-8 fixed it. A later notice assertion expected an individual attribution, while the actual official text attributes The ANTLR Project; the assertion was corrected to match the inspected source. Neither audit failure changed a package or application runtime. Initial/corrected/complete logs remain retained so failed runs are not represented as passing evidence.

## Cleanup and preservation

The owned staging directory was checked against its resolved absolute location, ownership marker and a complete no-links/no-junctions tree walk before removal. Cleanup removed **4,881,561 bytes** of source archives, extracted sources and temporary build output. The four verified wheels, build logs, reviewed packaging files, supplemental notice, resolver results and receipts remain as durable evidence. [Final acceptance receipt](validation/2026-10-16-separation-helpers-acceptance.json).

Protected user-state hashes, the preceding tested production sources, original Demucs weight hash, and the XTTS/NLLB/recognition/M2M100 runtime identities remain unchanged. No `runtime_profiles/separation-candidate` exists. There was no runtime installation, model download, default promotion or public release.

## Next step requiring separate approval

Build `runtime_profiles/separation-candidate` from this 32-package lock: copy the 22 existing distributions and Python bootstrap, extract the four approved local wheels, and download/hash-check the six reviewed wheels (365,848 bytes). Preserve all current environments/defaults and reuse the existing checkpoint and FFmpeg assets. This is the next installation proposal, not authorization inferred from the helper approval.

After installation, verify the full installed closure/payload/native origins, actual short stems and encoding, repeated-run behavior and owned-process cancellation. Then implement explicit per-feature selection and validated routing through settings, frozen jobs, preflight, readiness, evidence and portable inventory; test real pipeline background preservation and regressions. A failure must retain evidence and must not silently fall back into the legacy runtime or fetch additional dependencies. Newly needed packages, compilers or models require another documented approval. Default promotion and release remain separate decisions.

## Subsequent approval and execution

The user subsequently approved the separate runtime and tests. The candidate is now built and technically integrated for explicit CPU trial use. The lock's approval flags remain the historical planning snapshot rather than being rewritten after hashing. [Actual implementation, measurements, failures, short-video result and remaining release gates](SEPARATION_CANDIDATE_ACCEPTANCE_2026-10-16.md).
