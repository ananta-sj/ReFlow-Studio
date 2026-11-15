# F5 startup repair and visual-runtime preparation — 16 October 2026

## Outcome and scope

This iteration addresses the bounded F5 startup failure found in [the preceding remaining-engine audit](REMAINING_ENGINE_AUDIT_2026-10-16.md). It also prepares a metadata-only visual dependency proposal. No package, model or replacement runtime was installed; no application default was changed. Windows portable is the release target. Full release approval remains **false**.

This is the optional **base F5-TTS** worker, using its existing English checkpoint/reference. It is not an IndicF5 Hindi quality experiment. No new listening approval, naturalness claim or end-to-end Hindi acceptance is inferred from these technical tests.

## Root cause and repair

Installed `f5-tts==1.1.22` eagerly imported `transformers.pipeline` through `f5_tts.infer.utils_infer`, even when the caller supplied reference text. A second eager import in `f5_tts.model.__init__` loaded `Trainer`, then wandb/Accelerate and Transformers. Deferring only the ASR import was insufficient: the retained stack traces show the training import path still active.

`core/f5_imports.py` now supplies an application-owned, scoped import adapter. It verifies the installed distribution version and the exact SHA-256 of two reviewed upstream source files, then compiles those sources in memory with only their optional imports deferred. Installed package files are never rewritten. The real Transformers pipeline is imported and called with unchanged arguments when transcription is needed. The real Trainer remains available through a lazy module attribute and is cached when requested. Unrelated imports are ignored; the temporary import hook is removed on success or failure. A different version or changed source fails explicitly and requires a new review.

| Reviewed upstream file | SHA-256 |
| --- | --- |
| `f5_tts/infer/utils_infer.py` | `b05b7b159ceabe07f318b68c082970ec14ba8481fe2812e3774f8246628267c8` |
| `f5_tts/model/__init__.py` | `a27d1406ccf102af4dfc9e5c9071f06739e21eb356f312784274731f088953a0` |

`core/feature_worker.py` uses that adapter for single-shot and persistent F5 workers. Reference preparation now precedes the first speech-model construction. A failing reference does not load speech weights. Persistent sessions create the speech model once, after the first successful reference, and reuse it for subsequent cues. Existing transcript caching and reference-ASR release remain in place. A later, different reference may still require ASR while the persistent speech model is resident; no measured peak-memory reduction is claimed.

`core/runtime_probe_worker.py` checks the adapted F5 API and required audio decoder imports without constructing a speech model. Its existing 90-second deadline is unchanged. Its report explicitly distinguishes deferred ASR/training imports from tested imports. The in-process fallback in `core/providers/voice/f5tts_local.py` still follows its existing upstream import path; this repair covers the optional worker/probe route.

## Actual execution evidence

| Check | Observed result | Receipt |
| --- | --- | --- |
| Bounded API startup, existing CPU runtime | Passed in 17.86 s; no speech model constructed; Transformers, Trainer and wandb absent from loaded modules | [startup](validation/2026-10-16-f5-lazy-startup.json) |
| Dependency probe with unchanged deadline | Passed, existing Torch `2.9.1+cpu`; no model loaded | [probe](validation/2026-10-16-f5-lazy-probe-complete.json) |
| Actual automatic reference transcription | 96.343 s; expected words matched; ASR model released afterward | [reference ASR](validation/2026-10-16-f5-reference-asr.json) |
| Initial actual English synthesis | Passed, non-silent 1.227 s / 24 kHz; 179.624 s CPU run | [initial speech](validation/2026-10-16-f5-lazy-speech.json) |
| Final speech rerun after worker ordering change | Passed; non-silent 1.227 s / 24 kHz, peak 28,848; 182.282 s CPU; upstream source/model hashes preserved | [final speech](validation/2026-10-16-f5-lazy-speech-final.json) |
| Final regression and preservation checks | All 11 assertions passed; 907 backend and 40 overlapping focused tests | [acceptance](validation/2026-10-16-f5-startup-acceptance.json) |

Reference ASR returned **“Some call me nature. Others call me Mother Nature.”** The original supplied reference transcript was “Some call me nature, others call me mother nature.” Word comparison ignores punctuation/case. The synthesis used the supplied transcript and generated **“Good morning.”** with the existing `model_1250000.safetensors` checkpoint and cached vocoder. The checkpoint SHA-256 remains `670900fd14e6c458b95da6e9ed317cdb20dbaf7a1c02ac06a05475a9d32b6a38`.

The ASR and synthesis checks are separate actual executions. They do **not** constitute a single full automatic-reference render or a real multi-cue persistent-session run. Unit tests cover persistent construction order/reuse and the existing session tests cover worker ownership. These checks establish runnable code paths and non-silent output, not language fidelity, speaker similarity or naturalness. CPU generation remains slow.

Startup and ASR diagnostics reject socket operations and use offline settings. Speech generation uses offline Hugging Face settings and existing local assets. All owned diagnostic/acceptance processes and temporary job workspaces must be released before consolidated acceptance passes. Generated evidence/audio under `docs/validation` is intentionally retained.

## Tests, retained failures and measurement corrections

Added adapter tests cover deferred invocation and argument forwarding, retained Trainer export/cache, wrong-version rejection, both source-hash drift cases, ambiguous import rejection, hook cleanup and unrelated imports. Three worker tests cover reference-before-model ordering, reference failure without model loading, and two requests reusing one model. Existing F5 reference/probe/session tests are included in the final focused run.

