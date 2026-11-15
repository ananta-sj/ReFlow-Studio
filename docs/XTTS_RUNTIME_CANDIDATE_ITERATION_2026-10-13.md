# Isolated XTTS runtime candidate — 13 October 2026

## Result and boundaries

The user said “so go ahead” after reviewing the helper/lock results and the proposed next step of separately approved runtime creation and testing. This pass built and tested that isolated candidate. It did not switch the application default, change the model registry or install system tools. The previous approval limited to the helper build remains documented as an earlier phase; this later authorization covers the reviewed interpreter and 85-package candidate.

**Candidate technical acceptance: passed. Release eligibility: false.** The original shared runtime and optional profiles remain the working setup. Windows portable is the first release target; this pass does not validate Linux/macOS.

The new folder is `runtime_profiles/xtts-candidate`. It uses ordinary Windows x64 CPython 3.13.16, Coqui TTS 0.27.5, CPU Torch 2.9.1, Torchaudio 2.9.1, TorchCodec 0.8.1 and the exact reviewed 85-package lock. All required wheels and the Python archive were verified against their recorded SHA256 values. The locally built Docopt helper was reused. No compiler, Conda, new model, GPU driver or system Python/PATH change was introduced.

## Measured results

| Check | Observed result |
| --- | --- |
| Exact installed package set and versions | 85 packages, matching the reviewed lock |
| Duplicate distribution records | None in the candidate |
| Dependency constraints | All active target requirements satisfied |
| Import paths | Tested engine imports originate inside the candidate |
| Runtime checks | 14 checks passed, including CPU convolution and real audio decoding |
| Docopt on Python 3.13 | Real parser assertion passed |
| Existing XTTS checkpoint | Loaded without model downloads |
| Successful speech | 5.42 seconds, 24000 Hz, non-silent |
| Model loading | 29.861 seconds in the final trial |
| Speech generation | 42.893 seconds for this one utterance |
| Real token-boundary cancellation | 0.168 seconds |
| Model lifetime | Same loaded model reused for speech and cancellation |
| Output publication | Previous completed speech preserved after cancellation |
| Temporary generation state | Staging output and job workspace removed |
| Original state and models | Five app-state hashes and eight XTTS asset hashes unchanged |
| Production source files | Match the previously tested source hashes |
| Installed candidate size | 960,336,065 bytes, about 915.8 MiB at installation completion |
| Temporary installation cleanup | 291,023,750 bytes removed |
| Ollama trial | Earlier temporary trial remains absent |

The measured size excludes existing model weights and documentation/notice receipts. Imports can generate additional candidate cache files, so this is the installation-completion measurement rather than a promise of a fixed final footprint. The generation time is a single CPU observation, not a calibrated ETA or a general speed comparison. The candidate is about 7.9 times slower than real time for this utterance; GPU performance was not tested under this CPU evaluation approval.

## Speech-content cross-check

The unchanged existing Whisper Turbo assets and GPU worker recognized the newly generated audio, rather than a supplied transcript. The expected text was “Good morning. This is a test of the isolated Reflow speech runtime.” and the observed recognition was “Good morning. This is a test of the isolated reflow speech runtime.”. Word error rate was 0.0; the check passed. The recognition worker and its job workspace were released.

ASR similarity helps detect gross gibberish or missing words. It does not certify naturalness, emotion, speaker likeness, source-video timing or all-language pronunciation. This new candidate take has not received a human listening acceptance, and this pass did not render a full dubbed video or change the previously accepted Hindi pipeline.

## Offline guard and retained verification corrections

The first runtime check and first speech trial both completed their functional checks but marked the aggregate result false because the harness demanded zero socket attempts. The captured event was a blocked socket bind; subsequent stack tracing identified urllib3's `_has_ipv6("::1")` import-time capability probe. It was not a model download or an outbound connection.

The verification was corrected to record event/address/stack details, keep every network operation blocked, and separately require no outbound or DNS attempts. Both actual runtime and real speech/cancellation trials were rerun with the corrected checks. Their new labelled receipts passed. The original failed aggregate receipts and logs were retained without editing. This was a harness correction, not an exception allowing network access.

The speech worker used offline Hugging Face flags, explicit existing model paths and job-owned TTS/Hugging Face/Torch/Matplotlib/Numba cache paths. Source/reference media came from the existing `Sample/2.mp4`. New test audio is retained under validation only; no original media was overwritten. All root user-state hashes and original XTTS assets were checked again.

