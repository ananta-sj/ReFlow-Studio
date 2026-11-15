# Background-separation runtime audit and bounded next step

Date: 16 October 2026. Status: audit and narrow fixes accepted; clean separation runtime and full application release remain unaccepted.

## Findings

The approved modern desktop and translation runtimes do not yet provide the Demucs background-preservation feature. Separation currently chooses the general interpreter through `worker_python()`. Under normal source execution that is the desktop interpreter. Its preflight instead imports `demucs.separate` in the parent process. There is no independent, selected and validated modern separation runtime. Changing a global worker override is not a complete architecture repair because other stages also use it.

This was reproduced using actual local audio and the existing checksum-verified `htdemucs` weights. Both real calls started in the modern desktop parent; only the child interpreter changed:

| Selected child | Actual result |
| --- | --- |
| Desktop candidate | Failed at `import torch`; no Torch in that runtime |
| Original Windows portable | Completed; playable vocals and background, both 1,000 ms and 176,444 bytes |
| Translation candidate, dependency probe only | Torch loaded; `demucs` absent |

The legacy actual separation took 17.296 seconds for a one-second excerpt, including process/model startup. This is not a throughput calibration. The desktop failure took 3.477 seconds. [Actual execution and import evidence](validation/2026-10-16-separation-boundary.json).

The model SHA-256 remains `8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4`. No checkpoint was downloaded. Duration and decodability establish mechanical stem production, not audible separation quality or removal of all source dialogue. No full dubbed video is accepted by this audit.

## Repairs made

`core/audio_separator.py` now preserves `RenderCancelled` rather than wrapping it as an ordinary processing failure. This covers cancellation during the owned worker and during final output validation; ordinary failed workers, missing stems and undecodable audio still fail visibly.

Fixed decorative symbols in that module's status messages could raise `UnicodeEncodeError` in a Windows cp1252 output stream before separation started. Those fixed messages now use plain text. A regression test exercises a real cp1252 text wrapper with an ASCII filename. This does not claim every arbitrary Unicode path or third-party log can pass through every console encoding.

`core/runtime_probe_contract.py` and `core/runtime_probe_worker.py` now support a bounded Demucs dependency probe on CPU or the first NVIDIA device. It imports the actual separation/model/audio modules and checks device arithmetic without constructing a model. This diagnostic route was used in the audit; it does not install a runtime, migrate preflight, or declare the feature ready. Only CPU was exercised here. The preflight mismatch described above remains pending a proper runtime-selection design.

## Validation

- **878 backend tests passed**, 118.571 seconds, in the existing working interpreter. The two historical state-mutating/download scripts remain excluded from unittest discovery; their exclusion is not acceptance.
- **24 focused tests passed**, 1.242 seconds, in the clean desktop interpreter. These overlap the full suite and are not additive counts.
- An actual registered Demucs child was observed running, then cancelled. `RenderCancelled` survived unchanged, owned process registration cleared, and the workspace was removed. Return after cancellation: **0.117 seconds**. This verifies process cancellation; it does not verify a neural decoder/inference boundary or promise a universal latency. [Cancellation receipt](validation/2026-10-16-separation-cancellation.json).
- Both actual boundary attempts, including the failed desktop worker, left no registered owned processes or owned workspaces.
- Protected state hashes and the XTTS, NLLB, recognition and M2M100 runtime identities match their previous accepted baselines after the full suite. No defaults changed. [Final current-source receipt](validation/2026-10-16-separation-iteration-acceptance.json).

Detailed logs: [backend](validation/2026-10-16-separation-full-backend.log), [focused](validation/2026-10-16-separation-focused-complete.log), [real separation](validation/2026-10-16-separation-boundary.log), [cancellation](validation/2026-10-16-separation-cancellation.log), [finalization](validation/2026-10-16-separation-finalization.log).

## Retained failed attempts

The first focused invocation failed because embedded Python deliberately ignores the normal workspace import path. The corrected invocation explicitly inserted the project paths, then exposed the real cp1252 logging failure. Both logs remain retained as `2026-10-16-separation-focused.log` and `2026-10-16-separation-focused-corrected.log`; neither is passing evidence. The production log correction and final test results are recorded separately.

