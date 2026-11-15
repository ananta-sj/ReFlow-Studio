# Runtime dependency map and repair plan — 13 October 2026

**Current status: isolated XTTS candidate installed and technically validated; production defaults unchanged; release blocked.** The initial “go ahead” authorized plan preparation, followed by bounded Docopt approval. The later “so go ahead” after the complete 85-package review authorized candidate creation/testing. Its Python 3.13 package/audio/model/cancellation checks passed. Advisory findings prevent release eligibility. Historical planning receipts remain unchanged. See the [candidate iteration](XTTS_RUNTIME_CANDIDATE_ITERATION_2026-10-13.md).

## What needs repair

The working installation still executes tested jobs. Its 12 October regression run passed 766 tests, and real XTTS cancellation and the short Hindi render passed. A reproducible release has a different requirement: its installed files, declared package versions and dependency constraints must agree.

The core inventory contains **24 package names with duplicate distribution metadata**. Direct imports on 13 October identify:

| Loaded component | Actual imported version | Meaning |
| --- | --- | --- |
| Python | 3.10.11 | Existing embedded interpreter; preserve as the comparison baseline |
| Torch | 2.7.1+cpu | The main runtime is a CPU build; its compiled CUDA version is `None` |
| NumPy | 1.23.5 | Loaded numerical library, despite another NumPy metadata record |
| SciPy | 1.10.1 | Loaded signal-processing library |
| TTS | 0.22.0 | Original installed package; the source requirements instead describe maintained `coqui-tts` |

Separate GPU profiles can still execute GPU inference; a CPU-only main Torch does not establish that those profiles are broken. Conversely, a CUDA-looking duplicate metadata directory does not make the main runtime GPU-enabled. The reported core dependency failures are retained in [the captured audit](validation/2026-10-12-core-dependency-check-captured.log).

The decisive conflicting requirements are:

| Family | Published requirement | Consequence |
| --- | --- | --- |
| Maintained Coqui 0.27.5 | NumPy ≥1.26, SciPy ≥1.13, Transformers ≥4.57 | A modern XTTS worker needs its own compatible numerical/text stack |
| RVC Python 0.1.5 | NumPy ≤1.23.5, OmegaConf =2.0.6, Fairseq =0.12.2, FAISS =1.7.3 | It cannot share the proposed modern XTTS NumPy version |
| Fairseq 0.12.2 | Hydra ≥1.0.7 and <1.1; OmegaConf <2.1 | Installing the newer shared Hydra/OmegaConf versions does not satisfy this package |
| OmegaConf 2.0.6 | A `PyYAML (>=5.1.*)` requirement | The captured requirement fails modern requirement parsing; this is a rebuild blocker, not a reason to conceal the error |

