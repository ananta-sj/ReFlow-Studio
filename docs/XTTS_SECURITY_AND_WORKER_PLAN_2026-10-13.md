# XTTS security replacement and session bridge — 13 October 2026

## Outcome and scope

The existing validated offline candidate passed a real test through Reflow's existing `FeatureSession` interface. A separate replacement lock is ready for review. **No replacement package archives were downloaded and no installed runtime or production default changed in this pass.** The user's earlier request requires explanation and approval before adding packages/tools; replacement installation is the next approval step, not inferred from metadata preparation.

The replacement plan targets Windows portable and ordinary CPython 3.13.16. It reuses the verified interpreter bootstrap and existing XTTS model assets in a new owned `runtime_profiles/xtts-security-candidate` directory. The current working shared runtime and validated `xtts-candidate` remain comparison baselines. There is no new TTS/translation model, agent service, compiler, package manager or framework proposed. The library upgrade introduces the transitive support packages explicitly listed below.

## Actual persistent worker verification

This used the existing parent `FeatureSession` class with a development-only XTTS worker and the already installed CPU candidate. It did not substitute generated waveform fixtures or edit supplied audio. The candidate worker loaded the existing XTTS checkpoint once, answered two actual speech requests, rejected an unsupported `source` language, and cancelled a longer utterance after a real token boundary.

| Session check | Observed result |
| --- | --- |
| Two speech requests | Passed; nonempty generated WAV files |
| Worker lifetime | Same worker PID 26860 for both successful calls |
| Model lifetime | Same model identity, one load |
| Invalid speech language | Rejected; no output created |
| Stop to worker exit | 1.437 seconds |
| Previous completed output | Hash preserved after cancellation |
| Incomplete publication | No staged output left in the parent job |
| Worker/process ownership | Session thread finished; parent workspace removed |
| Total observed test time | 240.172 seconds |

The offline worker blocks socket connections, DNS and binds, uses explicit local models, and places TTS/Torch/Hugging Face/Matplotlib/Numba caches inside the caller's job folder. Its internal render workspace is also nested inside that folder, so an outer job owns cleanup even if the worker is stopped. Requests use the existing atomic JSON-file session protocol and bounded error diagnostics. The worker validates that output WAV destinations belong to the caller's job workspace.

This is **real session-interface acceptance**, not a production provider switch, native UI acceptance, full video render, resource calibration or approval to ship the old advisory-affected candidate. The development worker remains outside the production provider registry. All original XTTS assets, five saved app-state files and previously tested production sources remain hash-identical.

## Why these versions are proposed

| Library | Previous candidate | Proposed candidate | Reason |
| --- | --- | --- | --- |
| PyTorch | 2.9.1+cpu | 2.14.1+cpu | Published Windows CPU build beyond the prior advisory ranges |
| TorchAudio | 2.9.1+cpu | 2.11.0+cpu | Stable ABI supports Torch 2.11 and later; retains existing audio APIs |
| TorchCodec | 0.8.1 | 0.17.0+cpu | Current compatible decoder family for Torch 2.11+ and Python 3.13 |
| Transformers | 4.57.1 | 5.19.0 | Beyond the prior reported affected ranges; major generation API change requires actual XTTS testing |
| Coqui TTS | 0.27.5 | 0.27.5 | Same currently published engine and existing checkpoint; no engine replacement |

