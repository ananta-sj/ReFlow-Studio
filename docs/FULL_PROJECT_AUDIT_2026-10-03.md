# Reflow Studio — full project audit, 2026-10-03

## Outcome and iteration scope

The project has a working, tested set of orchestration and failure-handling
components, but it is not yet a verified portable release across all advertised
features or operating systems. Passing the backend suite does not establish
that the installed AI engines can perform a complete render.

This iteration expanded the requested cloud/F5 inspection into a project-wide
audit. **No implementation was repaired in this iteration.** Only this report,
source/runtime inventories, safe reproduction results, a storage snapshot, and
validation logs were created. No dependency installation, model download,
factory reset, application cancellation, credential access, commit, push, or
release build was performed. Temporary reproduction files were self-cleaned.

The previous approved iteration implemented XTTS speech-language safeguards;
its changes and 15 added regressions are described in
[the speech-language report](SPEECH_LANGUAGE_BACKEND_REPORT_2026-10-03.md).
Those safeguards are part of the baseline reviewed here, not new audit fixes.

This report contains **40 actionable findings**, including defects, design
risks, incomplete integrations, and release requirements. Findings are not all
equally severe, and static risks are not presented as observed crashes. It is
not possible to establish that every possible issue has been found from a source
audit and simulated tests. The feature matrix and verification backlog explicitly
record the remaining work required to make stronger claims.

## Evidence, confidence, and baseline

The local workspace is `C:\Projects\Reflow Studio`. Git HEAD is
`d3408a587f734b99ea6e30cac3c503804677ea98`; substantial uncommitted changes
predate this audit. No Git remote is configured. Consequently, the public
repository and this local working tree are separate evidence sources, not
assumed identical revisions.

