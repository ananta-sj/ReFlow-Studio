# Optional engine dependency inspection — 9 October 2026

## Result and authorization

The selected-runtime inspection now covers generic F5 voices, MuseTalk, NudeNet, RVC, GFPGAN, Wav2Lip and local image/text classifiers in addition to the pinned Whisper Turbo/IndicTrans2/IndicF5 routes. Checks use existing installations only. No package/model/framework installation, download, model construction, weight loading, inference or provider call was performed.

Actual CPU observations passed for NudeNet, RVC, GFPGAN and Wav2Lip. Generic F5 and MuseTalk exceeded their bounded import budgets and remain **unverified**, not classified as broken installations. These outcomes do not replace the earlier passing Hindi IndicF5 GPU observation: generic F5 and the pinned Hindi engine are different routes and environments. Full optional-engine rendering and release readiness remain pending.

## Shared probe contracts

New `core/runtime_probe_contract.py` provides the single adapter/device/timeout list used by both parent and worker. The UI cannot supply arbitrary module names. Existing pinned routes retain their exact PyTorch/Transformers/F5 version requirements. General optional/core routes record their installed PyTorch version and verify import/device behavior without imposing the Hindi engine's unrelated version pins.

| Route | Devices covered by inspection | Process timeout |
| --- | --- | --- |
| Pinned Whisper Turbo / IndicTrans2 | First NVIDIA GPU | 45 s |
| IndicF5 / generic F5 / MuseTalk / RVC / GFPGAN | CPU or first NVIDIA GPU | 90 s |
| NudeNet | CPU | 45 s |
| Wav2Lip / local image or text classifier | CPU or first NVIDIA GPU | 60 s |

Unsupported inspection combinations such as MPS or CUDA 1 return unverified guidance instead of asserting that an otherwise usable engine is broken. A supported CUDA check can still fail when its selected interpreter has only CPU PyTorch; finding NVIDIA hardware elsewhere does not establish CUDA support in that particular environment.

The existing offline flags, socket-connection guard, hidden owned process, private temporary/cache paths, bounded reports, cancellation/cleanup behavior and timeout classification are retained. A passed result proves the limited smoke check only. It does not establish a full pip dependency graph, installed weights, model compatibility, resource headroom or output quality.

## Feature routing and package checks

F5 uses the existing `f5` interpreter and imports its API, torchaudio and torchcodec decoder interfaces. FFmpeg shared libraries are registered using the same existing directory as its feature worker. No F5TTS object, vocoder or reference recognizer is constructed.

MuseTalk uses its existing `musetalk` interpreter. It checks torchvision/torchaudio, Diffusers, Transformers/WhisperModel, face-alignment, librosa, OmegaConf and OpenCV, followed by device arithmetic when imports complete. It does not execute the vendored inference entry point, create a face detector or load VAE/UNet/Whisper weights.

Built-in NudeNet uses the existing `vision` interpreter when ready, otherwise the same interpreter as in-process portable execution. Its route uses CPU independently of the Dashboard device. The probe imports NumPy/OpenCV/ONNX Runtime/NudeNet, checks CPUExecutionProvider availability and performs tiny NumPy arithmetic. No NudeDetector or ONNX inference session is constructed, and detection/blur accuracy is untested.

RVC checks rvc-python, librosa and soundfile plus tiny selected-device PyTorch arithmetic. Its selected voice must be a nonempty `.pth` file, but the checkpoint's tensor/configuration contract is intentionally deferred because it loads weights. A passing runtime therefore leaves voice-file contents unverified.

GFPGAN checks its package and face-restoration helper without constructing GFPGANer or downloading parser/detector assets. Wav2Lip checks its actual vendored model/audio modules and the Haar cascade's presence. Inspection follows the current local source: its face detector is a Haar cascade, so no missing legacy face-detection API is invented as a dependency. Model weights and the cascade are not executed. Local image/text classifiers check their appropriate Transformers model and processor/tokenizer symbols without calling from_pretrained.

## Correct interpreter selection and reuse

The Dashboard's selected-setup action can now show runtime findings for enabled built-in enhancement, filtering and lip-sync fallbacks, even without a registry entry. Their checkpoint/detector contents remain unverified. API entries remain configuration-only: no credentials or endpoints are tested. Disabled stages are not probed.