The initial dependency inventory encountered an installed legacy `pip-25.3.dist-info` entry without usable Name metadata. The corrected inventory reports this malformed path explicitly instead of silently treating it as a valid package or modifying it. It found no malformed entries in the modern source profile. The initial and corrected feasibility logs remain retained. The metadata traversal reports no active version conflicts in its selected base closure; that is not a resolved artifact lock, an extras audit or a compatibility guarantee.

## No-install dependency assessment

Installed metadata indicates ten Demucs support packages absent from the existing modern CPU package set: antlr4-python3-runtime, demucs, dora-search, julius, lameenc, omegaconf, openunmix, retrying, submitit and treetable. [Local dependency inventory](validation/2026-10-16-separation-dependency-feasibility.json).

Official PyPI metadata for the existing exact versions was then read without downloading archives. Six have compatible published wheels for this target, including native `lameenc` for CPython 3.13 Windows x64. Four require source-built wheels at the inspected versions. This inspection uses existing versions as candidates; it is not a recommendation that those versions are current secure release pins. No advisory scan, actual wheel METADATA resolver or modern Demucs inference acceptance has been completed. [Artifact metadata and exact upstream URLs/hashes](validation/2026-10-16-separation-artifact-review.json).

The four source artifacts total **1,476,709 bytes**, about **1.41 MiB**:

| Package | Version | Source bytes | Purpose |
| --- | --- | --- | --- |
| antlr4-python3-runtime | 4.9.3 | 117,034 | Parser used by OmegaConf configuration support |
| demucs | 4.0.1 | 1,212,924 | Existing vocal/background-separation engine |
| dora-search | 0.1.12 | 87,111 | Demucs experiment/checkpoint support dependency |
| julius | 0.2.7 | 59,640 | Audio resampling/filtering support |

Pinned source SHA-256 values, in the same order:

```
f224469b4168294902bb1efa80a8bf7855f24c99aef99cbefc1bcd3cce77881b
e45a5a788bae79767c37bbf6e69aae03862ddcca05550fb79b926346a177d713
2956fd2c4c7e4b9a4830e83f0d4cf961be45cfba1a2f0570281e91d15ac516fb
3c0f5f5306d7d6016fcc95196b274cae6f07e2c9596eed314e4e7641554fbb08
```

## Next approval boundary: source helpers and lock preparation only

The next proposed step is to download those four hash-pinned source archives from their recorded official PyPI artifact URLs, inspect archive/build contents, and build wheels in an owned temporary directory using existing packaging tools. Building package setup code executes third-party code, so this requires explicit approval under the user's instruction to approve package/tool additions. If an additional build dependency or compiler is needed, stop and document it rather than fetching it automatically.

This approval would permit the source-wheel preparation and metadata/advisory work needed for an exact dependency lock. It would **not** permit installing a separation runtime, changing defaults, adding a global worker override, downloading models, replacing existing packages, or promoting anything to production. Keep original sources, settings and models intact; retain build provenance and license/notice evidence; remove owned temporary staging when appropriate. Any later runtime installation needs a separate concrete plan with exact packages, transfer/storage estimates, validation criteria and approval.

After that preparation, the runtime design must cover per-feature selection, exact interpreter/package/model validation, correct preflight in that worker, run identity evidence, cancellation/cleanup, portable inclusion, actual modern stem generation and quality checks with speech plus background. Compatibility with current Torch/audio libraries must be measured, not assumed. Broader video, recognition quality, resource calibration, clean-machine and licensing gates remain open.

## Source and evidence scope

Production changes are limited to `core/audio_separator.py`, `core/runtime_probe_contract.py` and `core/runtime_probe_worker.py`. Added validation helpers are `dev/test_audio_separator.py`, `dev/audit_separation_boundary.py`, `dev/evaluate_separation_cancellation.py`, `dev/inspect_separation_dependencies.py`, `dev/prepare_separation_artifact_review.py` and `dev/finalize_separation_audit.py`; `dev/test_runtime_probe.py` gained a Demucs import-contract case. The final receipt binds their hashes and current production sources. Earlier translation acceptance remains historical evidence; its probe-source hashes naturally precede this new diagnostic route. Its bound inference recipe still validates and its runtime identity is unchanged.