Published sources: [Coqui metadata](https://pypi.org/pypi/coqui-tts/0.27.5/json), [RVC metadata](https://pypi.org/pypi/rvc-python/0.1.5/json), [Fairseq metadata](https://pypi.org/pypi/fairseq/0.12.2/json), [OmegaConf metadata](https://pypi.org/pypi/omegaconf/2.0.6/json). The captured metadata is [retained locally](validation/2026-10-13-runtime-repair-metadata.json).

## Python decision

Python's support table lists **3.10 as end-of-life from 1 October 2026**. Existing Python 3.10 engine profiles remain comparison baselines; they do not constitute the final supported-runtime proposal. [Official support table](https://devguide.python.org/versions/).

Proposed evaluation interpreter: **CPython 3.13.16, Windows x64, ordinary embeddable build**. This is a supported branch with a published Windows archive, and the selected numerical/audio packages have compatible Windows wheels. The exact interpreter is chosen for evaluation; it still needs actual native and engine acceptance. [Official release page](https://www.python.org/downloads/release/python-31316/).

Archive URL: `https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip`

Published SHA-256: `97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297`

The checksum was read from the release page. **The interpreter archive was not downloaded or verified against actual bytes in this pass.** No system Python, PATH, drivers or registry settings changed. No Conda, uv or new environment-management framework is proposed.

## Dependency ownership map

| Component | Current execution boundary | Repair direction |
| --- | --- | --- |
| Desktop, queue, settings, graph, cue review | Main embedded Python | A separately built desktop candidate with GUI/state/media helper packages; feature checks inspect the selected worker |
| Media extraction, mixing, subtitles and muxing | Python/pydub plus existing FFmpeg executable | Keep the existing media algorithms and binaries during comparison; provide `audioop-lts` on Python 3.13 |
| XTTS | Main-process `core/tts/tts_handler.py` through its provider | New persistent XTTS worker candidate; keep one model/session per render |
| RVC | Main-process `core/rvc/rvc_handler.py` | Separate dependency domain; rebuild recipe blocked pending a reviewed Windows-compatible solution |
| Default Whisper, NLLB/M2M100, Demucs | Main dependencies and/or workers using the core interpreter | Explicit media/recognition/translation worker ownership; preserve working routes until each candidate passes |
| IndicF5 | Existing CPU/GPU evaluation profiles | Preserve accepted voices/weights/recipes; migrate the runtime separately and verify the same media |
| Stronger Whisper and IndicTrans2 | Existing specialized/shared GPU profiles | Keep working model assets; record the actual interpreter/device and migrate without a global package upgrade |
| F5 voice cloning | Existing separate `f5` profile | Keep current working baseline; refresh and validate a supported-Python candidate independently |
| NudeNet | Existing `vision` profile | Preserve CPU-only isolation and masking behavior; independently verify migration |
| MuseTalk | Existing `musetalk` profile | Preserve its separate stack; validate moving-face execution and quality before switching |
| GFPGAN/Wav2Lip and classifier fallbacks | Core/vendor dependencies or core-interpreter workers | Keep older vision dependencies out of the modern speech stack; define and verify their worker recipes |
| Cloud/custom/local API providers | Existing explicit connection configuration | No live/paid provider calls or connection changes are part of this repair |

This is an ownership target, not a claim that the code already delegates every stage. In particular, `config.py` currently imports Torch at startup; `IntegrityDoctor` checks several optional AI libraries as core libraries; XTTS and RVC run in-process; and the default worker resolver returns the main interpreter. A small desktop environment cannot simply replace the current Python folder and boot unchanged. These integration points must be repaired and tested during candidate construction.

The existing `FeatureSession`/owned-process implementation provides a reusable starting point. It already supports an explicit executable, worker and operation. Worker lifecycle, cancellation, publication and diagnostics should follow those existing contracts rather than introduce a second orchestration framework.

## Proposed first evaluation: XTTS on CPU

Create only a new owned `runtime_profiles/xtts-candidate` after approval. Reuse existing XTTS weights and test media. Preserve the current runtime, model registry and selected engines. The first evaluation uses CPU to establish package compatibility and output correctness; a matching GPU candidate follows after that acceptance and its scoped approval.

### Exact candidate root pins

These are **proposed root pins**, verified against captured package metadata and Windows/Python wheel tags. They are **not a complete transitive lock or installation command**.

| Package | Candidate version | Why it is included |
| --- | --- | --- |
| `coqui-tts` | 0.27.5 | Maintained library for the existing XTTS model; do not also install original `TTS==0.22.0` in this candidate |
| `torch` | 2.9.1+cpu | CPU model execution, using the official CPU wheel |
| `torchaudio` | 2.9.1+cpu | Audio operations paired with the same Torch release/build |
| `torchcodec` | 0.8.1 | Required audio decoding for this Torch generation; test with the existing shared FFmpeg libraries |
| `numpy` | 2.3.5 | Python 3.13 numerical wheel; isolated from the RVC cap |
| `scipy` | 1.16.3 | Signal processing satisfying Coqui's minimum |
| `transformers` | 4.57.1 | Satisfies this Coqui version's minimum while retaining a below-5 candidate boundary |
| `numba` | 0.63.1 | Audio dependency chain's compiled numerical operations |
| `llvmlite` | 0.46.0 | The matching compiler library distributed as a wheel; this does not propose installing a system compiler |
| `soundfile` | 0.13.1 | Existing audio read/write interface |
| `anyascii` | 0.3.3 | Text transliteration required by the maintained Coqui package |
| `aiohttp` | 3.14.3 | Proposed HTTP helper for the required `fsspec[http]` chain; freeze and confirm that dependency edge in the full closure |
| `pydub` | 0.25.1 | Existing Reflow audio preparation/validation code |
| `audioop-lts` | 0.2.2 | Supplies the audio operations removed from Python 3.13, needed by pydub |

PyTorch publishes the matching 2.9.1 CPU/Torchaudio combination. TorchCodec's compatibility table pairs its 0.8 series with Torch 2.9 and Python through 3.13. The official CPU indexes contain the selected standard `cp313` Windows wheel links and SHA-256 fragments. [PyTorch versions](https://pytorch.org/get-started/previous-versions/), [TorchCodec compatibility](https://github.com/meta-pytorch/torchcodec#compatibility-with-torch-versions).

All root candidates have a compatible Windows or universal wheel and allow the proposed Python version in their metadata. NumPy 1.26.4 was considered because several existing profiles use it, but that release has no standard Python 3.13 wheel. This is why it is not the numerical pin for this candidate. Wheel existence and compatible declared constraints are planning evidence, not proof of model execution, numerical equivalence or security clearance.

### What the previous missing-package list does not mean

The original audit reports requirements of old `TTS==0.22.0`. That list should not be copied blindly into the maintained candidate:

- `encodec` is not a base requirement of the captured Coqui 0.27.5 metadata. It may be needed in other profiles such as F5; that does not make it a root XTTS dependency here.
- `unidecode` is not a base requirement in that metadata; `anyascii` is. A final transitive resolution may still introduce a text helper through another required dependency.
- `umap-learn` appears under optional `all`/`notebooks` extras. The proposed inference candidate does not request those extras.
- Korean language processing has its own extra; the candidate does not request every language extra automatically. Required base packages remain required, including Coqui's declared Korean/text helper. A language-specific runtime acceptance matrix is still needed.
- SpaCy, blis and thinc are not direct root choices for this XTTS candidate. If the complete selected dependency closure requires them, their versions and reason must be reviewed before installation.

Mandatory indirect packages such as Coqui's trainer/config/alignment helpers must still be resolved and recorded. Dependencies will not be suppressed merely because their names sound training-related. [Coqui installation and optional extras](https://coqui-tts.readthedocs.io/en/latest/installation.html).

### Full resolver result: one source-only helper still needs preparation

The guarded metadata-only package-manager dry run reached a concrete blocker: required `num2words` depends on **`docopt>=0.6.2`**, but no published binary wheel is available for that helper. The proposed source-helper pin is **`docopt==0.6.2`**. It parses command-line arguments used by that dependency; it is not another AI model. Its upstream setup declares a Python module rather than a native extension, so this particular build is expected to need ordinary Python packaging tools rather than a C++ compiler. Actual Python 3.13 behavior still requires verification. [Published metadata](https://pypi.org/pypi/docopt/0.6.2/json), [upstream setup](https://raw.githubusercontent.com/docopt/docopt/0.6.2/setup.py).

The published source archive is **25,901 bytes**, SHA-256 `49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491`. It was **not downloaded or executed**. After review/approval, a controlled local wheel build with retained source and notices can supply the resolver with a hashed artifact. Its full dependency resolution must then finish before installing the candidate. No source-build exception was silently enabled.

The initial resolver attempts used direct CPU archive links, then index metadata. The guard stopped the former before archive transfer; the latter reached the missing Docopt wheel. Both failed attempts are retained. Following the user's bounded helper-build approval, Docopt was built locally and a later metadata-only resolution completed. The target-specific review lock now contains 85 packages. Actual interpreter/engine acceptance and installation approval remain pending. [Direct-URL transfer rejection](validation/2026-10-13-metadata-only-direct-url-blocked.json), [initial index-resolution log](validation/2026-10-13-metadata-only-index-resolution.log), [completed helper and lock preparation](XTTS_DEPENDENCY_LOCK_PREPARATION_2026-10-13.md).

## Desktop candidate root versions

These are a separate proposed GUI/media-helper set after worker delegation exists:

| Function | Candidate pins |
| --- | --- |
| Existing Windows interface | `pywebview==6.2.1`, `pythonnet==3.1.0` |
| Hardware/process observation | `psutil==7.2.2` |
| Audio manipulation | `pydub==0.25.1`, `audioop-lts==0.2.2`, `soundfile==0.13.1`, `cffi==2.0.0` |
| Existing HTTP, locking and metadata | `requests==2.32.5`, `filelock==3.20.3`, `packaging==26.0` |
| Existing credentials, tray and images | `keyring==25.7.0`, `pystray==0.19.5`, `pillow==11.3.0` |

Captured metadata confirms compatible root wheel tags and Python ranges. These are not a resolved desktop lock. CLR loader and other Windows dependencies must be pinned as part of the full closure. WebView2, VC runtime and the selected Windows version remain native acceptance prerequisites. No GUI framework change is proposed.

## RVC rebuild blocker and next investigation

`rvc-python==0.1.5` has a universal Python wheel. Its required Fairseq 0.12.2 release has native wheels for older Linux/macOS interpreters and a source archive, but no Windows wheel. The root RVC package being universal does not solve that native dependency. Its old NumPy and OmegaConf requirements also conflict with the proposed modern speech worker.

The plan therefore does **not** label a complete RVC lock as solved. Next, inspect the precise inference-only dependency path and prepare a reviewed Windows recipe. If a compiler, different backend or third-party replacement is required, present its exact scope for approval first. No compiler, Conda environment, alternative RVC framework, old installer downgrade or unreviewed binary has been installed.

Genuine RVC model acceptance also needs an authorized valid inference checkpoint and its optional index. Import success alone cannot replace that test. Preserve unverified/custom voice assets.

## Existing profiles and portability work

The IndicF5 GPU profile currently records an absolute path to the CPU profile's non-Torch dependencies. That arrangement can work at the current location, but must be made portable and hash-bound before a release copy is moved elsewhere. Special engine setup code also uses evaluation-named profile locations. Declared profile status is not uniformly equivalent to proven engine readiness; actual acceptance receipts and dependency/device probes should determine readiness.

For each profile, record interpreter version, artifact/package hashes, owned dependency paths, device capability and setup completion. Resolve project-owned resources relative to the portable root while retaining explicit external user-media paths. Record runtime identity in execution/cache fingerprints so an old result is not misrepresented as validation of a new runtime. Never copy personal reference audio or authentication credentials into the distributed package.

The supported-Python migration includes the existing optional profiles, not just the GUI. Keeping Python 3.10 profiles for comparison does not close that release gate.

## Sequence and acceptance gates

1. **Review this map and candidate pins.** Complete. The only downloaded source archive was the subsequently approved 26 KB Docopt helper; no executable or published wheel archive was downloaded.
2. **Freeze the complete dependency closure.** XTTS metadata closure, target marker checks, exact artifact hashes and archive download budget are now prepared. The approved Docopt wheel is retained with its license and recipe. Exact installed disk usage, complete notice review and actual Python 3.13 execution remain pending. Desktop and other engine closures remain separate work.
3. **Obtain bounded installation approval.** The reviewable request should describe the exact candidate, required packages, resource cost and reuse of existing weights. Keep RVC's unresolved build/replacement decision outside that first install.
4. **Build the XTTS candidate in a new owned directory.** Use a clean interpreter and reviewed artifacts, not a copied polluted `site-packages`. Keep installers and staging owned; do not modify system Python/PATH/drivers. Preserve the original runtime and registry.
5. **Validate the package environment.** Require zero duplicate distribution records, valid metadata, dependency-check success, expected import origins and actual CPU/audio arithmetic/decoding. Verify shared FFmpeg DLL discovery; `ffmpeg.exe` alone does not provide those decoder libraries.
6. **Exercise actual existing XTTS weights.** Use existing benchmark media and explicit local paths. Block network/model auto-download during inference. Test successful speech, decoder sample rate, non-silent media, token-boundary cancellation, previous-output preservation and temporary cleanup. Compare naturalness/timing and cold/warm execution with the working baseline.
7. **Implement and test worker routing in a disposable app copy.** Preserve model lifetime per render, bounded requests/logs, child ownership, cancellation and output publication. Update readiness, resource routing and cache/runtime identity. Keep heavy stage choices immutable for an accepted running job.
8. **Construct the desktop candidate.** Defer AI imports from GUI startup and make integrity/readiness feature-scoped. Run current backend/interface contracts and real native startup/review/queue/recovery checks. Do not run the production app with a new interpreter against the user's original state as a shortcut.
9. **Migrate remaining worker families independently.** Solve and validate RVC, media/recognition/translation and optional vision/Hindi profiles. GPU testing uses a separately identified matching build and measured capability; no speedup is promised from package names alone.
10. **Verify the actual Windows release artifact.** Relocation, fresh model/reference setup, interrupted downloads, representative long/moving/noisy media, actual native process-crash recovery, memory/VRAM/throughput measurements and clean-machine acceptance still apply. Complete exact component notices and the owner's licensing decision before publication.

Switch defaults only after acceptance and explicit review of the candidate. A failed candidate can be discarded by removing only its verified owned directory; the original working setup remains usable. Removing duplicated model files is not part of this trial because it reuses the existing model locations.

### Candidate execution completed later on 13 October

The reviewed CPU candidate was installed separately. Fourteen actual runtime checks and real existing-checkpoint speech/model-reuse/cancellation checks passed. The existing Whisper worker recognized the generated sentence with zero normalized word errors. Measured candidate size was 960,336,065 bytes at installation completion; 291,023,750 bytes of owned staging were removed. No production default, original model or saved state changed. Docopt's previously pending Python 3.13 parser check now passes.

The security scan found advisory matches in Torch 2.9.1 and Transformers 4.57.1. These versions remain evaluation-only; compatible remediation must precede release. Notice texts were collected for 83 packages, with exact-source follow-up still needed for tokenizers and tensorboard-data-server. Candidate model execution does not close worker-bridge, all-engine, licensing or clean-machine release gates. The [detailed completion report](XTTS_RUNTIME_CANDIDATE_ITERATION_2026-10-13.md) records measurements, retained failures and corrected offline checks.

### Subsequent security and session preparation

The existing candidate now passes an actual persistent session-interface test: two requests use one process/model, invalid input is rejected, and cancellation preserves prior output and cleans the worker job. Production selection is unchanged. A metadata-only 99-package CPU replacement lock with six changed versions and fourteen added support dependencies has zero current OSV matches; archive budget is 304,189,555 bytes. This revised stack is not installed and Coqui/Transformers model compatibility is untested. Exact versions, package purposes, risk, installation scope and the next approval boundary are recorded in the [security and worker plan](XTTS_SECURITY_AND_WORKER_PLAN_2026-10-13.md).

### Approved replacement installed and evaluated

After explicit user approval, the separate 99-package replacement was built with the reused verified Python bootstrap and existing weights. It now passes native/import/audio/parser checks, real speech and cancellation, persistent model/worker reuse and actual recognition. Its exact-version adapter resolves the removed helper and dense-mask/position assumptions without modifying installed third-party source. Earlier failed attempts are preserved. Installation measured 1,055,079,244 bytes, and 304,210,617 bytes of installer staging were removed. The original setup and app defaults remain unchanged.

The reviewed package-advisory gate is clear at the recorded scan time; this is not full release security clearance. The production provider boundary, adapter-bound readiness/cache identity and wider inputs/devices still need implementation and disposable-copy acceptance. Full remaining runtime, licensing, workflow and clean-machine gates continue to apply. [Detailed approved replacement report](XTTS_SECURITY_RUNTIME_ITERATION_2026-10-13.md).

## Evidence and limits of this planning pass

The metadata/wheel/constraint/state checker passed **15 checks**. It verifies selected root compatibility, identified RVC conflicts and unchanged protected app state. Following bounded Docopt approval, a guarded metadata-only dry run resolved the XTTS tree; independent Windows/Python 3.13 marker, wheel-tag and version checks passed for 85 required packages and 128 active links. This certifies the declared candidate metadata closure, not actual model execution. No libraries were installed or models loaded; no full backend rerun was needed because production code did not change.

- [Machine-readable proposed pins, wheel hashes and blockers](validation/2026-10-13-runtime-repair-plan.json)
- [Captured upstream metadata](validation/2026-10-13-runtime-repair-metadata.json)
- [Planning check results](validation/2026-10-13-runtime-repair-plan.log)
- [Previous release audit](WINDOWS_RELEASE_ITERATION_2026-10-12.md)

All five protected state files match the previous accepted baseline. Only the approved Docopt source archive was downloaded and its wheel built locally; published package wheel archives, Python installers and model weights were not downloaded. No runtime folder was created, no installed package was upgraded/removed and no registry/voice selection changed. The temporary Ollama trial remains removed. See the [detailed completion record](XTTS_DEPENDENCY_LOCK_PREPARATION_2026-10-13.md) for exact artifacts, retained failures, cleanup, package inventory and remaining gates.
 
## Subsequent production integration

The approved XTTS replacement now has an explicit CPU trial through the application's provider, with persistent worker reuse, runtime/model manifest identities, setup inspection and parent-owned output publication. Real child-crash/output-preservation/new-job-recovery acceptance passed. No new dependency or model was added, and app defaults remain unchanged. The current integration report supersedes earlier statements that the provider boundary was unimplemented; release migration and wider acceptance remain pending. [Detailed changes, regression reruns and remaining gates](XTTS_PRODUCTION_INTEGRATION_2026-10-13.md).
 
## Saved selection and portable recipe closure

The optional XTTS CPU route is now selectable in Settings and wired into rendering/readiness/review. The portable builder can include its runtime and exact dependency lock; relocated actual speech, stage-worker release without cancelling the job, generation cancellation and cleanup passed. Future assembly uses bounded standard-library copy threads. The shared runtime and RVC-family repair still require their reviewed migration path; this CPU trial does not upgrade those environments or change defaults. [Detailed selection and portable iteration](XTTS_SELECTION_AND_PORTABLE_ITERATION_2026-10-13.md).

## Desktop import ownership corrected

The latest source tolerates missing/broken legacy Torch during desktop module startup, separates desktop integrity from explicit shared AI diagnostics, and checks the saved isolated XTTS route in audio/video preflight. Ten new cases bring the complete backend suite to 800 passing tests. Real subprocess probes imported the desktop and exported source subtitles while AI imports were blocked; this is not native GUI or new-runtime installation acceptance. The clean desktop closure must include tqdm and the full support dependency set, not just the previously proposed roots. No packages were installed. Original user state, model assets and isolated-runtime identity remain unchanged. The earlier portable QA artifact is retained without these source updates. [Detailed boundary iteration and evidence](DESKTOP_RUNTIME_BOUNDARY_ITERATION_2026-10-13.md).

## Revised desktop dependency proposal

The metadata-only desktop projection contains 31 packages and 22 active declared dependency links, totaling 24,683,768 published artifact bytes. Initial Pillow 11.3.0/Requests 2.32.5 proposal pins produced 38 advisory query matches; the proposal now uses Pillow 12.3.0/Requests 2.34.2, with zero current package matches in the revised scan. Installed packages remain unchanged. The binary-only resolver cannot complete until pywebview's source-only `proxy-tools==0.1.0` helper is built under separate approval. A 2,978-byte hash-bound source build is the narrow next request; the projection is not an installable lock or approval to install the desktop runtime. Five planning tests and eight preservation/integrity checks pass. [Exact package reasons, notices, costs, build procedure and limits](DESKTOP_RUNTIME_PROPOSAL_2026-10-13.md).

## Approved desktop helper and completed lock

The user approved only the proxy helper build/testing and lock preparation. The 2,978-byte source was hash-verified; its 3,956-byte wheel passed RECORD/source checks and a real Python 3.13 smoke test without installation. The archive omitted its license and contradicted its module's BSD label; a pinned supplemental upstream notice is retained in the wheel and that distribution-review issue remains explicit. Genuine metadata resolution and independent target validation now produce a 31-package/22-link lock, excluding three host-only dependencies and selecting more-itertools 11.2.0. Final artifacts total 24,686,927 bytes; the exact-version scan has zero current matches and all 12 preservation/integrity checks pass. No desktop environment was installed. [Detailed build, final lock, cost and separate installation proposal](DESKTOP_HELPER_AND_LOCK_COMPLETION_2026-10-13.md).

## Approved desktop installation and deep acceptance — 14 October

The user then approved the separate candidate and deep tests. The exact 31-package Python 3.13 desktop candidate is installed independently. Actual native WebView2 screens/selector, Windows credential/audio/state operations and isolated CPU XTTS speech/cancellation passed. The scoped desktop suite passes 438 tests; all 1,793 installed payload files match RECORD. The broader suite attempt fails with one failure/twelve errors because legacy AI libraries/routes remain absent; it is not an 800-test candidate pass. Installer staging was removed, original state/models/source preserved, and defaults unchanged. The retained 91,376,775-byte desktop candidate is validated only within that scope. Supported default AI worker migration and full-app/native clean-machine/licensing gates remain open. [Detailed acceptance, failed runs and approval limits](DESKTOP_CANDIDATE_ACCEPTANCE_2026-10-14.md).

## Recognition proposal and import repairs — 15 October

Unused Torch imports were removed from the Ollama/M2M100 wrapper and faster-whisper handler; their actual engine boundaries remain intact. The full working-runtime regression suite now passes 802 tests, with scoped desktop local-translation/boundary cases also passing. A guarded metadata-only recognition lock contains 24 packages, 31 satisfied target links and 85,325,533 download bytes, with zero current exact-version advisory matches. No recognition runtime was installed. Existing Whisper turbo assets and owned CTranslate2 conversion tools offer an offline evaluation route, subject to conversion acceptance and separate scoped installation approval. NLLB/M2M100/Demucs and remaining AI workers still need explicit supported-runtime ownership. [Detailed changes, retained failed focus run, exact package plan and proposed approval scope](RECOGNITION_MIGRATION_PLAN_2026-10-15.md).

## Approved recognition evaluation — partial acceptance

The approved 24-package candidate is installed separately; existing Whisper weights were converted offline into an 817,887,676-byte int8 copy without a model download. Conversion and decoding required two narrowly version-checked adapters; installed package source remains unchanged. English/silence/malformed-media and desktop-worker/cancellation tests pass, with 807 full backend regressions and 2,316 verified payload files. Automatic Hindi failed by choosing Urdu script; an explicit Hindi hint produced Devanagari but WER was about 25.8%. The acceptance receipt therefore remains `passed=false` with technical checks true. Defaults are unchanged; feature-specific routing/source hints and broader quality acceptance remain pending. Owned staging/cache cleanup completed; three package notice gaps remain. [Detailed failures, repairs, measurements and partial decision](RECOGNITION_CANDIDATE_ACCEPTANCE_2026-10-15.md).

## Recognition source-hint propagation completed — 15 October

The shared audio and video recognition paths now propagate explicit language choices through the CPU subprocess and GPU session worker. Selection enters the recognition cache identity; forced-language results carry `language_origin=hint` and no detection confidence through JSON, grouping and checkpoints. OpenAI-compatible cloud form handling and explicitly configured custom form fields are covered by mocked requests only. Actual offline desktop-to-worker Hindi checks pass on both existing CPU/GPU routes, with owned worker cleanup. Full shared-runtime regressions pass 815 tests; 79 overlapping desktop-scoped tests include the four subsequently added cases. The package/state/model checks remain intact; the intentionally repaired pipeline is recorded as an expected historical hash difference. No dependencies, models or defaults changed. Per-feature production selection and auto-language/accuracy acceptance remain unfinished. [Full repair and evidence](RECOGNITION_LANGUAGE_REPAIR_2026-10-15.md).

## CPU recognition explicit routing completed — 16 October

The existing 24-package recognition runtime is selectable through Settings as an isolated CPU trial. A portable recipe validates bootstrap/inference-source/lock hashes and installed versions; a bounded probe checks native imports in that environment. Audio/video jobs and preflight use the frozen selection, and manifests record the actual interpreter/identity. API and GPU routes remain independent. Actual recognition passes 18 checks, native interface acceptance 26, backend regressions 831, and final desktop-scoped regressions 104 overlapping tests. No package/model/default changes were made. The first real probe exposed a psutil coupling, removed with standard-library helpers. Translation/separation/RVC/visual runtime ownership, accuracy and other release gates remain open. [Full iteration](RECOGNITION_RUNTIME_ROUTING_2026-10-16.md).

## NLLB isolated CPU trial integrated — 16 October

The existing modern CPU environment can load the current NLLB checkpoint without new packages. NLLB now has a saved explicit runtime choice, a bound worker recipe, owned persistent session, real preflight/dependency probe and stage cleanup; cue-review translation also releases on error. Source/target token and completion guards remain. Actual worker checks pass 13 assertions, native settings 22, full backend regressions 846 and desktop-focused regressions 76 overlapping tests. No new package/model/default change was made. M2M100 is not migrated: this environment lacks SentencePiece, and adding it directly would invalidate the exact XTTS lock. A separate reviewed environment is needed before any installation request. [Detailed iteration and remaining work](NLLB_RUNTIME_ROUTING_2026-10-16.md).

## M2M100 candidate proposed; package approval pending — 16 October

The separate `translation-candidate` proposal reuses the existing embedded Python and 40 package distributions, adding only SentencePiece 0.2.2 for CPython 3.13 Windows x64. Metadata validates 41 packages and 48 required links, approximately 634.62 MiB of copied files plus unpacked SentencePiece, with a 1.19 MiB new archive transfer. Current OSV lookup reports zero exact-version matches. No wheel/archive, runtime, model or default has been changed. Independently authorized target-token validation and local model cleanup repairs pass 853 full tests and 17 focused overlapping tests. The new runtime requires the user's explicit installation approval before build or live worker tests. [Reviewable plan, exact versions/hash/size and test scope](M2M100_RUNTIME_PLAN_2026-10-16.md).

## M2M100 separate CPU trial accepted technically — 16 October 2026

Following explicit approval, the separate 41-package translation candidate is built from 40 existing packages and the pinned SentencePiece 0.2.2 wheel. Settings, frozen execution, preflight, readiness, manifest evidence and portable inventory support explicit isolated selection; defaults remain legacy. Actual offline subtitle pipeline/session/cancellation checks pass 17 assertions, candidate native checks 56, native interface checks 22, backend regressions 867 and focused regressions 73 overlapping tests. Owned staging cleanup removed 1,248,026 bytes; original runtime/state/model hashes are preserved. Installed notices cover 39 packages, with separately recorded official version-tag supplements for the other two; legal clearance remains open. Full video, semantic quality, remaining engine migrations, clean-machine and other release gates remain open. [Detailed acceptance and evidence](TRANSLATION_CANDIDATE_ACCEPTANCE_2026-10-16.md).

## Separation runtime boundary audited — 16 October 2026

Real one-second separation succeeds only with the original portable worker; the modern desktop lacks Torch and the translation runtime lacks Demucs. Cancellation now preserves RenderCancelled, fixed status text works in a legacy Windows console encoding, and a bounded no-model Demucs probe is available. Backend regressions pass 878 tests and desktop-focused checks pass 24 overlapping tests; actual active-child cancellation returns in 0.117 seconds with cleanup. Original state/model/runtime identities remain preserved. No packages or model archives were downloaded or installed. Metadata inspection identifies ten additional Demucs dependencies, including four source-only package versions needing an approved helper-build step before a lock/runtime proposal. Clean separation routing, quality and full-release gates remain open. [Audit, retained failures, exact source artifact hashes and next approval scope](SEPARATION_RUNTIME_AUDIT_2026-10-16.md).

## Approved Demucs helpers and prepared lock — 16 October 2026

The four approved source archives (1,476,709 bytes) produced verified pure-Python wheels with 126 byte-matched source files. Python 3.13 acceptance passes 14 bounded checks, including real resampling and a modern audio-writer roundtrip. Code inspection added the existing TorchCodec package as an operational requirement missed by declared dependencies. The final 32-package lock passes a genuine metadata-only resolver and independent artifact/requirement review; the 32-version OSV query has zero current matches. A missing ANTLR notice is supplemented from the official release tag without altering the wheel. Cleanup removed 4,881,561 bytes of owned staging; original sources/state/model/runtime identities are preserved. No separation runtime is installed. The separate installation proposal uses 22 copied packages, four existing built wheels and six downloads totaling 365,848 bytes; defaults stay unchanged pending approval. [Detailed completion, retained failures and next scope](SEPARATION_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md).

## Approved isolated CPU separation integrated — 16 October 2026

The approved 32-package candidate is built separately (615,796,387 bytes), with 365,848 bytes of pinned wheel downloads and existing Demucs weights. Saved explicit trial selection now reaches frozen audio/video jobs, correct isolated preflight, readiness/probe, manifest evidence and portable inventory; defaults remain legacy. A precise legacy NumPy scalar alias repairs restricted checkpoint loading without unrestricted pickle or package-source changes. Actual repeated stereo PCM16 stems match, cancellation returns in 0.111 seconds, native dependencies pass 48 checks, native interface 22, full backend regressions 891 and focused desktop checks 46 overlapping cases. A real six-second English video with separation/recognition/XTTS passes nine checks and fully decodes, but takes 213.997 seconds on CPU and does not validate Hindi or audible leakage/naturalness. Owned staging cleanup removes 365,886 bytes; original state/models/runtime identities remain preserved. Remaining engines, broader workflows/performance, fresh portable/clean-machine/manual and licensing gates remain open. [Complete implementation, evidence and retained failures](SEPARATION_CANDIDATE_ACCEPTANCE_2026-10-16.md).

## Remaining voice/visual engines audited and repaired — 16 October 2026

RVC and Wav2Lip now preserve RenderCancelled; fixed Wav2Lip status strings work in a cp1252 test. Detector/enhancer wrappers defer heavy imports, allowing actual existing NudeNet filtering from the clean desktop: eight checks pass, including failed-input output preservation. Actual legacy GFPGAN runs three face-model forwards and publishes three decoded frames in 92.329 seconds; legacy Wav2Lip also produces a valid one-second/three-frame result in 11.875 seconds. All 896 backend regressions and 21 overlapping focused checks pass. RVC/GFPGAN/Wav2Lip still lack clean desktop engine runtimes. MuseTalk dependency checks pass without new full rendering. F5 remains unverified after bounded startup timeouts, with a captured stack inside Transformers import-structure construction. Scoped inventory finds 37 registered voice entries, none installed and no usable RVC checkpoint in searched project/registered locations. No packages/models/defaults changed; protected state and all five isolated runtime identities remain preserved. [Detailed observations, tests, source changes and release gaps](REMAINING_ENGINE_AUDIT_2026-10-16.md).

## F5 startup repair and visual helper proposal — 16 October 2026

The optional F5 worker/probe startup failure is repaired without package installation: two exact hash-bound upstream modules are compiled in memory with ASR/training imports deferred. Installed sources remain unchanged. Reference transcription and speech generation pass separately; 907 backend and 40 overlapping focused regressions pass, with all 11 final checks satisfied. CPU speech remains slow; full automatic-reference/persistent/GPU and quality acceptance remain open. All five established runtime identities and protected state remain preserved. Official visual package metadata identifies BasicSR 1.4.2 and FilterPy 1.4.5 as source-only helpers (350,509 bytes combined); their download/build and lock preparation require separate approval. Runtime installation is excluded. [Complete findings and bounded next scope](F5_STARTUP_REPAIR_AND_VISUAL_PLAN_2026-10-16.md).


## Visual helpers built and exact guarded candidate proposed — 16 October 2026

Two approved sources (350,509 bytes) produced verified wheels with 128 byte-matched Python sources plus one generated version file; seven real helper checks pass under Python 3.13. Actual target metadata resolution and independent artifact review confirm 55 packages/96 active dependency edges. Two advisory records alias one BasicSR vulnerability (CVE-2024-27763); the lock remains security_clear=false. A no-install prototype blocks three distributed-training launchers with zero shell calls, but production mitigation and real modern GFPGAN inference remain untested. All 18 final preservation/preparation checks pass and 2,771,202 bytes of owned staging were removed. No runtime/model/default changes occurred. Separate proposed installation uses 41 copied packages, two retained helpers and 12 pinned downloads (64,466,647 bytes); explicit approval and guarded acceptance are required. [Full iteration, failures, exact inventory and next scope](VISUAL_HELPERS_AND_RUNTIME_PLAN_2026-10-16.md).

## Isolated CPU face enhancement technically validated — 16 October 2026

The approved separate 55-package visual candidate is installed with 64,466,647 bytes of pinned wheel downloads and existing local GFPGAN/detector/parser weights. Exact-source application guards disable BasicSR distributed training and adapt its old TorchVision import without changing installed package bytes. A lightweight media helper split removes an accidental audio/pipeline dependency from frame processing. Real restoration/failure/cancellation passes ten checks (three model forwards; cancellation 0.119 s), native dependencies 74, native interface 22, and post-processing pipeline integration nine with an explicitly substituted source-audio fixture. Final backend regressions pass 930 tests and focused checks 48 overlapping tests. A full generated dub separately fails the timing guard (6.605 s needed, 6.000 s available) before enhancement; it is not counted as successful dubbing. All 21,572 recorded payload files verify; runtime size is 1,048,855,925 bytes with no cache directories. Cleanup removed 64,466,681 bytes of owned staging. Existing user state, five established runtime identities and tested assets are preserved; defaults stay legacy. The upstream BasicSR advisory remains recorded, one distribution lacks an installed notice, and speech timing, broader workflows/performance, GPU, fresh portable/clean-machine and licensing gates remain open. [Complete iteration, failures, provenance and measured acceptance](VISUAL_RUNTIME_ACCEPTANCE_2026-10-16.md).

## Speech timing mechanics repaired; dense-line adaptation remains open — 16 October 2026

Non-Hindi fitting no longer slows short speech to fill a window; final cues may use actual remaining media time in sequential and parallel execution. Native preflight uses the same bounded media window, with existing ASR rounding tolerance capped at source end. Audible overflow retains a complete hash-verified take and a needs-review report instead of losing the generated audio. A single seeded English XTTS diagnostic produced 10.209 s for the dense six-second line, with only 0.416667 s of exact trailing silence; actual replay at the existing 1.3x limit still needs 7.853 s. Seven replay checks pass with no further model calls; the original six-second cue remains incomplete. Final backend regressions pass 936 cases, focused acceptance 131 overlapping cases, and all nine preservation/acceptance checks pass. Six established runtime identities, original XTTS assets, protected state and built frontend are preserved; no new packages/models/defaults/external AI calls occurred. Dialogue assistance is off with no configured instruction model. Automatic wording adaptation, full-workflow quality and prior release gates remain open. [Detailed diagnosis, repairs, failed attempts and evidence](SPEECH_TIMING_REPAIR_2026-10-16.md).