The Python 3.13 startup log includes “Failed to find real location” for its executable. The interpreter still reports the exact expected version and isolated paths, and native package/audio/model execution passes. The warning is retained as a clean-machine/launcher investigation item, not declared solved. Pydub and Docopt also emit invalid-escape SyntaxWarnings under Python 3.13; their actual tested audio/parser operations pass. No installed third-party source was patched merely to hide those warnings.

## Preparation failures and recovery

The initial notice collector mistakenly wrote a wheel license-directory entry as an empty file. Preparation stopped before pip installed packages. Resume handling first encountered the existing empty package destination, then a nested license-directory collision. The helper was corrected to skip directory entries, permit only the explicitly marked incomplete owned candidate with an empty package destination, preserve retry receipts, and remove only the empty notice-file artifacts created by the collector. The working runtime was never an installation target.

All subsequent package installation was offline from the verified local wheelhouse, with hashes required, dependencies already locked and source builds disabled. The existing pip was used in cross-target mode only to unpack the locked wheels. It did not install or upgrade itself. Cross-target console launchers referring to the old build interpreter were removed from the newly owned candidate; this worker uses package imports, not those CLI launchers. A future tool needing a console entry point must generate it against the correct interpreter and test it.

Archive path/link/size checks were retained. Redundant per-entry filesystem resolution was later replaced with lexical member validation for future builds in a fresh owned extraction directory; the completed installation had already used the original stricter checks. No existing candidate can be replaced automatically. Interrupted package installation cannot be resumed over a nonempty destination by this helper.

## Security and redistribution findings

The public OSV scan returned **16 advisory records** for Torch 2.9.1 and Transformers 4.57.1. Some records are aliases of the same CVE, so this does not mean 16 independent vulnerabilities. The following table groups by CVE. CPU local-version suffixes were removed only for advisory matching, not from the actual package lock.