New `core/python_runtime.py:inprocess_python` distinguishes packages used inside the app from separately configured worker interpreters. In portable/source mode, RVC/GFPGAN/classifier checks spawn the current app interpreter; `REFLOW_WORKER_PYTHON` cannot substitute another environment and create a misleading pass. Wav2Lip retains its actual worker-override routing. In a frozen executable, a standalone interpreter cannot establish the bundled in-process imports, so those checks return unverified instead of claiming equivalence. This does not add a frozen packaging implementation.

Within one inspection, identical adapter/interpreter/device checks are reused across voices. Each voice still gets its own artifact/selection checks and an independent report copy. There is no cross-request cache: changing settings/runtime or asking again starts a new inspection. This reduces repeated heavy imports without retaining stale readiness or weakening voice validation.

## Actual installed observations

`dev/verify_optional_engine_readiness.py` records CPU-only dependency observations from existing interpreters and writes progress after each route. The retained run used the current portable interpreter for its core routes; no worker override changed the observed environment. Result: `validation/2026-10-09-optional-engines-installed.json` and matching log.

| Route | Observation | Elapsed time | Recorded environment |
| --- | --- | --- | --- |
| NudeNet | Passed | 1.016 s | NumPy 1.26.4, OpenCV 4.10.0, ONNX Runtime 1.20.1, NudeNet 3.4.1 |
| Generic F5 | Unverified timeout | 90.141 s | Incomplete at F5 API import |
| MuseTalk | Unverified timeout | 90.343 s | Incomplete at OpenCV import after earlier dependencies |
| RVC | Passed | 22.234 s | Core PyTorch 2.7.1+cpu |
| GFPGAN | Passed | 23.360 s | Core PyTorch 2.7.1+cpu |
| Wav2Lip | Passed | 13.500 s | Core PyTorch 2.7.1+cpu |

Saved registry/settings and the sources captured by that diagnostic remained unchanged during the run. Interpreter-selection/cache refinements were added afterwards and tested separately; the actual probe worker/contract/parent sources remain the versions used for those observations. The original receipt is preserved as a historical observation rather than relabeled as a complete all-passed run. No models or generated user media were changed.

## Code and validation

Production changes: shared runtime-probe contract; parent/worker optional routes and imports; selected/built-in engine routing, safe unsupported-device outcomes and within-request reuse in `engine_readiness.py`; explicit in-process interpreter helper; Dashboard timeout wording. Diagnostic scripts record actual existing CPU environments. The backend runner adds a distinct `optional-readiness` label and includes the new contract/interpreter source hashes.

Focused checks initially passed 29 tests in 1.296 seconds. After interpreter/cache refinements, **32 tests passed in 1.149 seconds**. Logs: `validation/2026-10-09-optional-readiness-focused.log` and `-focused-final.log`. Coverage includes shared route/device budgets, no API calls, optional versus core interpreter selection, NudeNet CPU routing, no RVC checkpoint contract load, unsupported-device classification, forced MuseTalk selection, reused voice runtime checks, independent report copies and frozen/worker-override mismatches. Previous bounded transport/cleanup tests remain included.

Frontend production build and source lint passed with existing warnings; logs are `validation/2026-10-09-optional-readiness-frontend-build.log` and `-frontend-lint.log`. Browser interaction was not newly exercised. The final backend run passed **726 tests across 41 modules in 111.922 seconds**, with zero failures or errors. Its receipt/log is `validation/2026-10-09-optional-readiness-backend-complete.json/.log`.

Final evidence binding is recorded in `validation/2026-10-09-optional-readiness-evidence-integrity.json`: all tested production source hashes still match, saved registry/settings remained unchanged during the suite, and the accepted editorial video remains unchanged with SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. These assertions establish preservation and regression results, not new model-quality or end-to-end release validation.

## Remaining work

Generic F5/MuseTalk need further import-time investigation before their smoke checks can be called complete. Their existing ready profile labels are not rewritten from a timeout alone. No new dependency installation was attempted or requested. CUDA checks for these optional/core environments, classifier live model loading, actual detector/voice/lip-sync rendering, asset recovery behavior on independent jobs and wider platform/device verification remain open. Built-in checkpoint recovery and background separation are still not fully verified by this dependency report. The bounded Windows publication repair remains in place; the original historical lock holder remains unidentified. Release remains pending.