Compatibility sources: [TorchAudio's official installation matrix](https://docs.pytorch.org/audio/stable/installation.html), [TorchCodec's compatibility matrix](https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions), [Coqui installation requirements](https://coqui-tts.readthedocs.io/en/latest/installation.html). These sources and compatible Windows wheel tags support planning; they do not prove Coqui's customized GPT generation wrapper works unchanged with Transformers 5.19. That remains an explicit evaluation risk. No declared requirements were stripped or bypassed to manufacture a clean dependency result.

The final **99-package** CPU lock has **143 satisfied active target dependency links**. Required extras were propagated to a fixed point; Python/Windows markers and wheel tags were checked independently of the Python 3.10 resolver host. Host-only `async-timeout`, `exceptiongroup` and `tomli` were excluded. An exact-version public OSV lookup returned **zero matches** for this reviewed lock at the recorded scan time. That is a point-in-time advisory result, not certification of native DLLs, model files, runtime behavior or future vulnerabilities.

## Download and storage impact

The full proposed wheel set totals **304,189,555 bytes (290.1 MiB)**, including the already retained 13,857-byte local Docopt wheel. Reusing that wheel leaves 304,175,698 bytes of remote package archives. No new Python or model download is proposed. Installed disk size and peak staging overlap are unmeasured; they will be recorded after an approved separate installation. The previous 85-package candidate occupied about 960 MB after installation, so the replacement should be planned as another substantial runtime rather than described as a small patch.

All URLs, filenames and SHA256 values are recorded in the JSON and hash-bound text locks. Torch/TorchAudio/TorchCodec are explicitly pinned to CPU local versions. The review text lock contains a workspace-specific local Docopt URL; installation must deliberately rebind that owned wheel without changing its hash. Temporary wheel staging would be removed after verification while retaining source/notice/evidence records and both comparison runtimes.

## Changed library versions

| Package | Before | After | Requesting dependency |
| --- | --- | --- | --- |
| `huggingface-hub` | 0.36.2 | 2.2.0 | tokenizers, transformers |
| `tokenizers` | 0.22.2 | 0.23.3 | transformers |
| `torch` | 2.9.1+cpu | 2.14.1+cpu | Explicit runtime root |
| `torchaudio` | 2.9.1+cpu | 2.11.0+cpu | Explicit runtime root |
| `torchcodec` | 0.8.1 | 0.17.0+cpu | Explicit runtime root |
| `transformers` | 4.57.1 | 5.19.0 | coqui-tts |

## New transitive support packages

These are required by the revised libraries, not separate product features. HTTP/client/certificate packages support the Hugging Face client; terminal formatting/argument helpers support its command interface. They do not imply API use, a connected account or a model download. Offline evaluation will keep network operations blocked.

| Package | Version | Archive bytes | Required by |
| --- | --- | ---: | --- |
| `annotated-doc` | 0.0.5 | 5,302 | typer |
| `anyio` | 4.15.1 | 132,079 | httpx2 |
| `click` | 8.5.0 | 125,251 | huggingface-hub |
| `h11` | 0.16.0 | 37,515 | httpcore2 |
| `hf-xet` | 1.7.0 | 3,822,644 | huggingface-hub |
| `httpcore2` | 2.13.1 | 83,423 | httpx2 |
| `httpx2` | 2.13.1 | 95,597 | huggingface-hub |
| `markdown-it-py` | 4.2.0 | 91,687 | rich |
| `mdurl` | 0.1.2 | 9,979 | markdown-it-py |
| `pygments` | 2.21.0 | 1,250,147 | rich |
| `rich` | 15.0.0 | 310,654 | typer |
| `shellingham` | 1.5.4 | 9,755 | typer |
| `truststore` | 0.10.5 | 19,017 | httpcore2, httpx2 |
| `typer` | 0.27.3 | 123,312 | transformers |

## Retained planning corrections

The initial CPU-index lookup expected TorchCodec's plain version 0.17.0 and did not match the published local version 0.17.0+cpu. The first dry run selected that CPU version, but the review checker deliberately rejected the non-exact root match and the size helper's corresponding PyPI URL returned 404. Those reports remain retained. The root was then made explicitly `0.17.0+cpu`; all three CPU index hashes were captured, a separately labelled metadata-only resolution completed, and closure, size and advisory checks passed. No archive was transferred during these attempts.

The root plan now contains only current name/version/purpose entries rather than stale wheel metadata copied from the older library versions. Label/prefix parameters were added to existing helpers so the old candidate's lock, receipts and checks remain intact. Source builds, runtime installation and archive GETs remained disabled in every resolver attempt.

## Changes and evidence

Added `dev/inspect_xtts_security_replacements.py` and `dev/prepare_xtts_security_resolution.py` for metadata-only candidate selection; added `dev/xtts_candidate_worker.py` and `dev/verify_xtts_candidate_session.py` for actual isolated session testing; added this documentation helper. Existing resolver/closure/budget/advisory helpers gained labelled-plan/output support. No production module was changed, and no new audit framework was installed. Tests used the existing interpreted libraries and existing FFmpeg.

Evidence: [replacement review](validation/2026-10-13-xtts-security-upgrade-review.json), [exact dependency lock](validation/2026-10-13-xtts-security-cpu-lock-review.json), [hash-bound text lock](validation/2026-10-13-xtts-security-cpu-review.lock.txt), [metadata-only receipt](validation/2026-10-13-metadata-only-security-cpu-revision-receipt.json), [download budget](validation/2026-10-13-xtts-security-cpu-download-budget.json), [advisory scan](validation/2026-10-13-xtts-security-cpu-advisories.json), [session acceptance](validation/2026-10-13-xtts-candidate-session.json), [worker log](validation/2026-10-13-xtts-candidate-session-worker.log), [preservation](validation/2026-10-13-xtts-candidate-preservation-after.json), [iteration integrity](validation/2026-10-13-xtts-security-bridge-integrity.json).

## Approval boundary and remaining work

Next proposed action: create the separate replacement runtime, download/install only this reviewed 99-package hash-bound closure, reuse the verified Python bootstrap and existing weights, run the actual package/audio/XTTS/session/recognition checks, measure disk use and remove owned installer staging. Preserve both current runtimes, original state and model files; do not change app defaults or publish a release. Any extra package, compiler, source build, new model or alternative engine discovered necessary must be explained and reviewed before addition.

Approval is requested because the user explicitly asked to know what is being added and why before package/tool changes. The new support packages and major Transformer API change were not part of the earlier exact 85-package installation approval. Until approval arrives, the replacement remains metadata-only; the working app and validated candidate remain unchanged.

Successful evaluation would still leave the production provider/readiness/cache identity wiring, all other runtime families, licensing/notices, full workflow and clean-machine/native Windows release gates. The app is not release-ready. See the [runtime repair map](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release status](RELEASE_READINESS_2026-10-04.md).