| CVE | Package | Advisory / affected surface | Published range endpoint |
| --- | --- | --- | --- |
| CVE-2025-14929 | transformers | [PYSEC-2025-217](https://osv.dev/vulnerability/PYSEC-2025-217): See retained advisory details | last_affected: 5.0.0-rc0 |
| CVE-2025-14930 | transformers | [PYSEC-2025-218](https://osv.dev/vulnerability/PYSEC-2025-218): See retained advisory details | last_affected: 4.57.1 |
| CVE-2025-3000 | torch | [GHSA-rrmf-rvhw-rf47](https://osv.dev/vulnerability/GHSA-rrmf-rvhw-rf47): PyTorch is vulnerable to memory corruption through its torch.jit.script function | fixed: 2.13.0 |
| CVE-2025-3001 | torch | [GHSA-qfhq-4f3w-5fph](https://osv.dev/vulnerability/GHSA-qfhq-4f3w-5fph): PyTorch is vulnerable to memory corruption through its torch.lstm_cell function | fixed: 2.10.0 |
| CVE-2026-1839 | transformers | [GHSA-69w3-r845-3855](https://osv.dev/vulnerability/GHSA-69w3-r845-3855): HuggingFace Transformers allows for arbitrary code execution in the `Trainer` class | fixed: 5.0.0rc3 |
| CVE-2026-24747 | torch | [PYSEC-2026-2286](https://osv.dev/vulnerability/PYSEC-2026-2286): See retained advisory details | fixed: 2.10.0 |
| CVE-2026-4372 | transformers | [GHSA-29pf-2h5f-8g72](https://osv.dev/vulnerability/GHSA-29pf-2h5f-8g72): HuggingFace transformers vulnerable to remote code execution | fixed: 5.3.0 |
| CVE-2026-4538 | torch | [PYSEC-2026-139](https://osv.dev/vulnerability/PYSEC-2026-139): See retained advisory details | last_affected: 2.10.0 |
| CVE-2026-5241 | transformers | [GHSA-fgcw-684q-jj6r](https://osv.dev/vulnerability/GHSA-fgcw-684q-jj6r): huggingface/transformers: Arbitrary Code Execution During Model Initialization in the LightGlue Model Loading Path | fixed: 5.5.0 |
| CVE-2026-80047 | transformers | [GHSA-x9r9-c232-4q39](https://osv.dev/vulnerability/GHSA-x9r9-c232-4q39): Hugging Face Transformers downloads custom generation code before trust consent | last_affected: 5.8.1 |
| CVE-2026-9856 | transformers | [GHSA-xrqw-3rrv-vx5w](https://osv.dev/vulnerability/GHSA-xrqw-3rrv-vx5w): Transformers save_pretrained path traversal allows arbitrary file writes through chat template names | fixed: 5.10.0 |

These findings are an explicit **release blocker for this candidate**. Offline testing with hash-recorded existing assets does not remove or dismiss them. Actual exposure and compatible remediations require review; simply jumping to the highest fixed version can break the Torch/Torchaudio/TorchCodec/Transformers/Coqui compatibility set. No untrusted model/checkpoint or custom remote generation code was tested, no training/chat-template path was exercised, and no service was exposed.

The full raw advisory records, aliases, ranges, descriptions and references are retained. The scan is a point-in-time package advisory check, not security certification or a complete native-DLL/model audit.

Bundled wheel license/notice files were collected for 83 of 85 packages. The current extraction did not find bundled notices for **tensorboard-data-server, tokenizers**; these require exact-source notice/provenance follow-up. The full declared-license inventory and retained texts are available below. This collection does not settle transitive native-library/source-offer obligations, FFmpeg redistribution or model terms. The application's own license remains undecided; no license was assigned to the user's code.

## Changed files and evidence

Only development helpers, this candidate directory and validation/documentation artifacts changed in this pass. No production application source changed, so the previous 766-test backend and 47-contract frontend regression remain the production baseline; they were not rerun as a substitute for the actual new-runtime checks.

- `dev/build_xtts_runtime_candidate.py`: exact pinned archive fetch, safe fresh extraction, owned resume limits, offline cross-target installation, notice inventory, size measurement and temporary staging cleanup.
- `dev/verify_xtts_runtime_candidate.py`: actual candidate package/origin/dependency/arithmetic/decoding/parser checks with a fully blocked network guard.
- `dev/evaluate_xtts_runtime_candidate.py`: actual speech, model reuse, token-boundary cancellation and preserved-output/cleanup checks.
- `dev/check_xtts_candidate_speech_content.py`: real existing Whisper worker cross-check of generated audio.
- `dev/verify_xtts_candidate_preservation.py`: original asset/state/source integrity before and after evaluation.
- `dev/audit_xtts_candidate_advisories.py` and `dev/inspect_xtts_candidate_advisories.py`: public exact-version advisory lookup and retained detailed records; no installed audit framework.
- `dev/document_xtts_candidate_evaluation.py`: this report and consolidated evidence checks.

Evidence: [download receipt](validation/2026-10-13-xtts-candidate-downloads.json), [installation receipt](validation/2026-10-13-xtts-candidate-install.json), [runtime probe](validation/2026-10-13-xtts-candidate-runtime-probe-audited-network.json), [real speech/cancellation](validation/2026-10-13-xtts-candidate-live-evaluation-audited-network.json), [speech recognition](validation/2026-10-13-xtts-candidate-speech-content.json), [notice inventory](validation/2026-10-13-xtts-candidate-notices/inventory.json), [advisory scan](validation/2026-10-13-xtts-candidate-advisories.json), [advisory details](validation/2026-10-13-xtts-candidate-advisory-details.json), [original preservation](validation/2026-10-13-xtts-candidate-preservation-after.json), [staging cleanup](validation/2026-10-13-xtts-candidate-staging-cleanup.json), [consolidated integrity](validation/2026-10-13-xtts-candidate-iteration-integrity.json).

## What this unlocks and what remains

The tests establish that the existing XTTS checkpoint can load, generate and cancel using this clean supported-Python candidate. They remove the uncertainty that a successful metadata lock might still hide an unusable native/audio/model stack. They do not connect the app to this runtime or authorize an automatic default switch.

The next repair must resolve the known advisory versions while maintaining model/audio compatibility, then exercise the isolated worker bridge in a disposable app copy. RVC still needs its separate Windows/Fairseq/OmegaConf solution; desktop and other engine families need their own supported-runtime closure and acceptance. Full representative workflows, fresh-user setup/download retries, resource calibration, native process-crash recovery, clean-machine Windows prerequisites and licensing/portable-CI gates remain open. See the [repair map](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release readiness](RELEASE_READINESS_2026-10-04.md).

The original working setup remains usable for the previously validated Hindi workflow. This candidate remains an explicitly identified experiment, with production defaults unchanged and release eligibility false.