The public [ReFlow-Studio repository](https://github.com/ananta-sj/ReFlow-Studio)
still describes an older PyQt entry point, portable/offline operation, and batch
processing. The local application uses `main.py`, pywebview, and React. Public
documentation describes intended features; local source determines this audit's
implementation findings. No upstream issues or PRs were filed.

Evidence files:

| Artifact | Contents |
| --- | --- |
| `audit/2026-10-03/SOURCE_INVENTORY.json` | Paths, sizes, SHA-256 hashes, Python function names/line numbers for 286 project and vendored source/config files |
| `audit/2026-10-03/RUNTIME_METADATA.json` | Actual embedded interpreter and installed distribution versions; null means no distribution metadata found |
| `audit/2026-10-03/PIP_CHECK.txt` | Dependency inconsistencies and missing metadata; command exit code 1 |
| `audit/2026-10-03/SAFE_REPRODUCTIONS.json` | Mocked-network downloader failures and in-memory cross-stage registry activation |
| `audit/2026-10-03/SIZE_SNAPSHOT.json` | Logical bytes by top-level folder; disk allocation/compressed release size not measured |
| `validation/2026-10-03-full-audit-checks.log` | 242 passing backend checks in 17.526 seconds, exit code 0 |

All 128 Python files under core, bridge, dev, packaging, plus root entry/config
files parsed without syntax errors. This includes vendored inference source.
Parsing is not type checking, import validation, or branch execution. Frontend
files, including chart/UI components, were inventoried; critical feature wiring
was traced through pages, hooks, bridge methods, resolvers, and pipelines. Every
chart animation branch and every third-party training path was not manually
executed or individually certified.

Confidence labels used below:

- **Reproduced:** safely demonstrated in this audit without real service calls.
- **Confirmed:** directly established by current source or runtime metadata.
- **Risk:** implementation permits a failure; the failure was not induced here.
- **Release gap:** capability or acceptance evidence is missing.

P1 means a broken feature, misleading success, potential data/credential loss,
or a release blocker for the relevant feature. P2 means a significant limitation
or maintainability/reliability issue. Priority reflects impact, not the amount of
code required. No claim of an actively exploited vulnerability is made.

## Feature and pipeline coverage

| Feature | Actual implementation / audit result | Remaining verification |
| --- | --- | --- |
| Desktop startup | `main.py` opens built React UI through a file URI and exposes PythonBridge; Windows launcher prefers embedded Python | Clean-machine GUI startup, WebView runtime prerequisites, permissions and relocation |
| Video dubbing | Extract → optional Demucs → Whisper → optional translation/moderation → speech/voice → optional visual stages → merge | Real model render with stream/duration/content checks |
| Video with lip sync | Same video pipeline with lip-sync enabled | Wav2Lip/MuseTalk failure contracts and actual synchronization |
| Audio dubbing | Separation/transcription/translation/speech/mix → staged WAV | Source-language and decode checks pass in simulated tests; real inference and stem implementation missing |
| Subtitle translation | UTF-8/BOM SRT → translation → staged SRT; no speech checks | Reject partial malformed files; multilingual quality and formatting preservation |
| Local transcription | Worker process, faster-whisper, CPU/int8, metadata envelope | Real long/short/noisy/multilingual audio; timeout/stop behavior |
| Cloud transcription | OpenAI-shaped or custom upload; normalization preserves optional language metadata | Real endpoint schema, confidence availability, configuration forwarding |
| Ollama translation | Requested model matching, bounded HTTP, explicit generation failures | Actual installed-model quality and long-text behavior |
| M2M100 fallback | Exact target/source maps; incompatible instructions rejected before load | Actual model availability, translation quality, offline recovery |
| NLLB | Local checkpoint/tokenizer, exact source/target vocabulary checks | Checkpoint architecture screening and real inference |
| AirLLM | Layer-offloaded prompt generation, optional compression | Package absent; storage footprint, CPU/GPU compatibility and latency |
| Cloud translation | Named chat/custom adapters; source/instructions validated; translation request metadata forwarded | Actual service models and templates; UI editor for configuration |
| XTTS | Lazy handler; config-backed coverage, Chinese mapping, concrete source speech; playable output checks | Installed legacy TTS dependency conflicts; real inference and reference quality |
| RVC | Base speech → checked preprocessing → selected checkpoint → playable output | Installation name/path binding, architecture, index selection and concurrent model mutation |
| F5 | Direct text/reference generation; bypasses base XTTS | Package absent; Marketplace install route fails for repository directories; checkpoint/language selection |
| Cloud speech/voice | Text-to-audio and audio-to-audio adapters | Voice IDs, request settings and capabilities incompletely connected |
| Background preservation | Demucs htdemucs vocals/background + dynamic ducking | Separation fail propagation and quality; background may retain original speech |
| Face enhancement | GFPGAN frame loop with 1x/2x/4x options | Strict initialization/output contract and resolution-consistent failure behavior |
| Visual filtering | NudeNet boxes or NSFW classifier whole-frame blur | NudeNet absent; fail-open behavior, classifier label handling and video writer checks |
| Profanity filtering | Activated provider runs after translation | Source-mode bypass, fail-open adapters, label interpretation, output validation |
| Multi-cast | Duplicated voice nodes create round-robin segment assignments | Not speaker diarization; merged segments can change actor assignment |
| Segment parallelism | ThreadPoolExecutor; GPU inference lock; CPU inference unguarded | Shared engine initialization/model/config concurrency, memory pressure and measured benefit |
| Batch queue | Backend queue exists, with sequential continuation and terminal-state tests | Frontend asset queue is separate and does not submit backend batches |
| Stop/pause/recovery | Stop flag plus descendant process kill; pause between queued jobs; interrupted job restart | In-process cancellation, cleanup race, no checkpoints/persistent batch queue |
| Node editor | Fixed backbone graph, stage toggles, voice duplication, visual positions | Source parameter omitted; subtitles node and positions not execution contracts |
| Model Marketplace/search | Stage catalog, registry, recommendations, download metrics and heuristic detection | Architecture verification, safe installation, IDs, download cancellation and settings UI |
| Hardware/ETA/benchmark | CPU/CUDA/MPS discovery, telemetry, heuristic stage cost, synthetic benchmark | Per-stage device accuracy, actual timing calibration, benchmark under render load |
| Settings/onboarding | JSON backend defaults; browser preferences/render config; guided initial selections | Atomic persistence, validation, recovery and propagation of defaults |
| Logs/theme/tour/tray | Push-event logs, theme/accent, experience gates, walkthrough, pystray | Real GUI accessibility, tray lifecycle, navigation during jobs, log privacy |
| Packaging/CI | Three-OS PyInstaller workflow and full asset-folder copies | Frozen subprocess execution, optional source/data inclusion, fresh-install tests, signatures and size policy |

## Actual portable runtime

The active Windows embedded interpreter is **CPython 3.10.11**. Runtime metadata
reports **TTS 0.22.0**, Torch **2.1.2+cu118**, torchaudio **2.1.2+cu118**,
torchvision **0.16.2+cu118**, NumPy **1.23.5**, SciPy **1.10.1**, transformers
**4.36.2**, faster-whisper **1.2.1**, and rvc-python **0.1.5**.

No installed distribution metadata was found for coqui-tts, f5-tts, NudeNet,
AirLLM, diffusers, face-alignment, or torchcodec. The F5 and NudeNet package
directories are also absent. Absence of coqui-tts metadata does not mean the
`TTS` import is absent: legacy TTS 0.22.0 is present. Nor does absent torchcodec
alone prove this older Torch/TTS combination needs it; that dependency must be
chosen with the supported version set.

The dependency check found missing spacy-legacy/spacy-loggers and five declared
TTS dependencies (aiohttp, encodec, g2pkk, umap-learn, unidecode), plus incompatible
NumPy/SciPy, fairseq/hydra/omegaconf, rvc-python/omegaconf and thinc/blis requirements.
It also warns that pip's distribution METADATA is missing. These are environment
inconsistencies; they do not prove every dependency is exercised by every render.
Mocked engine tests cannot rule out resulting real inference failures.

`requirements.txt` requests the maintained coqui fork and largely unpinned
dependencies. `portable_requirements.txt` requests Torch 2.7.1 and includes
opencv-python while the main manifest requests headless OpenCV. Neither
describes the actual embedded installation as a reproducible lock.

## Findings: lifecycle, state and concurrency

### A01 — P1, Risk: Stop races with in-process work and cleanup

Evidence: `bridge/api.py::stop_render`, `_run_render_inner`,
`core/janitor.py::sweep`, `core/pipeline.py::_dub_all_segments`.
Stop sets a flag, kills selected child processes and deletes the shared temp
folder immediately. In-process XTTS/RVC/F5, image loops and HTTP calls do not
receive a cancellation token. The bridge checks the flag only when a generator
yields. Workers can continue touching deleted files, and the UI reports stopped
before those workers necessarily exit. Proposed fix: job-owned cancellation and
temporary directories; wait for owned workers before cleanup. Acceptance:
cancel each phase and parallel mode; no post-stop writes, success events, or
cleanup of another job; restarting remains blocked until the old worker exits.

### A02 — P1, Risk: CPU segment workers share mutable speech engines

Evidence: `core/pipeline.py::_dub_all_segments`,
`core/providers/tts/xtts_local.py::synthesize`, `core/rvc/rvc_handler.py::infer`.
Only GPU inference is locked. CPU workers share a lazy handler, per-actor
providers and RVC configuration/model mutation. The actor-resolution lock does
not serialize inference or lazy XTTS construction. Multiple constructors/model
loads or wrong-model use are possible. Fix: define per-engine synchronization or
isolated workers before advertising safe CPU speedups. Acceptance: concurrent
real engine calls cannot duplicate initialization, cross voices or corrupt config;
benchmark throughput before raising worker defaults.

### A03 — P1, Confirmed: Destructive operations have no active-job guard

Evidence: `bridge/api.py::factory_reset`, `remove_model`,
`frontend/src/pages/Assets.tsx::handleFactoryReset`.
Factory reset and model removal can run while a renderer/download is active.
The reset deletes outputs and temp; model removal can delete files in use.
Fix: synchronize with lifecycle, block or explicitly stop affected work before
destruction and expose a concrete affected-file list. Acceptance: reset/remove
during every job phase leaves no inconsistent registry, output or live worker.
This audit did not invoke either operation.

### A04 — P1, Confirmed: Frontend and backend queues are disconnected

Evidence: `frontend/src/lib/use-queue.ts`, `pages/Assets.tsx`, `lib/api.ts`,
`bridge/api.py::add_queue_item`, `core/queue_manager.py`.
Assets stores a browser-memory array; Dashboard/Nodes render one head item.
Frontend API wrappers do not submit those items to QueueManager. Backend
auto-advance tests therefore do not establish end-user batch processing.
Fix: one queue authority and explicit batch start/pause/status wiring. Acceptance:
three UI-added files run once in order, a failed file advances appropriately,
and removal/pause/status apply to the same jobs.

### A05 — P1, Confirmed: Render status is lost on page remount

Evidence: `frontend/src/App.tsx` conditional pages, `lib/use-render.ts`,
`lib/events.ts`. Each mounted hook starts from INITIAL; events are not retained
or replayed. Navigating away during work and returning can hide running state,
source feedback and output; controls may look idle while the backend is busy.
Fix: persistent shared job state plus backend snapshot on subscription.
Acceptance: navigation, experience-level changes and resume retain correct state.

### A06 — P2, Confirmed: Rejected starts still consume selected input

Evidence: `pages/Dashboard.tsx::handleStart`, `pages/Nodes.tsx::handleStart`,
`lib/use-render.ts::start`. The hook consumes a backend rejection internally and
returns no success indicator; callers still pop the queue or clear audio input.
Fix: return an accepted-job result and remove input only on acceptance.
Acceptance: overlapping start rejection retains the input and queue order.

### A07 — P1, Confirmed: Registry/settings/state persistence is non-atomic

Evidence: `core/model_registry.py::_save`, `settings.py::_save`,
`render_state.py::mark_started`, `hardware_profile.py::capture`.
Whole JSON files are overwritten directly, and model-download threads/UI calls
can mutate the shared registry without a lock. Crash/interleaved writes can
truncate files or lose updates. Loaders also do not validate complete shapes.
Fix: locking, schema validation and atomic replacement; preserve corrupt files
for recovery. Acceptance: concurrent updates and interrupted writes preserve a
valid prior or new state. No real registry was modified by audit probes.

### A08 — P2, Reproduced: Cross-stage active model selection is accepted

Evidence: `ModelRegistry.set_active`; SAFE_REPRODUCTIONS.json. An in-memory
TTS entry was successfully assigned as active translation. Existence is checked,
but stage compatibility is not. Fix: verify stage, kind, availability and
adapter compatibility before activation. Acceptance: wrong-stage assignments
fail without persistence; legitimate stage selection still works.

## Findings: output, speech and visual correctness

### A09 — P1, Confirmed: Video stem export raises after publishing output

Evidence: `core/pipeline.py::process_video_gen` export block. `temp_bg` and
`temp_vocals` are read but never defined. Enabling export_stems raises NameError
after final merge, so a render can publish a video then be reported failed.
Fix: export the actual separation/mix artifacts through validated staging.
Acceptance: background on/off stem jobs produce documented playable stems,
with consistent success/failure and preservation of existing outputs.

### A10 — P2, Confirmed: Audio export parameters are accepted but unused

Evidence: `process_audio_dub_gen` accepts `export_stems` and `sub_style`;
its body implements neither. Dashboard's shared payload builder does not expose
stem/style settings either. Fix: implement applicable audio exports or reject
unsupported options; avoid UI promises for disconnected parameters.
Acceptance: each accepted option changes an observable artifact or fails early.

### A11 — P1, Confirmed: Enabled lip sync may silently disappear

Evidence: `process_video_gen` result_video conditional; `LipSyncHandler.execute`.
The local handler returns None on errors and the pipeline proceeds with the
original visuals. A requested lip-sync render can report complete without lip
sync. Child exit status is not required for success. Fix: fail enabled stages
or obtain an explicit user-selected degraded mode. Acceptance: nonzero exit,
timeout and invalid media produce a clear failed lip-sync stage.

### A12 — P1, Risk: MuseTalk can accept a stale result

Evidence: `core/providers/lipsync/musetalk_local.py::execute`. Fixed task/config
and result names are reused; the previous result is not cleared before execution,
and success uses existence/size without checking returncode. A failed process
can leave a previous result accepted. Fix: per-job output directories, checked
exit code and decoded media validation. Acceptance: seeded stale result plus
failed subprocess never returns success or overwrites a good destination.

### A13 — P1, Confirmed: Enhancer failures can masquerade as completion

Evidence: `core/enhancer.py`. Missing/failed GFPGAN initialization returns the
input. Frame errors write original-sized frames into a writer sized for upscale;
outer failures are swallowed and any existing output is treated as complete.
VideoCapture/Writer open state and complete frame count are not checked.
Fix: strict stage contract, dimension-consistent fallback only when explicit,
staged output validation. Acceptance: 1x/2x/4x errors never silently truncate
video or claim enhancement completed.

### A14 — P1, Confirmed: Visual filtering fails open

Evidence: `core/vision/vision_handler.py`, `providers/filter/nudenet_local.py`.
Initialization failures disable detection; frame detection exceptions return
no boxes. Since NudeNet is absent, the default route can produce an unchanged
video while filtering was requested. API call/label compatibility also needs
validation against an approved installed version. Fix: surface unavailability
and frame errors, validate writer/output and define an explicit failure policy.
Acceptance: unavailable or failing detector cannot be presented as filtered media.

### A15 — P1, Confirmed: Classifier label matching is ambiguous

Evidence: `profanity_filter/classifier_local.py` searches for substring `toxic`,
and `filter/vision_classifier_local.py` searches for `nsfw`, taking the first
match. Labels such as `non-toxic` and `not_nsfw` also match those substrings.
Fix: exact normalized label mappings with declared positive class and ambiguity
rejection. Acceptance: reversed label order and negative labels cannot invert
moderation; unsupported multi-class schemas fail clearly.

### A16 — P1, Confirmed: Profanity failures and output validation lag translation

Evidence: `profanity_filter/ollama_local.py`, `profanity_filter/cloud_rest.py`,
`pipeline.py::_translate_line`. Ollama failure/empty output returns the original
line; custom cloud moderation can fall back to input. The pipeline does not apply
strict string/nonblank validation to the moderation result. Fixed classifier
instructions are accepted but ignored; a removed-line English placeholder may
be spoken as target-language dialogue. Fix: explicit contract and failure policy,
language-appropriate removal behavior, and instruction capability checks.
Acceptance: broken/empty/malformed moderation cannot silently bypass requested
filtering or create later unexplained speech failures.

### A17 — P1, Confirmed: Keep-source jobs skip profanity filtering

Evidence: all translation loops invoke filtering through `_translate_line` only
when target_lang != source. Activating moderation does not cause a separate pass
in keep-source mode. Fix: independent transcript moderation stage with clear
order and language context. Acceptance: identical moderation behavior for source
and translated jobs, including subtitle templates if that feature is promised.

### A18 — P1, Confirmed: Separation hides its own failures

Evidence: `core/audio_separator.py::separate`, video/audio separation callers.
Timeout, child failure or missing artifacts returns (None, None), contradicting
the comment that errors reach the bridge. Callers then choose a missing
transcription source when background preservation is enabled. Stems use shared
names and are not decoded before use. Fix: checked separation artifacts and
contextual errors; fallback only when explicitly selected. Acceptance: a failed
separator reports that stage and does not proceed with None or stale stems.

### A19 — P2, Confirmed: Device selection is not a per-stage guarantee

Evidence: Whisper forces CPU; Wav2Lip auto-selects CUDA/CPU; MuseTalk provider
stores device but does not pass gpu_id/device, and vendored inference auto-selects
CUDA; NLLB resolver does not pass the selected compute device; classifier routes
fall back to CPU for non-CUDA. UI/ETA device selection can imply a broader effect
than it has. Fix: stage-specific effective device report and supported overrides.
Acceptance: CPU/CUDA-index/MPS requests produce documented actual routing and
estimates based on those routes, with visible unsupported choices.

### A20 — P2, Confirmed: SRT parser silently omits malformed cues

Evidence: `core/srt_utils.py::parse_srt`. Regex finds valid-looking blocks and
does not reject unmatched content. A partly malformed subtitle file can yield
a subset and be exported as a successful translation; multiline text is flattened.
Fix: strict whole-file cue parsing or an explicit partial-import report.
Acceptance: one bad cue cannot disappear without a diagnostic; define formatting
preservation for multiline captions and tags.

### A21 — P2, Confirmed: Output naming can overwrite unrelated jobs

Evidence: pipeline filenames derive from input basename and target only.
Inputs in different directories with the same name/target publish to the same
destination. Atomic replacement protects against broken partial output but still
replaces a valid previous job. Fix: explicit overwrite policy or unique job IDs.
Acceptance: duplicate basenames in a batch cannot silently erase earlier results.

## Findings: provider configuration and Marketplace

### A22 — P1, Confirmed: Cloud request settings are discarded

Evidence: `core/providers/resolve.py`, bridge add_cloud/add_local_api methods.
Translation forwards meta.translation_request; STT, TTS, voice, enhancement,
filtering, lipsync and profanity resolvers do not forward their adapters' extra
configuration. TTS voice is also omitted. UI add forms expose base URL/preset/key
but not the full request contract. Async video settings therefore remain unused
through normal resolver flow. Fix: validated per-stage configuration schema and
consistent registry/UI/resolver forwarding. Acceptance: custom paths, headers,
body/model/voice and async fields survive add/save/restart/resolve exactly.

### A23 — P1, Confirmed: Cloud voice identity is confused with display name

Evidence: `_dub_segment` passes actor display_name as model_name;
`voice/cloud_rest.py::_elevenlabs_sts_request` uses it as voice_id. TTS ElevenLabs
needs voice_id, but resolver supplies neither voice nor extras. Display labels
are not service IDs. Fix: distinct immutable entry ID, display name and vendor
voice ID; bind selected actor to its actual service configuration.
Acceptance: a friendly display name and different vendor ID render correctly.

### A24 — P1, Confirmed: F5 Marketplace installation follows RVC installation

Evidence: recommended F5 entry is a voice local_file repository; bridge
`_run_local_download` sends every voice download to
`install_downloaded_voice_model`, which accepts only .pth or .zip, not a Hugging
Face repository directory. F5 provider subsequently loads package defaults and
ignores the connected local path. Fix: F5-specific setup/checkpoint binding,
approved package availability and explicit language capabilities. Acceptance:
connecting F5 reaches a usable installed state and uses the selected checkpoint
without downloading it twice. No package addition is approved by this audit.

### A25 — P1, Confirmed: RVC display name may not match installed checkpoint

Evidence: voice installer returns filename-derived _name, but bridge ignores it;
RVC infer builds weights/<actor display name>.pth and ignores registry.local_path.
A custom name can select a nonexistent file. Archive installs may move several
weights but register only the last one; indexes are sorted by their own filename
rather than an explicit voice association. Fix: bind voice entries to checkpoint
and index paths, inspect architecture rather than force all models to V2.
Acceptance: renamed voices, multi-weight archives, and V1/V2/index combinations
either work as declared or reject clearly before inference.

### A26 — P1, Reproduced: Marketplace downloader accepts invalid artifacts

Evidence: `core/downloader.py::download_with_progress`; safe reproductions.
HTML bytes (24 written, 100 declared) and a short binary (3 written, 100 declared)
both produced phase done. Writes go directly to destination; no nonempty/content
type/length/architecture checks. This is distinct from the stricter model_assets
helper repaired earlier. Fix: stage-aware verified download/install with staging,
atomic publication and integrity policy. Acceptance: HTML, truncated, empty and
wrong-architecture inputs never become installed models or erase valid files.

### A27 — P2, Risk: Removing a Hugging Face download does not stop its worker

Evidence: `_download_hf_snapshot` creates a background thread; bridge removal
breaks out of the progress generator, then can delete the destination. The thread
has no cancellation handle and may continue writing after registry removal.
Fix: download lifecycle ownership and coordinated cancellation/join/cleanup.
Acceptance: removal stops actual transfer, creates no later files/events, and
does not leave uncontrolled cache growth.

### A28 — P1, Risk: Model deletion trusts stored filesystem paths

Evidence: `bridge/api.py::remove_model`. Existing local_path is recursively
deleted without verifying ownership/containment in managed model storage.
Registry loading accepts externally edited paths; this makes a malformed or
imported entry potentially destructive. Archive installation also replaces
same-named weights, and removal may leave index/extra weights behind.
Fix: explicit ownership records, canonical-path containment, reference counting
and verified deletion plans. Acceptance: external/custom files and shared models
are preserved; only owned unused files are removed. No destructive probe run.

### A29 — P1, Confirmed: Local model selection does not ensure adapter compatibility

Evidence: resolvers treat local translation as NLLB, local TTS as XTTS,
local lip sync as MuseTalk; enhancer uses bundled GFPGAN regardless of active
local path; visual filters only honor one classifier preset. New XTTS preflight
narrows its own error, but generic Marketplace labels imply wider interchangeability.
Fix: adapter/architecture declarations and validation before install/activate;
never silently substitute a missing selected model with a default.
Acceptance: each supported model uses its registered files and unsupported
architectures fail before a large download/load or unrelated default render.

### A30 — P1, Risk: Async cloud URLs receive stored authentication headers

Evidence: enhancement/filter/lipsync cloud adapters send their original headers
to server-provided status_url and result_url. There is no origin policy; a URL
on another host receives the API key explicitly. Normal resolver flow currently
does not enable async settings, but direct/configured adapters expose the risk.
Fix: validate schemes/origins; separate service authentication from signed asset
downloads. Acceptance: foreign-origin response URLs never receive credentials;
valid same-origin polling and signed downloads still function. No secret read or
network exploit was performed.

## Findings: runtime, delivery and missing release evidence

### A31 — P1, Confirmed: Advertised optional engines are absent

Evidence: RUNTIME_METADATA.json and package directory inspection. F5, NudeNet,
AirLLM, diffusers and face-alignment are unavailable in the embedded environment.
Enabling these features either fails late or takes a silent fallback in the
visual-filter route. Fix: feature dependency manifest and preflight availability
report; agree whether optional engines ship or install on demand.
Acceptance: every advertised selectable feature is available or clearly marked
unavailable before a job starts. Installation requires a separate user approval.

### A32 — P1, Confirmed: Dependency environment does not satisfy installed requirements

Evidence: PIP_CHECK.txt, exit 1. Missing legacy TTS dependencies and incompatible
NumPy/SciPy/fairseq/rvc-python/spacy-related requirements are present; pip metadata
is damaged. Fix: build a tested compatible environment from a reviewed lock,
rather than patching versions one by one in the production folder.
Acceptance: dependency checks and real imports/inference pass in a freshly
assembled runtime; old environment remains recoverable during migration.

### A33 — P1, Confirmed: Dependency manifests disagree and omit RVC runtime

Evidence: both requirements files versus actual metadata. Main manifest asks for
coqui-tts; portable manifest pins a different Torch set and OpenCV flavor.
Neither declares rvc-python despite the handler's required import. Main manifest
also omits explicit GFPGAN/basicsr/realesrgan dependencies relied on by startup/
enhancement. Fix: one supported lock/profile system with feature ownership and
OS-specific constraints. Acceptance: clean install supplies the approved feature
set without relying on the mutable self-healing guard.

### A34 — P1, Confirmed: Startup integrity can install silently and claim success

Evidence: `IntegrityDoctor.check_libraries/install_package`, bridge integrity
method. Missing imports invoke pip; install exceptions are printed and swallowed;
no successful re-import is required, and the bridge can return ok. find_spec checks
presence, not loadability. STT/TTS/F5 and other feature dependencies are not fully
covered. Fix: separate read-only diagnosis from approved repair, validate actual
imports and return structured unmet requirements. Acceptance: an unavailable
engine is never labeled verified; boot does not mutate dependencies unexpectedly.

### A35 — P1, Confirmed: Frozen build subprocess contracts are incompatible

Evidence: PyInstaller entry is main.py; STT, Demucs, Wav2Lip and MuseTalk execute
sys.executable with Python script/-m arguments. In a frozen build sys.executable
is the application executable, whose entry point has no worker CLI dispatch.
Those calls cannot be assumed to behave as an interpreter and can start another
GUI. Wav2Lip/MuseTalk source/data and runtime asset locations are not completely
assembled by build_dist/spec; source-relative paths can differ from executable
asset paths. Fix: choose an approved portable interpreter strategy or explicit
frozen-worker entry points and data manifest. Acceptance: actual packaged builds
execute every worker once, resolve assets after relocation, and never spawn
unintended app instances. No executable build was attempted in this audit.

### A36 — P1, Confirmed: CI builds artifacts without release acceptance checks

Evidence: `.github/workflows/build.yml`. Uses npm install, floating Python
dependencies and OS runners; no backend tests, dependency check, packaged smoke
test, actual feature render, size budget or OS GUI acceptance. Windows fresh
checkout does not obtain ignored FFmpeg binaries/shared libraries; packaging
copies folders only if they already exist. Linux webview system dependencies
and macOS bundle/signing acceptance are not established. Fix: reproducible
portable-build pipeline with explicit assets and approval-controlled publishing.
Acceptance: three clean runners validate the approved feature matrix and release
contents before artifact promotion. External tooling choices need review first.

### A37 — P1, Confirmed: Nodes omits source language; some graph controls are cosmetic

Evidence: `frontend/src/pages/Nodes.tsx` builds RenderParams without
source_language, while Dashboard uses the shared builder. Manual source choice
is lost for jobs started from Nodes. The subtitles node has no mapping to the
pipeline's always-generated subtitles, and dragged positions are not persisted
as an execution graph. Fixed graph edges do not schedule a general DAG.
Fix: use a common job contract and define which nodes actually control behavior.
Acceptance: Dashboard/Nodes submit equal language settings and each enabled
control has a documented effect; cosmetic layout is labeled appropriately.

### A38 — P2, Confirmed: Offline and portable instructions overstate current guarantees

Evidence: README.txt, public README, launchers and model_assets. Public docs
refer to the old PyQt entry point. Local README points to a removed VC installer,
calls M2M100 built-in/offline although its weights are recovered separately, and
instructs `sh LAUNCH_REFLOW.sh` despite Bash-specific source/BASH_SOURCE syntax.
REFLOW_OFFLINE controls model_assets only, not Whisper/HF/AirLLM/cloud paths;
startup guard may install packages. The workspace remains several GB, not a
500 MB self-contained runtime. Fix: regenerate instructions from verified release
profiles; define offline mode across all downloads and service calls.
Acceptance: documented commands/files exist, fresh startup behavior matches the
guide, and offline missing assets fail locally without attempted network access.

### A39 — P1, External constraint: Commercial model permissions are unresolved

Wav2Lip's original open-source release restricts commercial use; XTTS-v2's
published CPML restricts model/output use to non-commercial purposes. These
constraints require a product decision before commercial distribution/use of
those artifacts. This audit does not determine whether separate permissions
have already been obtained or select replacements. Maintain per-model provenance,
license/version records and distribution notices; obtain appropriate permissions
or approve a different model before a business release. Sources checked in this
iteration: [Wav2Lip upstream](https://github.com/Rudrabha/Wav2Lip),
[XTTS-v2 published license](https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt).

### A40 — P2, Release gap: End-to-end, resource and GUI evidence is incomplete

There is no current real-engine/fresh-machine/three-OS acceptance result in this
iteration. Frontend dependencies remain cleared, so build/lint/26 source-language
UI checks from the earlier UI iteration were not rerun here. No live native GUI
or browser was available for interaction verification. Long media is decoded
into memory; parallelism queues all segment futures and retains clips before
mixing. No measured limits for input duration, RAM, worker count or disk growth
are established. Fix: small approved acceptance dataset and supported hardware
matrix, then staged real-engine/GUI/resource tests. Acceptance: reproducible
outputs and clear limits, rather than inferring reliability from mocks or ETA.

## What is already useful and should be preserved

The earlier work provides strong foundations: checked FFmpeg commands with
bounded diagnostics; staged final outputs; playable speech validation; explicit
XTTS/RVC/F5 failure boundaries; fixed translation/source mappings; preserved
transcription metadata; source feedback and compatibility guards; sequential
backend queue continuation; and a growing reusable regression suite. The audit
does not recommend rewriting these to introduce a new framework.

Credentials are held through the OS keyring with references in registry files;
this audit did not read credential values. Main UI content is local and JSON
push-event values are serialized, rather than interpolating raw provider text
as executable code. These good boundaries should remain during fixes.

Multi-cast is currently round-robin after segment merging, not speaker-aware
casting. Parallel workers are segment scheduling, not simultaneous GPU model
inference. Hardware ETA is heuristic, not a guaranteed completion time. These
are valid design choices if represented accurately and tested within their limits.

## Unnecessary weight and duplication — candidates, not deletions

The original 500 MB goal is still a delivery-profile decision. The current
runtime includes a large scientific/AI environment; tightening text/config files
will not materially solve it. The storage snapshot distinguishes the embedded
runtime, developer `.venv`, Git history, FFmpeg, media and models. Logical size
does not establish download archive size or extraction requirements.

Candidates for an eventual release exclusion list: developer `.venv`, `.git`,
test-only fixtures/reports, compiler/download caches, sample/rendered media,
vendored training/evaluation assets not required for inference, and packages
owned only by optional engines. The many frontend chart components should be
checked for imports and actual bundle contribution before removal; source file
count alone is not shipped bundle size. Do not remove FFmpeg shared libraries
or transitive AI dependencies based only on apparent duplication.

Two dependency files, legacy executable packaging alongside portable setup,
multiple downloader implementations, duplicated Dashboard/Nodes parameter
construction, broad wildcard warning suppression and obsolete model/provider
comments increase maintenance cost. Consolidate only after behavior contracts
and the supported release profile are agreed. No cleanup was performed here.

## Proposed repair order — each batch needs approval

1. **Lifecycle and user-data protection:** A01–A08, especially stop/cleanup,
   reset/remove guards, shared render state and queue authority. Decide persistent
   batches and cancellation semantics before implementation.
2. **Truthful stage results:** A09–A18. Fix stem export, enabled-stage failures,
   stale visual outputs, separation and moderation. Agree explicit fallback policy.
3. **Model and service contracts:** A22–A30, A37. Bind IDs/paths/configurations,
   validate architecture/downloads, correct F5 setup and credential origin policy.
4. **Supported runtime/release profile:** A31–A36, A38–A39. Review dependency
   choices, portability/size/offline expectations and model permissions before
   installing or replacing engines.
5. **Acceptance and quality:** A19–A21, A40. Real models, timing/quality, GUI,
   accessibility, long-media resource limits and OS release validation.

These are sequencing recommendations, not authorization to execute repairs.
Some dependencies overlap: queue/UI wiring and runtime availability may need
smaller separately reviewable batches.

## Verification backlog for the next iterations

Use synthetic disposable inputs first; preserve user samples and outputs. Cover
video/audio/subtitle routes, background on/off, each supported generator/voice,
all visual stages individually then combined, source Auto/manual/keep-source,
supported/unsupported language pairs, one/multiple workers, custom/cloud request
schemas with mocked HTTP before live services, cancellation at every boundary,
duplicate input names, malformed SRT, invalid references, disk-full/permission
errors, stale artifacts and interrupted writes. For real inference, confirm
spoken language/voice and timing in addition to file decodability.

Release testing must include a freshly created runtime rather than this existing
workspace, relocation to paths with spaces/non-ASCII characters, no external
Python/FFmpeg assumptions, restricted writable locations, first run online,
subsequent offline run, unavailable optional features, all declared CPU/GPU
routes, and Windows/Linux/macOS individually. GUI acceptance includes navigating
during jobs, persistent status, rejected starts, dropdowns, keyboard/focus,
onboarding, errors, tray restore/quit, and destructive-action explanations.

The immediate recommended next step is to review this issue register and approve
one concrete fix batch. No new tools/frameworks are needed merely to start fixing
the lifecycle and wiring defects.