The final focused run passed **40 tests in 12.854 s**. The final full backend run passed **907 tests in 119.668 s**, after the worker-order change. The earlier full run passed **904 tests in 136.935 s** before that change and remains historical evidence. Counts overlap and must not be added together. The discovered backend suite excludes `test_model_download.py` and `test_pipeline_dryrun.py`, which are standalone scripts, consistent with the preceding audit.

Retained unsuccessful attempts:

- The ASR-only deferred probe still timed out; its stack identified the eager training path. See `2026-10-16-f5-lazy-probe.json` and `2026-10-16-f5-lazy-startup-asr-only-stack.log`.
- The first diagnostic merged a phase timestamp into the total `seconds` field. The ASR-only receipt's approximately seven-second value is **not a valid total startup measurement**. The final diagnostic uses `source_transformed_at_seconds` separately; its 17.86-second total is the valid observation. Stack captures at 20/40 seconds from the ASR-only attempt remain available.
- The initial focused command needed explicit workspace/module/temp paths and corrected mock patch ordering. Its failed log is retained; corrected and final logs pass.
- A final speech rerun initially targeted a nonexistent `Scripts/python.exe` beneath the embedded desktop runtime; no child ran. The corrected command uses that profile's root `python.exe`.

No installed dependency source was edited to make these tests pass. The final acceptance binds current application/test/helper source hashes, the protected user-state baseline, the built frontend, the preceding engine repairs, both upstream F5 sources, the speech model and all five established isolated runtime identities. A matching identity validates that runtime's established integrity contract; it is not a claim of a new exhaustive hash inventory for every legacy runtime.

## Visual runtime: metadata-only findings

[The feasibility receipt](validation/2026-10-16-visual-runtime-feasibility.json) records official PyPI release metadata and official PyTorch CPU index/wheel metadata. No package archive was downloaded by that inspection.

| Existing engine dependency | Proposed version | Distribution finding |
| --- | --- | --- |
| GFPGAN | 1.3.8 | Pure Python wheel available; no source build required |
| BasicSR | 1.4.2 | Source archive only; helper build required |
| Facexlib | 0.3.0 | Pure Python wheel available |
| FilterPy | 1.4.5 | Source archive only; helper build required |
| TorchVision CPU | 0.29.1+cpu | Windows CPython 3.13 wheel found; declares Torch >=2.14.0, matching existing 2.14.1+cpu metadata |

Metadata compatibility is only a prerequisite. No clean visual environment, actual modern TorchVision/GFPGAN inference acceptance, exact full lock or current advisory clearance is claimed. Fresh BasicSR may need an application-owned compatibility adaptation for modern TorchVision. Existing legacy BasicSR already uses `torchvision.transforms.functional`; copying an old locally modified package would hide this risk. GFPGAN/BasicSR training-oriented `tb-nightly` dependencies must be accounted for explicitly rather than silently substituted with another distribution. RVC's old dependency conflicts and missing usable conversion checkpoint remain separate work.

## Next bounded approval: two helper builds and dependency-lock preparation

This scope requires approval under the owner's instruction to ask before adding packages/tools. **It has not been performed.**

| Helper and purpose | Official archive | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| BasicSR 1.4.2: restoration architectures/image helpers used by GFPGAN | `basicsr-1.4.2.tar.gz` | 172,524 | `b89b595a87ef964cda9913b4d99380ddb6554c965577c0c10cb7b78e31301e87` |
| FilterPy 1.4.5: filtering/tracking support used by Facexlib | `filterpy-1.4.5.zip` | 177,985 | `4f2a4d39e4ea601b9ab42b2db08b5918a9538c168cff1c6895ae26646f3d73b1` |

Total published source downloads: **350,509 bytes**, about **342 KiB**. Exact official URLs are retained in the feasibility receipt. These are required helpers for existing engines, not a new feature framework.

Approval would cover hash-verified download of these two archives; safe extraction and inspection of build/source files; source wheel builds in owned temporary staging using existing packaging tools; bounded no-install tests; source/wheel/notice review; and preparation of an exact dependency-lock/runtime proposal. Source builds execute upstream build code. BasicSR's optional native/CUDA build path must be inspected before execution. If a compiler, extra build package or new tool is needed, stop and discuss it rather than install it automatically.

This scope excludes runtime installation, downloading model files, changing defaults, installing other dependency wheels, or deleting working runtimes/models. Build staging will be removed after retaining the reviewed wheels/evidence. A later proposal must state the complete runtime's package list, size, compatibility findings and acceptance tests before asking for separate installation approval.

## Remaining release work

F5 startup is repaired for the scoped optional worker; CPU latency, full automatic-reference/persistent rendering, broader speech quality and GPU acceptance remain unapproved. Clean visual/RVC/MuseTalk runtime acceptance remains incomplete. Other release gates include broader Hindi/long/noisy/music/multi-speaker workflows, recognition accuracy and automatic Hindi/Urdu ambiguity, download/offline recovery, parallel/resource/GPU calibration, a fresh portable build and clean-machine/manual-accessibility checks. Owner application licensing and third-party/model redistribution decisions remain open. Historical successful clips and unit tests do not close those gates.
