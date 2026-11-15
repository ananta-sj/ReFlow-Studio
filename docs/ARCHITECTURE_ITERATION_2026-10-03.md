# Continued architecture and feature repair

Started: 2026-10-03, after the saved-state repair. Status: in progress.
Scope update, 2026-10-04: the user explicitly dropped the 500 MB constraint and
prioritized product quality and differentiation. Earlier size-target references
are historical; size reduction is no longer a release gate. The proposed main-AI
runtime migration was not approved and is withdrawn. Existing optional-engine
approval remains in effect. No new framework/tool is authorized by this update.
Current capabilities and the product-quality gaps are summarized in
[PRODUCT_READINESS_2026-10-04.md](PRODUCT_READINESS_2026-10-04.md).
This is a working ledger, not a claim of real-engine acceptance for every feature.
The latest verified state is summarized at the end; earlier checkpoints retain
their original pending/failed status as a chronological record.

The user authorized auditing and continuing repairs across the remaining project
without pausing for each scope, including Nodes, parallel processing, resource
estimates and model downloads. Explain any new tool/framework and preserve user
media/custom models. No new framework is planned. Changes remain local; no release
or push is authorized.

## Work sequence

1. Execution: strict enabled stages/input/output, subtitles, moderation, exports,
   unique outputs and durable recovery acknowledgment.
2. Models: validated downloads/installations, owned artifacts, explicit adapter,
   checkpoint/service voice binding and activation checks.
3. Nodes/jobs: common parameters, connected controls, explicit graph limits and
   preservation of queue/cancellation safety.
4. Resources: per-stage actual device routes, consistent units, honest heuristic
   estimates and bounded scheduling/memory use where feasible.
5. Runtime/delivery: read-only diagnosis, explicit optional dependencies, portable
   workers, coherent manifests/build checks/offline behavior and documentation.
6. Regression/feature checks; record real-engine/GUI/platform gaps individually.
   Missing external decisions/assets do not count as passing acceptance.

## Starting evidence and scope ledger

Historical audit: FULL_PROJECT_AUDIT_2026-10-03.md, A01–A40. The saved-state
foundation passed 345 aggregate backend tests plus one additional test, 65 UI
checks and a TypeScript/Vite build. Portable Python is 3.10.11. The 500 MB delivery
target remains unresolved; replaceable weights were removed by user approval.

| Area | Starting status |
| --- | --- |
| A01 cancellation | Repaired; real providers pending |
| A02 parallel speech | Inference serialized; tooltip/ETA follow-up pending |
| A03/A28 reset/removal | Ownership repaired; cross-store rollback limitation |
| A04/A05/A06 queue/session | Repaired; persistent batch recovery separate |
| A07 saved state | Foundation complete; interrupted-offer acknowledgment pending |
| A08/A22–A26/A29 models/providers | Pending |
| A09–A18/A20/A21 outputs/stages | Pending |
| A19 devices/resources | Pending |
| A27 transfers | Removal blocked/drained; explicit cancellation pending |
| A31–A38 runtime/build/Nodes/offline | Pending |
| A39 commercial permissions | External product/distribution decision |
| A40 real-engine/GUI/resources/platforms | Acceptance pending |

Details/checks/decisions are appended as batches complete. Listing an issue does
not close it; original audit evidence remains unchanged.

## Implemented during this continuation (verification still in progress)

### Execution and output contracts

- Enabled lip-sync, enhancement and visual filtering must return the requested
  destination with a valid video stream. Missing results or the original input
  are errors, rather than a completed job with a silently skipped stage.
- GFPGAN and visual classifiers share a frame transformer that checks decoder
  and encoder initialization, frame count, dimensions, pixel format and scale.
  It releases the encoder before cleanup, including on Windows failure paths.
- NudeNet uses its current ndarray API and exposed-part labels. Detector import,
  initialization and frame failures propagate. There is no fail-open frame skip.
- Wav2Lip and MuseTalk get unique job work directories, checked process exit
  status and validated result video. A stale result from another job is unusable.
  Wav2Lip receives the selected compute device explicitly.
- MuseTalk receives selected model paths and its supporting-model root. Its
  vendored inference now uses argument lists and checked FFmpeg processes,
  rejects incomplete face/frame data, and raises task failures. It currently
  requires a detected face in every source frame; multi-speaker tracking and
  graceful preservation of no-face frames remain separate work.
- SRT parsing validates the whole file: indexes, timestamp syntax/ranges,
  increasing cue duration and nonempty text. Malformed trailing blocks cannot
  disappear silently. Multiline text and tags remain intact.
- Text classifier labels must explicitly describe one positive and one negative
  binary class. Ambiguous or generic labels cannot imply a polarity. Failed
  label validation never publishes the cached model as ready.
- A toxicity classifier removes a flagged line by returning an explicit empty
  result; it never synthesizes an English placeholder into another language.
  Custom instructions are rejected for a fixed classifier. Source-language
  jobs also run the active text filter; removing all dialogue fails visibly.
- Parallel speech uses a window of at most twice the worker count, bounded by
  the next segment to mix. An early slow segment cannot cause an unbounded
  completed-clip buffer. Mixing preserves source order and consumes clips.
  CPU/GPU model inference remains serialized; worker count receives no invented
  ETA discount. Full-length PCM buffers still require further memory review.
- Render names include random identifiers. Audio stems use the actual source
  vocals, optional background, dubbed speech and mastered mix. For stem exports,
  the complete main render and stems are prepared in a sibling temporary
  directory, then published with one directory rename. Failure publishes no
  incomplete bundle. Bundles appear under an output directory named after the
  render; ordinary renders retain their individual-file layout.

### Selected models, downloads and recovery

- Local artifact contracts distinguish CTranslate2 Whisper, NLLB, XTTS, RVC,
  F5, GFPGAN, Wav2Lip/MuseTalk and binary classifiers. A selected missing or
  incompatible model cannot silently become a default model.
- Activation requires the correct stage, installed status and an existing local
  path. Bridge activation checks the adapter contract. Download completion
  publishes installed status only after validating the resulting artifact.
- RVC uses the registered checkpoint and optional index directly. The embedded
  configuration and 256/768 input channels select V1/V2; forced V2 configuration
  creation was removed. Unsupported loader/version/index combinations fail.
  Checkpoint contract checks use restricted tensor loading.
- Voice selection uses registry IDs. Legacy display names still resolve when
  unique; duplicate names produce an explicit ambiguity error. An ElevenLabs
  speech-to-speech service voice ID is distinct from the display name.
- Voice installation keeps artifacts in their owned download tree. It never
  replaces global user weights. Archives require exactly one inference weight
  and at most one retrieval index; ambiguous archives are retained for reviewed
  removal, rather than choosing the last weight encountered.
- Direct downloads use unique staged files and a destination lock, reject HTML,
  empty, compressed/unverifiable and truncated responses, fsync before rename,
  and retain an earlier destination on failure. Repository downloads use a
  staged directory, refuse replacement of an existing repository and drain the
  producer before cleanup. ZIP traversal and overwrites are rejected.
- F5's official recommendation downloads only its v1 checkpoint/vocabulary and
  documentation at revision `84e5a410d9cead4de2f847e7c9369a6440bdfaca`, inspected
  from the official model API during this iteration. Other repository variants
  are excluded. F5 binds that checkpoint/vocabulary explicitly.
- Recovery reads no longer consume an interrupted-render record. Explicit
  discard compares a content token under the store lock; a stale dialog cannot
  delete a newer render's record. An accepted restart replaces the record only
  after the new job's marker is durably written. This is a restart from the
  beginning, not a stage-level checkpoint or persisted batch queue.

### Optional runtimes approved by the user

The user explicitly approved separate environments and required packages for
F5, NudeNet and MuseTalk. No product framework was replaced. The current portable
runtime and the existing `.venv` were preserved.

`dev/prepare_optional_runtime.py` copies a small embedded-Python runtime into
`runtime_profiles/<feature>` and installs into only that profile's site-packages.
It does not create an absolute-base-dependent virtual environment. The isolated
Python search path excludes the core and development site-packages. Profile
readiness is published only after `dev/verify_optional_runtime.py` checks every
declared dependency and feature imports. Workers have file-backed diagnostics,
owned temporary request/log directories, inherited job cancellation and bounded
timeouts. Models and service caches stay under the project. Ready profiles are
CPU profiles; future CUDA profiles require their own compatibility verification.

| Profile | Verified packages | Recorded installed bytes | Evidence |
| --- | ---: | ---: | --- |
| vision | 12 | 300,718,667 | `validation/2026-10-03-vision-runtime.json` |
| F5 | 151 | 1,647,125,297 | `validation/2026-10-03-f5-runtime.json` |
| MuseTalk | 58 | 2,013,878,179 | `validation/2026-10-03-musetalk-runtime.json` |

The table above records installation size before clearance. On 2026-10-04,
`dev/trim_optional_runtime.ps1 -Apply` removed **30,440 files / 1,107,613,513
bytes** from the newly created profiles. The receipt contains every removed
file and its original size (`validation/2026-10-03-optional-runtime-trim.json`).
Only bytecode caches and MuseTalk PyTorch's 708,668,648-byte `dnnl.lib` were
removed. That static library supports native-extension compilation; inference
DLLs were retained. These profiles target inference and no longer include that
compilation SDK component. Original portable/development environments were not
trimmed. The planner rejected reparse points and paths outside `runtime_profiles`.
An initial inefficient planning run was interrupted before any deletion; the
optimized run completed successfully.

Post-clearance sizes, with dependency, import and feature probes passing:

| Profile | Bytes after clearance | Verification |
| --- | ---: | --- |
| vision | 263,719,327 | Actual NudeNet detector on a blank image |
| F5 | 1,439,090,115 | CPU convolution and actual TorchCodec WAV decoding |
| MuseTalk | 1,151,607,799 | CPU convolution and vendored inference-module import |

Reports retain their original Oct-03 filenames but now describe the latest
post-clearance measurements. These tests establish runtime readiness, not
F5 checkpoint synthesis or MuseTalk checkpoint rendering. F5's Google dependency
emitted a Python 3.10 end-of-support warning; upgrading the interpreter requires
an independently tested runtime migration and was not silently performed.

These are installed package/runtime bytes before model downloads and final cache
clearance, not compressed delivery sizes. Package receipts were used to create
version/hash locks in `packaging/optional`. Three pure-Python dependencies
(ANTLR's runtime, transformers_stream_generator and Encodec) require building
from their pinned source distributions; byte-identical wheel reproduction across
different build environments is not yet claimed. Jinja2's missing pip receipt
hash was computed from its exact installed wheel URL. Installer warnings about
the existing development environment were distinguished from checks run inside
the isolated profiles, where all declared requirements passed.

NudeNet 3.4.1 includes the default 320n ONNX model and supports ndarray input.
Its actual detector ran on a blank image and the actual optional worker processed
a four-frame video. This proves initialization and the video path, not detection
accuracy on representative content. See [the package's official instructions](https://pypi.org/project/nudenet/3.4.1/).
F5's API imports and its TorchCodec decoder read a real WAV. MuseTalk's vendored
inference module imports in its profile. Full F5 synthesis and MuseTalk model
inference remain unverified. F5 additionally downloads a vocoder and reference
transcription model on first use; they are not included in the sizes above.

### Nodes, estimates and offline behavior under verification

- Nodes now builds job parameters through the same production helper as
  Dashboard, including source language. Subtitle muting controls actual output
  inclusion. Dashboard exposes stem exports, subtitle inclusion and burn-in
  font size. Audio-only jobs reject subtitle styling. Required graph nodes and
  read-only/unknown parameters cannot be edited through the bridge.
- Resource estimates identify CPU-bound stages and avoid a GPU discount for
  their work. Remote services get no assumed speed advantage. Parallel workers
  increase the decoded-audio RAM estimate, rather than GPU model memory. These
  are uncalibrated estimates; downloads and service latency remain unknown.
  Per-actor model residency and representative calibration still need review.
- Offline policy permits loopback services and local files, rejects remote
  service calls/redirects, and forces local-only Whisper/M2M loading. Optional
  workers propagate HF offline flags and project-local cache paths.
- Demucs receives an explicit device and owned output directory. Its model is
  obtained through the guarded downloader into a project-local repository,
  checked against the vendor filename's SHA-256 prefix, then loaded through
  `--repo`. It cannot silently fetch into the user's global Torch cache. The
  implementation is pending feature-specific tests and real separation.
- Startup integrity diagnosis actually imports required modules and reports
  failures. It performs no automatic pip repair. Selected-feature preflight
  checks imports and model contracts before media extraction/synthesis.

## Validation checkpoints and remaining acceptance work

The continuation's first combined targeted run passed 29 checks. The strict
frame/provider tests passed nine checks, then two optional-worker checks were
added. A later focused run passed 102 checks. The model/bundle/recovery suite
passed 12 checks. A full checkpoint passed **390 backend tests in 43.225 s**;
the subsequent resource/offline/preflight edits are not covered by that pass.
The next aggregate found two preflight ordering/None-registry errors; these were
repaired and the 15 speech-language checks passed. Full verification is ongoing.
Existing frontend scripts passed 65 checks. TypeScript/Vite built successfully
after the Nodes/export changes; later edits require another build.

Logs under `docs/validation` record each run. Test fixtures were corrected to
write literal CRLF without Windows double translation, explicitly select no
active moderation model, and force mocked in-process providers when optional
profiles are installed. A failed focused invocation lacked UTF-8/workspace-temp
settings; the corrected invocation passed. None of these harness failures is
counted as production acceptance. Earlier reports and their evidence remain
historical snapshots, rather than hashes of the current sources.

Still required: finish resource/device/cast residency review, validate all new
preflight/offline paths, explicit transfer cancellation, cloud configuration
editing, graph persistence/round-robin cast explanation, reproducible portable
delivery and size accounting, real engine/model acceptance, and GUI/platform
checks. AirLLM/commercial model permissions need explicit recorded capabilities
and product decisions. The 500 MB lightweight core target is **not achieved**
by the current all-in-one runtime; approved optional environments and weights
must be accounted separately. No release, commit or push has been performed.

## 2026-10-04 continuation: transfer ownership, Nodes and service configuration

### Download cancellation

Each tracked model transfer owns a `RenderContext`. Stop requests mark the
context and the UI displays "Stopping" until the producer exits. Model removal
and factory clearance remain blocked throughout that interval. A cancelled
transfer cannot publish an installed registry entry; the installation check
and cancellation request share the context lock. Hugging Face's internal
transfer may finish its current request before joining, so cancellation is
acknowledged immediately but completion is not promised to be immediate.

Two aggregate regressions were repaired: reading an absent registry entry must
not prevent draining an already-owned producer, and failure to deliver the
final UI event must not escape cleanup. Tests cover cancellation while blocked,
protected deletion previews, release after worker exit and cancelled installation.

### Persistent Nodes and truthful UI

`core/graph_state.py` saves supported node instances, voice choices, optional
switches and finite layout coordinates in `graph.json`, using the existing
atomic JSON store. It reconstructs the supported fixed topology instead of
trusting saved arbitrary edges. Missing required nodes, duplicate IDs, unknown
parameters and altered read-only values are rejected; original corrupt bytes
are retained in a recovery copy. A failed save rolls back the in-memory edit.
Dragging persists position on drag completion. Dashboard remains the owner of
shared optional-stage switches; saved cast/layout are independent.

Deleting a middle Voice instance previously made the next duplicate reuse an
existing ID. IDs now use the greatest surviving numeric suffix plus one, and
cast order is numeric (2 precedes 10). Tests exercise deletion, duplicate creation,
layout reload, required/read-only protections and failed-save rollback. The UI
waits for accepted changes and surfaces rejection messages. It explicitly states
that the pipeline order is fixed and extra voices alternate by transcript segment;
there is no speaker-identification implementation.

### Connected service configuration

Cloud and local-service addition accept a JSON request configuration, retained
under the stage's existing provider metadata key. Advanced fields are collapsed
by default. ElevenLabs presets expose a separate service voice ID; a display
name cannot substitute for it. URL, stage/preset and configuration shape are
validated before credential storage. Invalid additions leave no credential or
registry entry; registry-write failure attempts to remove the newly stored key.
Tests verify configuration reaches the selected provider metadata and secrets
are absent from returned model records. Paid/live remote-service acceptance is
not claimed. Editing an existing connection remains separate acceptance work.

### Estimates and evidence

The UI labels estimates uncalibrated and shows the decoded-audio buffer RAM
approximation, explicitly excluding model memory. Downloads and remote latency
are excluded from timing. Voice estimates now use the chosen cast rather than
an unrelated globally active Voice entry, count unique resident actor models
once and omit XTTS residency when all actors use F5. These remain heuristics,
not measured peak-memory guarantees or admission control.

Checkpoints: 396 backend checks passed after download repairs; 400 passed after
the first graph/service changes (64.555 seconds). A separate 38-check lifecycle,
graph and service run passed after adding graph persistence. The frontend built
with TypeScript/Vite and 14 architecture UI checks passed. Current logs use
`validation/2026-10-04-*`. Later changes require the next aggregate checkpoint.
Scoped frontend lint exits successfully with existing React warnings; an earlier
unscoped run traversed installed dependencies and is not used as source validation.
Vite still warns about the large frontend chunk. Runtime import probes include
real CPU convolution after static-library removal. Representative synthesis,
separation, rendering, desktop behavior and other-OS portable delivery remain
open; the iteration is still in progress.

### Real Whisper execution and a newly exposed timing defect

An explicit acceptance script downloaded only the replaceable Whisper **tiny**
model into the project's cache and transcribed an eight-second local sample.
The original sample-1 run executed successfully but emitted timestamps beyond
the actual decoded clip. Its initial smoke criterion (nonempty transcript) was
insufficient and is **not counted as accepted transcription**. The subsequent
run rejected those timestamps. `require_media_bounds` now checks finite numeric
times, positive intervals and source-duration bounds; the local worker applies
it against Whisper's decoded duration. VAD is enabled using the existing
faster-whisper dependency. Worker failures return a bounded log excerpt to the
caller instead of only a generic process exit code.

Sample 2 subsequently passed the real CPU worker path with cached weights and
`REFLOW_OFFLINE=1` in **8.422 seconds**, detecting English at confidence 0.9839.
Its transcript is recorded in `validation/2026-10-04-whisper-sample-2.json`.
This is execution/timing acceptance for tiny on one sample, not a human-reviewed
accuracy benchmark, default-medium acceptance, or proof for all languages.
Both sample files were hashed and preserved; extracted audio lived in an owned
job workspace that was removed after exit. Logs retain the failed bounds run.

### Catalog compatibility and F5 capabilities

Unsupported local catalog entries now appear as reference links, with their
one-click download removed. Known reference URLs are rejected by the bridge
before a download thread starts. Automatic candidate ranking is restricted to
catalog repositories with implemented adapters. A matching Hugging Face task
tag or high download count does not establish compatibility. Known supported
entries also supply their adapter marker in Quick Add. Custom remote services
explain that endpoint/body/response configuration is required in addition to
credentials. Model discovery/offline coverage remains under review.

The pinned F5 v1 Base recipe is no longer treated as an unrestricted-language
generator. Preflight accepts English/Chinese by default, with registered custom
checkpoint language declarations checked separately. The catalog records the
upstream weights' CC-BY-NC-4.0 license; this is material to the later business
discussion. Sources: [official model card](https://huggingface.co/SWivid/F5-TTS)
and [official inference guidance](https://raw.githubusercontent.com/SWivid/F5-TTS/main/src/f5_tts/infer/README.md).
Full F5 checkpoint synthesis is still unverified.

### Real separation and subsequent downloader/runtime repairs

The real Demucs acceptance initially failed because the upstream loader omits
`weights_only`, whose default changed in the installed Torch version. The new
`core/run_demucs.py` worker forces restricted loading and permits only the model's
required HTDemucs, Fraction and NumPy scalar/dtype classes. Unrestricted pickle
loading was not enabled. The official checkpoint downloaded over HTTPS matched
the vendor filename's checksum prefix; its complete SHA-256 is now pinned as
`8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4`.
The repaired worker passed with networking disabled, producing two playable
3,000-ms stems from a three-second local sample in **18.875 seconds**. The
source sample was preserved and temporary stems were cleaned after exit.
Separation accuracy is not human-reviewed. Evidence:
`validation/2026-10-04-demucs-engine.json` and the failed/repaired run logs.

The app import and bundled FFmpeg/FFprobe checks also passed, including real
H.264 encoding. This does not establish desktop-window or other-platform behavior.

RVC preprocessing now uses an owned unique file instead of deleting an existing
`reference_16k.wav` sibling. RVC and XTTS validate staged speech before replacing
a destination, preserving prior output on failures. RVC caches checkpoint
validation and loaded selection until checkpoint/index identity changes, avoiding
reloading an unchanged voice for every segment. Regression checks cover prior
output and sibling preservation, repeat inference and changed-checkpoint reload.

Default asset recovery now uses the shared guarded downloader, including exact
expected-size validation before publication, fsync, identity encoding, offline
policy and unique temporary files. ZIP extraction rejects duplicate target paths
before creating output and checks cancellation while copying each megabyte.

Hugging Face snapshot transfers now run in an owned child process with a one-hour
ceiling. The controller joins after the existing process manager stops the child
on cancellation, so a stuck native transfer need not keep deletion blocked
indefinitely. A test starts an actual sleeping process and verifies cancellation,
process release and workspace cleanup. Preallocated HF cache files are excluded
from progress: only completed model files count, intermediate percentage is below
100, and transfer speed/ETA are unknown until completion. The UI explains that
progress updates per finished file. The initial F5 acceptance download used the
older thread implementation; later transfers use this repaired process path.

Latest checkpoints before the last downloader/publication edits: **407 backend
checks passed in 59.928 seconds**, all **79 frontend contract checks** passed,
and TypeScript/Vite built successfully. The RVC/XTTS focused run passed 45 checks;
shared-downloader checks passed 36; repository process/progress checks passed 29.
Final aggregate verification remains in progress. AirLLM is absent from the
runtime; a separate environment needs the user's pending approval. No AirLLM
package has been installed implicitly.

### Continued acceptance and packaging checks — 2026-10-04

The next aggregate checkpoint passed **417 backend checks in 62.091 seconds**.
TypeScript/Vite also passed after adding missing Quick Add service configuration
and ElevenLabs voice-ID inputs. No new frontend packages were added. These
checkpoints precede the subsequent Python-worker and portable-builder changes;
their final verification is still pending.

The real F5 CPU profile synthesized a playable **4,661-ms** clip containing
223,788 bytes. Total acceptance time was **701.484 seconds**, including model
recovery. Reference text was supplied explicitly, so automatic reference
transcription remains unverified. Production's empty-reference-text route can
download an additional upstream ASR model. The optional provider currently starts
a fresh process for each segment, repeating model initialization; persistent
worker reuse and measured estimates remain outstanding. This acceptance proves
synthesis output, not subjective cloning quality or a completed multi-stage render.

Wav2Lip's former no-face/resize fallbacks substituted black face crops, and its
mel-window logic could drop final video frames. Those paths now fail explicitly
when a face cannot be detected and pad the final mel window. Video processing uses
batches of at most 32 frames instead of keeping the entire source in RAM. Every
decoded frame is processed; incomplete decoding, invalid crops/predictions and
encoder failure abort the stage. Audio conversion and final muxing use checked
argument-list subprocesses. The no-smoothing option is honored. Audio/mel buffers
still occupy memory, and detection selects the largest face independently per
frame; identity tracking and occlusion handling are not established.

Real Wav2Lip CPU acceptance passed: **five decoded/output frames at 5 fps** from
a one-second preserved sample; output 45,603 bytes, total recovery/run time
147.578 seconds. Human visual/lip-sync-quality review remains pending. Evidence:
`validation/2026-10-04-wav2lip-engine.json`. Fifteen visual contract checks passed,
including tail padding, batch preservation, short-audio rejection and closing a
reader after early consumer exit.

The owned-process Hugging Face downloader also passed a real pinned-revision
transfer of the 13,800-byte F5 vocabulary and cleaned its job workspace.
Evidence: `validation/2026-10-04-hf-process-transfer.json`.

Frozen executables previously used `sys.executable` to run Python scripts, which
would relaunch the application executable rather than a Python interpreter.
Worker resolution now uses the source interpreter or an explicit/bundled external
Python worker and raises an actionable error when the frozen distribution lacks
it. This is a guard and routing repair, not acceptance of native artifacts.

`packaging/build_portable.py` generates a file/size manifest or creates a new
Windows portable directory. It excludes personal settings, credentials, samples,
outputs, model-download directories, development environments and caches. Optional
profiles are selected explicitly. Vendor-package inference assets remain included
when required by those packages. The first model-free core inventory was
**2,841,334,166 bytes**, so the 500-MB goal is **not met**. The Python CPU runtime
and FFmpeg account for much of that floor. No original environment was deleted to
manufacture a smaller result. A copied portable distribution has not yet passed
acceptance, and Linux/macOS feature acceptance remains unverified.

The Windows launcher now prefers its available portable interpreter over an old
native build. Integrity CLI failures now return a nonzero status, and explicit
legacy asset recovery uses guarded atomic downloads rather than overwriting or
deleting a prior file on transfer failure. README platform/version claims were
corrected to match the verified Windows Python 3.10.11 setup.

### Real visual engines, isolated-session reuse and recovery revisions

The next aggregate run passed **422 backend checks in 96.096 seconds** and all
**79 frontend checks**. Later session/recovery changes are not covered by that
checkpoint; their focused run passed **59 checks**, including three tests that
launch real processes to verify reuse, error reporting, cancellation and cleanup.

GFPGAN recovered its three required assets and produced five complete frames at
5 fps. Initial recovery/run time was 1,370.391 seconds. The repaired strict path
also passed offline in 62.625 seconds. Its upstream helper catches inference
errors and substitutes the original face; Reflow now propagates those errors and
preserves prior output. Face helper assets use an absolute project path. A custom
enhancer downloads only the two required helper assets, rather than an unrelated
default restoration checkpoint. Restoration loads tensor-only weights and checks
prediction validity. Human restoration-quality review remains outstanding.

MuseTalk passed a real five-frame CPU acceptance in 193.062 seconds after face
asset recovery. Two actual failures informed repairs: parser checksum verification
initially imported a controller dependency absent from the isolated environment;
that verification now uses a dependency-free module. An offline run then attempted
vendor face-model downloads. Those assets now recover through the project
downloader, and the worker requires them before detector initialization. Parser
checksums come from pinned HF metadata; face-detector/FAN checkpoints matched the
vendor filenames' checksum prefixes, and their full SHA-256 values are pinned.

MuseTalk source frames, latents and generated faces now stay within batches of
at most 32 frames. It preserves source-video frame count rather than cycling the
source to match a differently sized audio feature sequence. A one-frame audio
rounding gap can reuse the preceding feature; a larger shortage fails. Fractional
frame rates are preserved, final partial audio frames are included, and feature
window failure raises an error instead of terminating with a successful exit code.
Coordinate-pickle reuse is explicitly rejected in this bounded path. Audio
features and extracted/generated image files still scale with clip duration.
No identity tracking or subjective lip-sync-quality acceptance is claimed.

The newly copied model-free Windows distribution passed a hidden desktop check
using its own Python interpreter: page rendered, Python bridge connected, settings
loaded, ten graph nodes returned, and required library imports passed. This is
boot/bridge acceptance, not human layout review or full-render acceptance. The
builder initially excluded a model-code directory along with weight directories;
that rule was narrowed to the exact download/checkpoint locations and the missing
code restored. Copied installation wheels were removed without modifying the
original runtime. The revised source inventory is approximately **2.824 GB**;
the copied artifact needs its final manifest/engine verification after all edits.

F5 optional inference now has a job-owned persistent worker: a checkpoint remains
loaded across subtitle requests and is shared by identical selections within the
job. JSON mailbox publication is atomic, calls are serialized, diagnostics are
bounded, and cancellation uses the existing owned-process manager. Job cleanup
closes the session and joins its controller before deleting the workspace. Real
two-request F5 acceptance passed offline. Automatic reference transcription remains
unverified; its upstream ASR download/storage is still a separate acceptance item.

XTTS, M2M100 and NLLB recovery sources now pin repository revisions and known
large-file SHA-256/size metadata. Recovery excludes unused training/alternate
weight formats. Default M2M100 recovery now uses the shared guarded downloader,
followed by local-only model loading, rather than a download hidden inside the
in-process Transformers loader. Their actual CPU acceptance passed.

Estimates now include the previously omitted background-separation stage and
audio mastering even when background preservation is disabled. Nonfinite media
duration is rejected by the probe. Timings remain uncalibrated; cold-start model
loading, F5 reference ASR, engine quality and per-platform performance are not
represented as established guarantees. AirLLM approval and an RVC test checkpoint
remain pending user input. No AirLLM package or arbitrary third-party voice was
added.

### Continued acceptance — real speech and translation, 2026-10-04

Receipts are in `docs/validation/2026-10-04-{xtts,m2m100,nllb}-engine.json`
and `2026-10-04-f5-session.json`. These use actual CPU inference and installed
model artifacts, not mocked providers. Download time is included in the first
three elapsed totals below; these are not steady-state performance benchmarks.

| Check | Observed result | Elapsed time | Limit of acceptance |
| --- | --- | --- | --- |
| XTTS | 3,077 ms playable WAV, 135,756 bytes | 1,431.656 s including download | English synthesis only; subjective voice quality not approved |
| M2M100 | Nonempty Hindi-script output | 1,496.187 s including download | Functional inference only; incorrect rendering of “Good morning” observed |
| NLLB | “सुप्रभात, यह एक छोटी सी परीक्षा है।” | 1,685.484 s including download | One short English-to-Hindi example; no broad quality claim |
| F5 session | Two playable 1,227 ms WAVs; same worker PID for both requests | 294.609 s first request, 157.407 s second; 453.5 s total | Explicit reference text only; automatic reference ASR not tested |

M2M100 returned “ठीक है, यह एक छोटी सी परीक्षा है।” for “Good morning.
This is a short test.” The inference check passes because an actual translated
artifact was produced, but semantic quality is not accepted. No engine replacement
or additional framework was introduced. Translation fidelity requires a multilingual
review set and human review before product claims.

F5's controller stopped its process and removed its job workspace after both
requests. Warm reuse saves repeated initialization but does not make this CPU
fast enough for interactive speech generation. Estimates now expose an F5-specific
warning in the Dashboard; no universal timing ratio is inferred from this single
machine. Session hardening also rejects malformed worker responses, permits
cleanup after controller thread startup failure, and includes vocabulary size/
modification time in the cache key so a changed vocabulary cannot reuse an old
session.

`dev/verify_workflows.py` exercises the production pipeline entry point with
temporary read-only fixture model connections, leaving user selections/settings
untouched. It runs offline against the cached Whisper-tiny, NLLB and XTTS models.
Audio/video acceptance requests two speech workers, background preservation and
four exported stems. Video acceptance adds Wav2Lip, GFPGAN and NudeNet, plus
soft subtitles; the video fixture is a static portrait taken from the existing
sample with its first eight seconds of audio. This intentionally narrow fixture
does not establish identity tracking, moving-face robustness or subjective quality.
Each run records stage events and failure details, requires final publication,
checks media/stem duration, preserves accepted QA artifacts, and cleans its owned
workspace. Whole-workflow video checks are currently running; engine acceptance
above must not be mistaken for their completion.

#### Completed whole-workflow receipts

- `2026-10-04-subtitle_translate-workflow.json`: two cues translated offline;
  original 0–2 s / 2–4 s timings preserved; SRT published; owned workspace removed;
  58.359 s including pipeline/fixture setup. NLLB translated the isolated first
  cue “Good morning.” as “शुभ दोपहर.” (Good afternoon). This is a second concrete
  semantic-quality issue despite functional acceptance; do not claim either
  translation engine is quality-certified.
- `2026-10-04-audio_dub-workflow.json`: real Whisper tiny → NLLB → XTTS Hindi,
  Demucs vocal/background separation, two segment workers, mixing and atomic
  stem-bundle publication passed offline. The main WAV and each of the four stems
  (vocals/background/master/dubbed) remained within 150 ms of the eight-second
  fixture duration. Workspace removed; QA artifacts preserved in the report's
  output folder; elapsed 378.562 s including setup. Shared speech inference is
  deliberately serialized; the worker count does not imply two simultaneous
  XTTS model inferences or a guaranteed twofold speedup.
- Aggregate: **426 backend checks passed in 151.649 s**. Additional final focused
  checks: **36 passed in 3.382 s**. All **79 frontend checks** passed again and the
  frontend production build passed (existing large-chunk warning remains).

Translation and classifier providers are now explicitly released after their
stage, before speech/visual model initialization, to reduce overlapping model
residency on machines with limited RAM. This is a lifecycle improvement; it does
not establish a precise peak-RAM guarantee or memory admission control.

Residual API audit: legacy `process_video_gen` arguments `pitch_shift` and
`blur_strength` currently have no effect on the active provider path and are not
exposed by the current bridge/UI. Provider blur kernels are fixed. They must not
be advertised as working user controls until implemented or removed. Automatic
F5 reference ASR still uses the upstream large-v3-turbo path when reference text
is empty, unlike the explicit-text F5 acceptance fixture; the ordinary F5 render
path therefore remains unaccepted until that dependency/download is exercised.

#### Further recovery and storage corrections

F5 automatic reference transcription now recovers its existing upstream
Whisper-large-v3-turbo dependency through the shared downloader before inference.
The source is pinned to revision `41f01f3fe87f28c78e2fbf8b568835947dd65ed9`;
the selected safetensors file is 1,617,824,864 bytes with SHA-256
`542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1`.
Tokenizer/configuration files are explicitly allowlisted; alternate weight
formats are excluded. The worker initializes the upstream F5 ASR pipeline from
the recovered local directory, so that dependency does not silently download
from an unpinned default repository during synthesis. Explicit reference text
continues to bypass ASR recovery. The automatic-reference acceptance run is in
progress; no speech-quality acceptance is implied. This adds replaceable model
storage, not another package/framework, and stays outside the core distribution.

The offline restoration helper now uses the registry's `JsonStore` transaction
instead of writing `models.json` directly. This preserves concurrent app changes,
the active model selections, and prior saved bytes if publication fails. The
recovery/session/speech regression group passed **63 checks in 24.065 s**;
the stage-release/source/translation/parallel regression group passed **100 checks
in 82.812 s**.

Removed only generated `.vite` and `frontend/.architecture-npm-cache` caches:
381 files, **40,358,959 bytes**. Receipt:
`docs/validation/2026-10-04-generated-cache-cleanup.json`. Project containment and
reparse-point checks preceded deletion. User media, custom voices, installed
packages, original portable runtime and optional profiles were preserved.

The QA-copy refresh correctly failed its consistency check when six source
files changed during the copy/verification pass. This is an invalidated snapshot,
not accepted packaging. The refresh is being repeated against the completed
edits; its final receipt and subsequent desktop boot check determine acceptance.

#### Video-chain and copied-distribution acceptance

`2026-10-04-video_dub_lipsync-workflow.json` now records a completed real offline
chain: Demucs → Whisper tiny → NLLB Hindi → XTTS, two segment workers, background
mixing, Wav2Lip GAN, GFPGAN, NudeNet, soft-subtitle mux and four stem exports.
All **40 output frames** decode at **640×360 / 5 fps**, with H.264 video, AAC audio
and a `mov_text` subtitle stream. Main media and stems retain the eight-second
timeline within the acceptance tolerance. Atomic output bundle published;
owned workspace removed; accepted QA artifacts retained. Elapsed **1,217.11 s**
including fixture/preflight setup. Static portrait and short audio acceptance
do not establish performance/quality for long or moving-face footage.

I ran the heavy F5 acceptance concurrently with this video check, leaving less
than 1 GB RAM available on the 15.64 GB machine and causing memory pressure.
That was an unsuitable validation schedule. Only the verified owned F5 worker
was terminated after checking its parent verifier and request operation; its
parent recorded the failed/interrupted acceptance and cleaned the job workspace.
The logs already show successful automatic reference transcription, but that
interrupted synthesis is not accepted. F5 is being retried **alone and offline**
using the preserved downloaded assets. The overlapping video timing is not a
reliable calibration sample for normal rendering.

The final full QA-copy inventory passed: **42,919 files**, no size mismatches.
An application-only refresh then captured the five later generation-control
changes without recopying the unchanged runtime: **165 application files**,
no mismatches. `2026-10-04-portable-final-desktop.json` confirms that the copied
distribution boots using **its own Python**, renders the page, connects the
bridge, loads settings, returns ten graph nodes and passes library integrity;
elapsed **44.75 s**. This remains desktop/bridge acceptance rather than manual
layout review or a complete render from the model-free copied distribution.

Local XTTS, NLLB and M2M100 generation now checks job cancellation at each
autoregressive token boundary, with shared cancellation identity preserved when
Transformers copies its criteria. Cancelled speech/translation exceptions pass
through without being relabeled as generic stage failures. This does not claim
instant interruption inside a single tensor operation or during model loading.
Regression group: **113 checks passed in 26.875 s**. The concurrently completed
aggregate recorded **430 checks passed in 293.754 s**; some modules were imported
before the last edits, so focused checks and subsequent actual-generation
acceptance must establish those latest changes. Real XTTS token-boundary
cancellation acceptance is prepared and will run after F5 to avoid overlapping
heavy model loads.

### 2026-10-04: current acceptance, memory lifecycle and transfer integrity

This checkpoint supersedes the pending F5/desktop/cancellation statements above.
It does not erase failed attempts or convert fixture checks into quality approval.

**F5 automatic reference.** The isolated, offline retry succeeded in 484.688 s.
Its receipt is retained as `2026-10-04-f5-automatic-reference-before-release.json`.
The next repair transcribes once, validates that the transcript contains speech,
releases upstream Whisper ASR weights in a `finally` block, and retains a bounded
64-entry transcript cache keyed by reference path, size and modification time.
Explicit reference text bypasses this step. The persistent F5 worker reuses that
cache across segment calls. Failed transcription also releases ASR; changed
references invalidate cached transcripts. The original reference path is retained
so the upstream processed-reference cache remains usable. No new dependency was
introduced. The ASR asset remains revision-pinned and recovered into project-owned
storage before work starts; inference no longer initiates an unpinned ASR download.
The real offline acceptance after this repair succeeded in **252.688 s**, producing
1,227 ms / 58,924 bytes of playable WAV. This is observational timing, not a
controlled performance comparison. Receipt: `2026-10-04-f5-automatic-reference.json`.
Initial ASR loading can still overlap resident F5 model weights. The explicit-text
two-request persistent worker acceptance and the reference-cache regression test
cover reuse; a real automatic-reference two-request session is still separate
acceptance work. Human voice quality remains unverified.

**Actual cancellation.** `2026-10-04-xtts-cancellation.json` records cancellation
at an observed real XTTS token boundary, offline: **0.11 s** from stop request to
exception. Prior output bytes were preserved; staging and owned workspace were
removed. Total acceptance elapsed 51.36 s. This establishes the XTTS generation
boundary, not interruptibility of arbitrary model-loading or tensor operations.

**Dashboard/Nodes agreement.** Selecting the fixed video-plus-lip-sync workflow
now enables lip sync in the submitted parameters and preview estimate. Disabling
its checkbox selects the ordinary video workflow. Nodes explicitly chooses its
workflow from its own lip-sync setting, so a Dashboard selection cannot reactivate
a muted Nodes stage. Four frontend regressions were added: **83 frontend checks**
pass; TypeScript/Vite build passes (4.34 s). The existing large-bundle build warning
remains. No UI framework was added.

**Bounded cloud transfers.** `core/http_media.py` implements multipart upload
iteration and media download in **256 KiB chunks**, using the existing Requests
library and standard library. It calculates exact multipart length, preserves
repeated fields, removes local directory names from uploaded filenames, rejects
header injection and checks cancellation between chunks. TTS, voice conversion,
enhancement, filtering and lip-sync downloads now stage, validate and atomically
publish media instead of retaining the entire response in RAM. Empty/truncated
transfers, HTML/JSON error documents, invalid playable media and cancellation
preserve prior output. Responses close on failure and cancellation; redirects
retain the existing origin/credential controls. No package/framework was added.
Nine new tests include a real temporary **127.0.0.1** HTTP server, multipart
upload and streamed WAV checked by FFprobe. The default sandbox forbids listening
sockets (WinError 10013); the approved elevated validation passed **115 checks in
1.211 s**. This verifies the transport contract, not an authenticated production
cloud vendor or its inference quality. Chunk-boundary cancellation may wait for
a blocked socket read until the configured read timeout.

**Visual duration integrity.** Every enabled lip-sync, enhancement and filtering
stage must retain the stripped input video's duration within **0.25 s**. Shorter
or extended results fail before final bundle publication. The comparison uses the
actual video-only input, avoiding discrepancies between source audio and video
container duration. The tolerance permits small container/frame rounding; it is
not a guarantee of frame alignment or lip-sync quality. A regression rejects both
shortened and extended provider results and accepts a small rounding difference.

**Current aggregate and portable desktop.** After these changes, **447 backend
checks passed in 49.196 s**. Log: `2026-10-04-current-architecture-checks.log`.
The application-only QA refresh passed for **166 files**, no size mismatches;
unchanged portable runtime files are covered by the prior full 42,919-file
inventory. The copied application's own Python then passed the page walk in
**26.578 s**: Dashboard, Nodes, Assets, Marketplace, Logs and Settings, bridge,
library integrity, ten API nodes and ten rendered nodes, no captured JavaScript
errors. Receipt: `2026-10-04-portable-pages.json`. This is automated Windows desktop
acceptance; manual layout review, Linux/macOS and a production render from a clean
model-free distribution remain unverified.

**Storage truth.** The read-only full workspace inventory records **26,888,700,475
bytes** in 231,544 actual files (`2026-10-04-storage-inventory.json`). That includes
recovered replaceable weights, optional profiles, original environments, Git
history, development dependencies and the 2.83 GB QA copy. It is not the release
size. The core portable manifest is about **2.824 GB**, excluding downloaded model
weights and optional profiles; the three optional profiles total about **2.854 GB**.
Therefore the **500 MB delivery target is not achieved**. Current local recovery
weights occupy substantial additional storage. Seven skipped cache links were
inspected: all resolve within the project to already-counted owned blobs, not
external user cache paths. The inventory classifies ~56.65 MB of bytecode caches;
classification is not deletion authorization, and original runtimes remain intact.
The earlier 31 GB-to-6.3 GB cleanup checkpoint must not be presented as current
workspace size after approved engine recovery and acceptance copies.

**Remaining release gates.** Human speech/translation/video quality, realistic
long or moving-face footage, performance-calibrated estimates and memory admission
control, RVC acceptance using an authorized custom checkpoint, configured live
cloud services, Linux/macOS acceptance and the 500 MB architecture remain open.
The isolated NLLB greeting mistranslation and M2M100 semantic failure recorded above
are still quality issues. AirLLM optional installation remains pending approval;
no arbitrary voice checkpoint has been downloaded. This iteration remains open;
no commit, push, deployment or release was performed.

#### Offline MuseTalk and resource-routing follow-up

The latest MuseTalk acceptance ran with Hugging Face/Transformers offline flags,
using existing pinned assets and the isolated optional runtime: **178.688 s**,
five frames reported and five decoded at 5 fps, 34,561-byte playable output.
`2026-10-04-musetalk-engine.json` holds the current receipt;
`2026-10-04-musetalk-engine-before-offline.json` preserves the earlier run.
No new model/network recovery was required. This remains short-fixture mechanical
acceptance, not human visual approval.

Remote TTS/voice/visual service estimates no longer receive the selected local
GPU's speed multiplier. Mixed remote TTS plus a local voice converter still uses
the selected GPU route. Non-numeric, boolean, negative and non-finite saved model
sizes fall back to the declared heuristic instead of raising or returning a
corrupted/NaN estimate. **34 focused architecture checks passed in 0.470 s**;
`2026-10-04-resource-route-checks.log`. The QA application files were refreshed
again with zero mismatches. These corrections do not calibrate unknown service
latency, estimate service-side GPU/RAM, or establish memory admission control.

`dev/verify_f5_session.py --automatic-reference` now exercises two real offline
requests with the same reference, checks one worker PID, checks exactly one actual
upstream transcription marker in the completed worker log, then verifies worker
shutdown and workspace removal. It keeps a separate automatic-session receipt
so the earlier explicit-text session evidence is preserved. Acceptance is in
progress at this checkpoint and is not counted as passed yet.

#### Product-priority update from the user

The user explicitly said to forget the 500 MB target and make ReFlow the best,
distinctive tool. Stop treating core size as an outstanding requirement. Keep
cleanup focused on generated/redundant artifacts and preserve useful offline
capabilities. `SMALL_CORE_ARCHITECTURE_PROPOSAL_2026-10-04.md` is withdrawn and
retained as measured historical analysis; no main-AI runtime migration was
approved or performed. Storage reporting remains useful for installation/model
transparency, but is not a reason to remove functioning engine dependencies.

The latest full regression run after remote resource-routing corrections passed
**449 backend checks in 71.846 s**. The remaining product work centers on quality,
realistic media, user control over intermediate results, credible resource
estimates and reliable supported-engine/platform behavior. A running pipeline
and passing fixtures do not establish differentiation or production media quality.

#### Translation/voice quality chosen as the leading product priority

The user selected **better translation and voice quality first** rather than
leading with the proposed review workspace or batch-speed work. The priority is
recorded in `PRODUCT_READINESS_2026-10-04.md`; those other proposals remain future
work, not implemented capabilities.

**Completed real F5 automatic session.** Two requests succeeded offline in the
same worker (PID 16236), producing 1,227 ms / 58,924-byte WAVs each. The completed
worker log contains exactly **one** automatic reference transcription marker.
Worker shutdown and owned workspace removal passed. Request elapsed times:
**582.172 s** then **299.562 s**, total **884.157 s**. This confirms reference/model
reuse, but the CPU latency remains a material usability gap. The initial interval
overlapped the short regression run, and machine load differs from the previous
single-call acceptance; do not claim controlled speedup from these timings.
`2026-10-04-f5-automatic-session.json` and its preserved worker log contain the
receipt/evidence. Human voice quality remains false/unreviewed.

**Voice mastering clipping repair.** `AudioEngineer.master_voice_segment` used
to normalize to -1 dB peak before overlaying its high-pass treble copy. Integer
PCM overlay can saturate at full scale, producing distortion that normalization
afterwards cannot undo. The repair computes a conservative peak bound from both
signals, applies sufficient attenuation BEFORE the overlay, then normalizes the
mixed result to -1 dB. No engine, package or framework was added. Two real PCM
checks passed (0.113 s): a full-scale 4 kHz tone retains a sinusoidal waveform with
relative fit residual below 0.5% and a -1 dB peak; silence retains its timeline.
The compressor is bypassed only in the tone test to isolate unintended EQ/mix
distortion from intentional dynamic compression. This prevents mastering-induced
clipping; it does not repair clipped source samples or establish naturalness.
Evidence: `2026-10-04-voice-mastering-checks.log`.

**Reproducible translation comparison prepared.** Eight English-to-Hindi cases
cover the recorded morning/afternoon error, greeting context, negation, dates/
times, amounts, a polite request, brand identity and multi-sentence narration.
Proposed Hindi references and review criteria are stored in
`dev/translation_quality_cases.json`. `dev/compare_translation_quality.py` compares
deterministic beam widths 1 and 5 using the existing pinned NLLB or M2M100 model,
without changing production settings, adding a package, contacting the network,
or declaring exact-reference matching to be semantic acceptance. It records all
candidate outputs and timings; human review remains required. The installed NLLB
checkpoint defaults to greedy decoding; M2M100 defaults to five beams. Whether a
beam change improves this corpus must be established by the actual outputs.

#### First quality improvements and retained listening samples

NLLB's offline eight-case comparison completed in **102.141 s**. The isolated
morning greeting was wrong under greedy decoding (`शुभ दोपहर.`) and correct with
five beams (`सुप्रभात.`). Five beams also preserved the distinction between “some”
and “others” in the two-sentence reference more clearly. Both decoding settings
retained negation and the numeric/time details in the tested cases; neither is
certified generally accurate. Existing production NLLB now explicitly uses
**five beams with sampling disabled**, using the same model/runtime and token
limit. Warm five-beam cases took roughly 5–9 s versus 2–3 s for greedy in this
small run; the first greedy call included warm-up. This is a deliberate quality/
processing-cost tradeoff, not a universal benchmark or accuracy score. All raw
candidates/review criteria remain in `2026-10-04-nllb-quality-comparison.json`.
M2M100 is being evaluated against the same corpus separately; its production
settings have not been changed merely to match this isolated greeting.

Speech output now distinguishes valid silent background audio from generated
speech: the pipeline and local XTTS/F5/RVC publication guards reject **exact
digital silence**. XTTS retains prior output if an engine returns a silent WAV.
The pipeline also rejects a timing adjustment that cuts away all speech after
initial silence. This narrow signal test does not detect noise, wrong words,
unnatural pronunciation or extremely quiet nonzero speech. Focused speech,
parallel, translation and mastering group passed **101 checks in 20.881 s**
before the additional timing-removal regression; the latter has its own run.

`dev/verify_voice_quality.py` completed real offline XTTS English/Hindi synthesis
and saved an owned listening bundle at
`validation/2026-10-04-voice-quality-b6905bf2/`: reference, raw and mastered clips
for both languages. Correct source texts are supplied directly to isolate voice
from translation defects. English duration **3,682 ms**, Hindi **4,645 ms**;
mastering preserved both durations and produced peaks around **-1.000 dBFS** with
zero full-scale samples. Raw English had one near-full-scale sample; this count
alone does not establish perceptible clipping. Total **98.422 s**, synthesis/
mastering cases 33.125 s and 36.875 s. The completed run is recorded in
`2026-10-04-voice-quality.json`; workspace removed. Listening, pronunciation,
reference-voice similarity and naturalness are still **not human accepted**.

Newly identified remaining quality defect: `_dub_segment` still caps speed
adjustment to 1.3× and trims an overlong result to the available timeline. This
can remove trailing words even when the file remains playable and non-silent.
The new empty-after-timing guard covers complete loss, but does not close partial
word truncation. A proper fit strategy needs explicit treatment of available
silence, speech boundaries, regeneration/concise translation and user control;
silently treating duration preservation as word preservation is unacceptable.
Record this as an open quality gate, not a passed feature.

#### Word-preserving timing contract

The partial-word truncation issue above is now repaired at the output boundary.
The pipeline uses the gap before the next cue before accelerating speech, applies
even a small required speed correction instead of tolerating an audible overflow,
and caps the supported rate increase at 1.3×. If output remains overlong, it may
remove only a tail containing **exact digital silence**; audible overflow fails
with segment/voice/timing context before final publication. It no longer fades
and slices a spoken tail to manufacture a duration match. Overlong synthesis can
therefore produce an explicit fit error where the previous version reported
success with missing words. Shorter text, a faster voice or revised cue spacing
is required in that case; the missing review/editor workflow limits convenient
in-app correction and remains product work.

Regression checks cover using a gap at natural speed, safe silent-tail removal,
refusal to cut an audible tail (including a line delayed by leading silence),
and a real FFmpeg tempo correction for a 5% overflow. The real offline audio
workflow is being repeated with these timing guards and five-beam NLLB; its prior
receipt is archived as `2026-10-04-audio_dub-before-quality.json`. This preserves
historical acceptance rather than assuming an earlier cropped result proves the
new word-preserving behavior.

M2M100's same eight-case offline comparison completed in **60.000 s**. Five beams
still changed the contextual greeting to `ठीक है` (“okay”); greedy retained a
morning greeting in that case but was not universally preferable on the corpus.
Both settings retained the tested negation and amount details. No M2M100 default
was changed based on cherry-picking one sentence. Its current production isolated
greeting is the literal `अच्छी सुबह।`; human semantic/style acceptance remains
false. Receipt: `2026-10-04-m2m100-quality-comparison.json`. This supports expanding
quality evaluation and choosing providers deliberately, not declaring the fallback
engine's semantic issue fixed.

#### Listening feedback, measured loudness, and current timing failure

The user reviewed the retained English/Hindi XTTS samples and reported low
volume and a slow Hindi delivery. Original samples remain unchanged in
`validation/2026-10-04-voice-quality-b6905bf2/`. Two comparison previews were
created with the existing FFmpeg: `en-louder.wav` keeps its timing, while
`hi-louder-faster.wav` uses pitch-preserving 1.1x tempo. No global Hindi speech
rate was changed; the comparison awaits the user's listening feedback.

New `core/loudness.py` measures integrated loudness and true peak, applies
measured two-pass normalization targeting -14 LUFS / -1.5 dBTP, and validates
playability, channel count, sample rate and duration before atomic publication.
`AudioEngineer.master_voice_segment` now invokes this after its corrected EQ.
Existing FFmpeg/pydub are used; no new tool, package or framework was installed.
Job cancellation is propagated. Exact silence is preserved; clips too short for
finite gated measurements use peak normalization, which does not establish
integrated loudness. Output true peak allows up to 0.3 dB resampling tolerance.
This targets generated voice clips, not a verified final-mix mastering standard.

Preview measurements: English -14.39 LUFS / -1.47 dBTP; Hindi -14.44 LUFS /
-1.29 dBTP. Original Hindi measured -15.92 LUFS / -0.68 dBTP. The change improves
measured level and peak control; comfortable playback and naturalness still
require listening. Receipt: `2026-10-04-voice-feedback-adjustment.json`.
The previews predate the added post-normalization receipt fields; their
independent measurements are retained explicitly. Focused loudness/mastering/
speech checks: **56 PASS in 17.391 s**, including real FFmpeg gain/tempo,
short-clip fallback and cancellation preservation. Log:
`2026-10-04-loudness-checks.log`.

The repeated real offline audio workflow **FAILED**, as recorded in
`2026-10-04-audio_dub-workflow.json` and
`2026-10-04-audio_dub-quality-workflow.log`: after the maximum 1.3x adjustment,
segment 1 still needed **7.055 s** in an available **4.880 s** slot. The error
identified segment 1 and voice CLONED_USER. Total **225.875 s**; owned workspace
removed. The prior receipt is preserved in `2026-10-04-audio_dub-before-quality.json`.
This is evidence that the new word-preserving guard detected a real quality
failure, not evidence of successful current dubbing. The failed run preceded
the new loudness helper. Historical video/audio passes do not validate the
current speech chain. Duration-aware translation, regeneration or an editable
cue review remains required; raising the rate cap or silently clipping words
would not establish natural speech or semantic fidelity.

Final regression verification for this audio change: **460 PASS in 61.020 s**
(`2026-10-04-quality-final-backend.log`). The full suite used temporary loopback
HTTP fixtures under the approved execution scope. Mocked failure-path diagnostics
in the log are expected test output, not additional failed checks. No claim of
real synthesis quality follows from this regression count. The owned portable
QA application was refreshed: **167 files**, zero size mismatches, acceptance
true (`2026-10-04-portable-app-refresh.json`). Original runtime remains preserved.
Whitespace diff validation passed. Frontend was unchanged; previous 83 checks
and build evidence were retained rather than repeated without a frontend change.

Direct current-production NLLB probe completed offline in **19.687 s**:
`Good morning.` -> `सुप्रभात.`. Execution completed and workspace removed;
semantic acceptance remains false beyond this observed example. Receipt:
`2026-10-04-nllb-production-greeting.json`.

The user then accepted the revised volume and found the Hindi pace better, but
reported that the last word remained drawn out. Record volume feedback as
accepted for these previews only, and pace as partially improved, not fully
accepted. Investigating the ending with existing local audio analysis/Whisper;
no production language-wide speed change or new dependency was introduced.

Ending-focused comparison is now retained as `hi-shorter-ending.wav` in the
same review folder. Existing offline Whisper returned only three low-confidence
words and missed part of the known text; those timings are **not verified** and
were not used for an automatic last-word cut. Energy analysis found the last
inter-phrase pause between approximately 1.500 and 1.695 s. The preview starts
an additional pitch-preserving 1.18x adjustment at 1.620 s, within that pause,
for the entire remaining phrase. No speech samples are discarded. It preserves
the earlier preview's opening pace, then remeasures/normalizes the full clip.
Duration **4.201 -> 3.789 s**; achieved **-13.98 LUFS / -1.49 dBTP**. The relative
ending rate is a listening experiment, not an engine default or reliable word
alignment feature. Receipt: `2026-10-04-hindi-ending-preview.json`; analysis:
`2026-10-04-hindi-ending-analysis.json`. Workspace removed. Earlier samples
remain retained. User acceptance of this new ending is pending.

During preview preparation an incorrect unbound helper invocation produced an
unpublished incomplete candidate; a subsequent invocation lacked its temporary
workspace setting and failed. Both were corrected before presenting the result.
The final generation explicitly checked the adjusted phrase's expected duration
(with 80 ms tolerance), nonzero content and AudioSegment type before publication.
The latest receipt describes only the corrected 3.789 s candidate. These were
preview-script errors, not changes to the production pipeline or original media.

#### Revised diagnosis: unnatural delivery, not established slow speech

The user clarified that the voice feels unnatural and that perceived slowness
may have been a misdiagnosis. Naturalness is therefore **rejected** for the
presented Hindi previews. Volume was accepted separately. Do not treat the
1.1x/ending-specific tempo experiments as a fix or promote them to defaults.
No further production speed change has been made.

Inspection: XTTS uses temperature 0.75, speed 1.0 and sentence splitting, with
checkpoint defaults of repetition penalty 5.0, top-k 50 and top-p 0.85. The test
clones a six-second reference from Sample/2.mp4 (seconds 2-8) to Hindi. Reference
cleanliness, cross-language pronunciation/prosody and engine limitations are
hypotheses, not verified causes. Voice mastering also applies dynamic compression
and a boosted high-pass overlay; those effects can influence perceived timbre.
Playback speed adjustment cannot establish natural prosody or pronunciation.

A controlled listening diagnostic preserves the same original Hindi synthesis
but bypasses EQ, compression and tempo adjustment; it applies only the existing
measured loudness normalization for audible playback. Retained as
`hi-generation-only-louder.wav` in the original review folder. This isolates the
additional effects from generation while keeping source text, model and reference
unchanged. Loudness normalization itself remains processing; this is not a claim
of completely unprocessed audio. Listening comparison is required before blaming
any one stage or changing its defaults. No new engine/tool/package was installed.

#### Generation-level diagnosis after effects bypass

The user heard **no change** in the generation-only, volume-adjusted diagnostic.
This weakens the hypothesis that added EQ/compression/tempo processing is the
primary cause. Generation/reference quality is now the leading investigation;
this feedback alone does not prove a particular model/reference defect. Raw
synthesis quality remains unaccepted, so further tempo tuning is suspended.

New `dev/compare_voice_naturalness.py` prepares three actual offline XTTS cases:
current settings (.75 temperature, sentence splitting on), lower temperature
(.45, splitting on), and unchanged temperature with sentence splitting off.
Same Hindi text, six-second reference, seed 1234, CPU model and speed 1.0; the
seed is reset for each case. These are controlled setting comparisons, not a
promise of bitwise reproducibility or that lower temperature sounds better.
Each listening file receives only measured loudness adjustment; original raw
synthesis is retained alongside it. No added EQ, compression or tempo adjustment.
The owned review directory is published only after all clips pass content and
timeline validation. Production defaults and personal settings are untouched.
No new tool, framework, model or package is introduced. Real execution and user
listening acceptance will be recorded separately in the following entry.

Fresh generation comparison completed offline in **142.719 s**; workspace
removed. Review folder: `validation/2026-10-04-naturalness-89c0716e/`; receipt:
`2026-10-04-naturalness-comparison.json`. Baseline: 4.842 s, -15.46 LUFS,
-1.48 dBTP; lower temperature: 5.144 s, -14.87 LUFS, -1.49 dBTP; unsplit:
4.842 s, -15.46 LUFS, -1.48 dBTP. A -14 LUFS target did not yield exact
loudness equality; the achieved 0.59 LUFS difference is recorded rather than
claiming perfectly matched playback. Raw/listening files remain retained.

For this text, splitting yielded one chunk. Baseline and unsplit **raw WAV
SHA256 are identical**:
`8ACAFFFC53ECEEA7EDB8F092354C770F47A0A9FD96256AB431B8994CEF0550FF`.
Thus sentence splitting did not alter this particular synthesis. Lower
sampling temperature produced a different, slightly longer result; duration
is not a naturalness verdict. Present only baseline/lower-temperature for
listening, avoiding a redundant identical sample. No production inference
settings changed. Naturalness remains pending; there is no evidence yet that
these settings resolve the user's concern. Backend code is unchanged since
its 460-check validation; this added isolated diagnostic does not require
repeating the full mocked suite or refreshing the unchanged application copy.

#### User-requested three-second pace comparison

The user rejected both fresh generation candidates as similarly artificial and
felt they were slower. They explicitly requested a faster clip around 1-3 s.
Prepared a **2.994 s** comparison from the fresh 4.842 s baseline using existing
FFmpeg atempo **1.614x**, preserving pitch and retaining the full speech without
slicing words. Selected the upper end of the requested range for this sentence.
File: `validation/2026-10-04-naturalness-89c0716e/hi-three-second.wav`.
Receipt: `2026-10-04-three-second-preview.json`. Content and expected duration
validated before atomic publication; workspace removed. No production tempo cap
or language default was changed: this explicit listening experiment exceeds the
pipeline's 1.3x automatic fit cap and is not acceptance of that broader change.

Measured loudness after adjustment: **-18.12 LUFS / -1.50 dBTP**, despite the
normalizer's -14 LUFS target. Thus this preview is not loudness-matched to earlier
accepted-volume samples; short speech normalization still needs refinement.
This limitation is recorded rather than asserting unchanged perceived volume.
Naturalness remains rejected for prior candidates and pending for this requested
pace preview; duration reduction alone cannot establish natural voice quality.
No model/tool/package was added and original samples remain preserved.

#### Detailed user review isolates the final Hindi word

The user rejected the three-second version as too fast, then clarified that
`सुप्रभात`, its pause, and `यह एक छोटा परीक्षण` sound good; specifically `है`
is stretched and sounds casual/unnatural. This supersedes a blanket judgment
that every part of the line needs regeneration or acceleration. Preserve the
good opening/phrase; investigate final-word prosody rather than total duration.

Prepared `hi-shorter-hai.wav` from the earlier moderate-paced
`hi-louder-faster.wav`. The ending from approximately 2.880 s is accelerated
1.35x with pitch-preserving existing FFmpeg; an 8 ms crossfade joins it to the
unchanged prefix. The first **2.872 s are byte-identical PCM** to that source,
verified before publication, so earlier speech/pause/volume are preserved.
Duration **4.201 -> 3.837 s**; measured **-14.20 LUFS / -1.29 dBTP**.
No global normalization, EQ, compression or additional opening tempo change.
No hard truncation of speech; crossfade affects only the tiny edit junction.
Receipt: `2026-10-04-shorter-hai-preview.json`; owned workspace removed.

The 2.880 s boundary is an approximate final-word boundary from the earlier
low-confidence recognition, **not verified alignment**. It may include part of
the preceding word; listening confirmation is required before calling this a
successful isolated `है` correction. This is a retained manual diagnostic, not
an automatic production word-editing feature. Production defaults remain
unchanged. Original and all earlier comparison files remain retained. No tool,
model or package was installed. Broad naturalness and full dubbing acceptance
remain open; the user has now identified specific good and bad portions.

#### User-requested additional 15% / 20% tempo comparisons

The user found the ending-focused preview slow and requested a further .15 or
.2 speed increase. Interpreted explicitly as **15% / 20% faster** on the whole
latest `hi-shorter-hai.wav` preview, including its existing ending edit. Produced
two separate existing-FFmpeg pitch-preserving atempo outputs (1.15x and 1.20x),
with no additional EQ, compression or loudness normalization. Full input speech
is time-compressed without hard trimming. Both pass nonzero-content and expected
duration validation (100 ms tolerance) before atomic publication. Measurements
and durations: `2026-10-04-hindi-plus-15-20-preview.json`. Owned workspace removed.
Original and preceding comparisons retained. Naturalness/listening acceptance
pending; production speech-rate settings and automatic fit caps unchanged.

The user requested .22 next. Prepared **1.22x** of the same ending-focused
base preview (not an extra 22% on the already accelerated 20% file), preserving
pitch and all input speech. Retained as `hi-shorter-hai-plus-22-percent.wav`.
Content/duration validated before atomic publication; measurements and exact
duration in `2026-10-04-hindi-plus-22-preview.json`. No further loudness/EQ/
compression adjustment; no new packages/tools or production-default changes.
Owned workspace removed. Listening acceptance remains pending.

#### Preferred Hindi listening reference

The user reviewed `hi-shorter-hai-plus-22-percent.wav` and said **"this looks
much much better"**. Record it as the **preferred comparison sample** and a
substantial perceived improvement for this specific line. Its receipt now
preserves that exact feedback and acceptance scope. This is not full acceptance
of pronunciation, speaker similarity, all Hindi lines or final mixed renders.

The successful reference combines two edits: the approximate final-word region
was shortened 1.35x, then the resulting whole preview accelerated 1.22x. Therefore
it is not evidence that a plain global 1.22x setting reproduces the result for
unaltered synthesis. Earlier accepted portions were preserved in the ending
edit, then received the requested whole-line pace adjustment. No production
setting has been changed and no general automatic word alignment is implemented.
Use this retained clip as the next listening target; validate longer/diverse
Hindi lines and sentence endings before promoting a production policy. Existing
word-preserving fit guard remains in place. Broad architecture/media quality
acceptance is still in progress.

#### Longer Hindi validation against the preferred listening target

The user authorized the next check. `dev/verify_long_hindi_voice.py` generates
two longer prepared Hindi passages using the same existing offline XTTS model,
six-second reference, CPU and seed 1234. One passage ends in `चाहिए`, the other
in `है`; both contain two sentences. These texts isolate voice delivery from
translation quality and are not a human-certified translation corpus.

The preferred short clip already had a 1.1x overall adjustment before the
additional 1.22x. Therefore the longer diagnostic applies **1.342x** overall
pace (1.1 * 1.22) to mastered fresh synthesis, rather than misrepresenting a
plain 1.22x raw-output setting as an equivalent pace. It does **not** automatically
edit the final word: the earlier approximate manual boundary cannot be safely
transferred to new speech. Preserve raw, mastered original-pace and adjusted
listening files. Validate content/timeline before publishing the complete review
directory. Production defaults and automatic timing caps remain unchanged.

Inspection of the installed upstream TTS implementation confirms its synthesizer
initializes an English sentence segmenter; Hindi preprocessing uses basic
cleaning rather than language-specific expansion. The earlier Hindi short text
was not split at its danda punctuation. These are observed limitations to consider
in text preparation/number reading and future sentence handling, not proof that
they caused the stretched `है`. No upstream package was modified or installed.
The current prepared passages spell out their time rather than testing digits.

Longer Hindi execution completed successfully; see
`2026-10-04-long-hindi-voice.json` for exact total elapsed time and owned review
folder. First passage: **7.779 -> 5.778 s**, -15.50 LUFS / -1.47 dBTP,
case time 61.453 s. Meeting passage ending in `है`: **8.987 -> 6.685 s**,
-14.87 LUFS / -1.45 dBTP, case time 73.172 s. Both used whole-line 1.342x
pitch-preserving adjustment, retained complete input speech without hard
truncation, and passed playback and expected-duration checks. Raw and mastered
original-pace versions are preserved alongside listening candidates. The
upstream splitter again returned one chunk for each multi-sentence Hindi text.
Workspace removed. All actual achieved loudness values are recorded; targets
are not claimed to be exact or perfectly matched. No ending-specific edits or
production settings changed. User listening review of longer-line pace,
pronunciation and final-word naturalness is pending. Successful file generation
is not full Hindi voice or end-to-end pipeline acceptance.

#### Approved Hindi pacing applied to production dubbing

The user approved both longer Hindi samples (`so good`) and explicitly authorized
applying their pace to Hindi dubbing while retaining word-preserving safeguards.
The longer-sample receipt now records that listening approval and its limited
scope. Production `_dub_segment_bound` uses **1.342x pitch-preserving tempo**
for resolved Hindi (`hi`) after existing voice mastering, reproducing the overall
1.1 * 1.22 pace from those longer approved clips. It applies in the shared audio/
video dubbing path, including source-language passthrough resolved to Hindi.
Other languages retain their existing timing behavior. All voices routed through
Hindi dubbing receive this policy; the actual listening evidence is for the
recorded XTTS/reference cases, not untested cloud voices or converters.

Hindi is no longer slowed to fill a spacious cue. It keeps that reviewed rate
when a gap provides extra room, and does not exceed it to force an overlong line
into a short slot. The existing guard still refuses audible overflow and allows
removing only an exactly silent tail. It never automatically transfers the
short clip's approximate `है` edit to new sentences. No new model, tool,
framework or package was added, and no user model/sample/output was deleted.
This change is a deliberate approved language-specific production default,
not a generic claim of perfect naturalness or a duration-aware translation fix.

Targeted speech/parallel/dry-run checks: **61 PASS in 20.848 s**
(`2026-10-04-hindi-pacing-checks.log`). New meaningful regressions use real
FFmpeg tempo to verify Hindi short speech stays brisk in a spacious cue,
uses available gap without extra acceleration, and rejects overlong words at
the approved pace. Existing English timing and sequential/parallel failure
contracts remain covered.

`dev/verify_hindi_pacing.py` replayed retained actual XTTS synthesis through
production segment mastering/timing. Both outputs **match the approved longer
previews exactly in PCM, channel count, sample width and sample rate**:
5.778 s and 6.685 s. Receipt: `2026-10-04-hindi-production-pacing.json`;
owned workspace removed. This is real audio-processing integration acceptance
with a cached synthesis adapter, not fresh engine inference or acceptance of a
complete transcription/translation/render workflow. The previously failed
news-dubbing fixture remains a known separate timing/translation gate until
rerun and resolved. Full regression verification follows below.

Final Hindi pacing regression verification: **463 PASS in 73.201 s**
(`2026-10-04-hindi-pacing-backend.log`), including approved temporary loopback
HTTP fixtures. Whitespace diff validation passed. Owned portable QA application
refreshed: **167 files**, zero size mismatches, acceptance true; the original
runtime remains preserved. Frontend unchanged, so retained 83-check/build
validation is still the relevant UI evidence. No commit, push or release made.
This completes the specifically approved Hindi pacing integration; full product
readiness, duration-aware translation, and cross-engine/platform acceptance
remain open as documented.

#### Failing translation/timing unit reviewed with existing tools

The user authorized reviewing the failing line and testing a natural concise
Hindi version at the approved pace. Detailed findings and limitations are in
`TRANSLATION_TIMING_REVIEW_2026-10-04.md`. Existing tiny Whisper with 15 seconds
of source context now recognizes `Before long`, whereas the prior short raw
transcript read `Before a longer-standard`. The first complete sentence spans
0-6.300 s; its continuation had been split after `immediately`, and the next
report introduction starts at 6.660 s. Exact separated-source transcript from
the failed run was not preserved; do not conflate it with the older raw receipt.
Source accuracy remains subject to human review.

Fresh NLLB on the complete sentence produced an improved but awkward Hindi
translation. Actual XTTS + production mastering/approved Hindi pace fits it in
**6.009 s**. A proposed manual concise translation fits in **5.030 s**:
`जल्द ही खबरों की एक तय दृश्य शैली बनी, जिसे सब तुरंत पहचान लेते थे।`
Both are below the next-cue start at 6.660 s, preserve all generated speech, and
use no guessed final-word edit. Neither is claimed to fit the original incomplete
4.880 s cue. Execution **77.937 s**, workspace removed; receipt:
`2026-10-04-failing-line-review.json`. This demonstrates full-sentence context
and timing plus concise wording, not an automatic production translation fix.

The concise candidate was mixed on the original 6.660 s sentence timeline with
the retained Demucs background using the production dynamic mixer. Background
separation was not rerun. Mix level **-12.09 LUFS / -1.46 dBTP**; decoded duration
6.660 s, foreground 5.030 s. Source sentence, isolated candidate and mixed
candidate retained in `validation/2026-10-04-line-review-76b5fc7e/`. Receipt:
`2026-10-04-failing-line-mix.json`; workspace removed. Measured final level differs
from the isolated voice (-15.19 LUFS), so do not claim loudness equality.
Wording/pronunciation, perceived volume and residual original speech require
listening; source speech after the Hindi line ends is a relevant review point.

No production cue-merging or translation rule was added, no tool/model/package
installed, and original failure receipts/outputs retained. The earlier unchanged
automatic eight-second workflow is still not accepted by this manual review.
General correction needs complete-thought grouping with bounded timing and
reviewable text, rather than one hard-coded translation or arbitrary truncation.
Existing 463 backend checks remain the latest production evidence; only isolated
review scripts/docs changed in this step, so the full suite was not redundantly
rerun. No commit, push or release made.

#### User rejects choppy final words; background leakage check passes

The user confirmed no original English is audible underneath the mix, but
reported robotic delivery in the final three/four words, with abrupt transitions.
Record **background leakage review passed for this preview**, **ending delivery
rejected**, and overall mix quality still unaccepted. The mix receipt stores
these separate verdicts; it does not turn a background pass into a voice pass.

This sentence preview had no manual per-word edit. Energy analysis of raw and
paced speech finds internal quiet intervals in the original synthesis too;
`2026-10-04-robotic-ending-gap-analysis.json` records durations, a -40 dBFS
threshold and minimum 70 ms silence. These are not verified word boundaries.
Mastering changes threshold crossings, so interval positions/counts cannot
alone prove an exact cause. Do not automatically delete gaps: stop consonants,
breaths and natural pauses also contain low energy. Generation is a leading
hypothesis, while raw-versus-paced listening remains necessary.

`dev/review_failing_translation.py --ending-review` now preserves the original
raw speech with only loudness adjustment for comparison, generates the same
words with seed 7 instead of 1234, and generates the proposed simpler ending
`जिसे हर कोई तुरंत पहचान सकता था` using the original seed. Same XTTS/reference,
temperature .75, production mastering and Hindi 1.342x pace. The new variants
are diagnostic; no production seed, translation or pause-deletion rule changes.
Both still must fit before the 6.660 s next cue; failures remain preserved as
raw samples rather than cutting words. Separate receipts preserve earlier tests.

A future alternative was researched only: AI4Bharat's official IndicF5 README
lists Hindi among supported languages and requires reference audio plus its
transcript. The official Hugging Face model page currently gates file access
behind acceptance/contact sharing. No download, term acceptance, contact sharing,
remote-code execution or new installation was performed. This candidate is not
quality-accepted on this machine, and requires the user's approval/access before
any new engine work. Sources: https://github.com/AI4Bharat/IndicF5/blob/main/README.md
and https://huggingface.co/ai4bharat/IndicF5 . Existing-stack diagnostics continue.

#### Real ending comparison exposed a loudness boundary failure

The first fresh-reading case fitted in **4.839 s**, but the following simpler
ending failed the mastering boundary with `invalid loudness or excessive true
peak`. Run **144.188 s**, workspace removed; preserved pre-fix receipt/log as
`2026-10-04-robotic-ending-review-before-peak-fix.*`. The old combined error did
not record measured values, so it does not by itself prove which measurement
triggered rejection. Earlier raw review files were lost when this all-or-nothing
diagnostic failed before publishing; that diagnostic retention gap is now fixed.
Future failures preserve only the owned generated review folder and its path,
without touching original media or runtime files.

`core/loudness.py` now handles a finite measured true-peak overshoot by reducing
only output gain by the measured excess plus 0.05 dB, then measuring again before
publication. The original peak rejection threshold (-1.5 dBTP + 0.3 dB tolerance)
is unchanged; invalid measurements or remaining excessive peaks still fail.
Gain adjustment preserves pitch, duration, pauses and audio format. This is a
level-handling repair, not a prosody/naturalness fix. `master_voice_segment` now
returns its existing normalization receipt so diagnostics can preserve actual
achieved levels and any correction. Existing production callers ignore that
return value, as before.

Focused checks **60 PASS in 19.786 s** (`2026-10-04-peak-correction-checks.log`)
include a simulated converter overshoot with **real** FFmpeg measurement and
real PCM gain correction, verifying peak and unchanged timeline/rate. The
simulation is not presented as a second real engine failure. Fresh ending
inference is being rerun, with separate full regression verification. These
short tests may overlap the inference run; timings are operational observations,
not controlled CPU performance benchmarks. No new dependency/tool/model added.

#### Ending candidates completed after peak correction

Rerun completed in **122.875 s**, workspace removed; receipt
`2026-10-04-robotic-ending-review.json`; retained directory
`validation/2026-10-04-ending-review-1c0cd47b/`. Same-words fresh reading (seed 7)
fits in **4.839 s**, measured -15.14 LUFS / -1.50 dBTP. Simpler proposed ending
`जिसे हर कोई तुरंत पहचान सकता था` (seed 1234) fits in **5.030 s**, measured
-15.49 LUFS / -1.79 dBTP. Both use existing production mastering/Hindi pace and
retain complete generated words within the 6.660 s window. No automatic pause
removal or guessed word edit; no production translation/seed change. Generation
alone, raw variants and fitted variants remain available for review. Naturalness
and revised wording acceptance remain pending.

The actual simpler-ending rerun required **0.44 dB** true-peak gain correction;
after mastering it measured -1.55 dBTP, and after tempo -1.79 dBTP. This confirms
that the new correction branch handled an actual finite peak excess, while the
original failed receipt lacked sufficient measurements to independently identify
its exact trigger. The fix preserved duration and all pause locations. It is
not evidence that the choppy prosody was repaired; that requires listening.

Full regression verification: **464 PASS in 82.713 s**
(`2026-10-04-peak-fix-backend.log`). The approved temporary loopback HTTP fixtures
were included. Inference and some short regressions overlapped; elapsed times
are not controlled benchmark results. Latest portable QA refresh covers 167
application files with zero size mismatches. Original runtime/models/media remain
preserved; no new dependency, model, commit, push or release. Broad product and
automatic translation/timing acceptance remain open.

#### Selected fresh reading accepted and mixed

The user accepted the **4.839 s fresh-reading** candidate: `the 4.84 second one
is actually good`. Its case receipt now records voice-delivery listening
acceptance and selection for this sentence, while source/translation semantic
certification and general model naturalness remain open. The simpler-ending
candidate was not selected. Do not turn one seed-7 success into a new fixed
production seed or an automatic naturalness guarantee.

The exact accepted fitted voice is reused, without rerunning inference, in
`fresh-reading-selected-mix.wav`. Production dynamic mixing combines it with
the preserved background on the **6.660 s** original sentence timeline; no hard
speech truncation, no change to the next cue's start, and no new separation.
Measured mix **-12.11 LUFS / -1.49 dBTP**, sample peak -1.496 dBFS; exact dialogue
length 4.839 s. Receipt: `2026-10-04-selected-sentence-mix.json`; workspace removed.
The prior background mix passed leakage listening review, but this selected
mix still awaits its own full listening approval. Every earlier candidate,
original sample and failure receipt is retained. Production generation settings
remain unchanged; approved Hindi pacing remains in place. No new tools/models/
packages, commit, push or release. Core unchanged since the 464-check pass.

#### Correction: source excerpt has no music or ambience

The user corrected the background description: **no music or ambient sound was
present** in the excerpt. The assistant had incorrectly described the Demucs
residual/background-labelled stem as verified music/ambience. A separator's
non-vocal stem name does not establish its semantic content; it may contain
residual speech/noise or separation artifacts. Retract that description. The
prior comment that no original English was audible concerned leakage in that
specific playback, not proof of actual background music in the source.

For this reviewed sentence, supersede the residual-stem mixed candidate with
`fresh-reading-selected-voice-only.wav`. It preserves the **accepted 4.839 s
voice exactly in PCM** and fills the remainder of its **6.660 s** original
sentence window with **verified exact digital silence**. No separated track,
new music/ambience, gain change or voice regeneration. Receipt:
`2026-10-04-selected-voice-only.json`. The preceding mix receipt is marked
superseded for this review, and the original mixed file remains preserved as
historical evidence. Production background settings/features remain unchanged;
this correction applies to the particular reviewed excerpt, not all projects.
No core changes since the 464-check pass; no new tool/model/package/commit/release.

## 2026-10-04 — bounded sentence grouping and automatic reruns

Implemented conservative single-voice source continuation joining before translation in both audio/video paths. The previous cue need no longer be under 2.5 seconds when it lacks terminal punctuation and the next cue begins lowercase. Existing 0.6-second gap / nine-second combined-window limits remain; overlaps and known speaker differences reject every join. Multi-voice additional joining is disabled to preserve current alternating cue assignments. Input dictionaries and detected-language metadata are preserved. No new engine/dependency or Hindi pace/loudness change.

Five new regression tests cover the recorded fragment, punctuation/quotes, pause/length/overlap and speaker boundaries, voice-count behavior and metadata/immutability. Initial test setup omitted an explicit source language; corrected the fixture without weakening production guards. Complete suite: 469 PASS in 98.596 seconds (`validation/2026-10-04-sentence-grouping-backend.log`). Refreshed only the owned portable QA app: 167 files, no size mismatches.

Enhanced real-workflow receipts with separately labelled runs, grouped source/translated cues and progress retained on failures. Explicitly changed audio duration requires a separate label. Original default eight-second fixture preserved. Eight-second rerun FAILED before grouping: recognition segment three outside media bounds (158.453 seconds, owned workspace removed). Fifteen-second profile FAILED overall (178.750 seconds): first complete sentence 0–6.520s now passes automatic speech timing; cue two needs 3.143s in a 2.720s window. Recognized source 'Me, has this report.' remains suspect. No manual text substitution, no word cutting, no extra Hindi acceleration, no final output. This is evidence of a specific first-cue repair, not full automatic or semantic-quality acceptance.

Full explanation and remaining gates: `SENTENCE_GROUPING_ITERATION_2026-10-04.md`. Updated product/release readiness. Recognition correction, per-cue audition/regeneration, current full media/platform acceptance and remaining release gates stay open. No commit, push or release.

## 2026-10-04 — single-voice audio correction, audition and accepted-take assembly

Added `core/cue_review.py`, typed bridge endpoints and Dashboard review controls using the existing stack. Preparation publishes a complete source/vocals/background/reference snapshot and translated cues under owned `outputs/cue-reviews/<id>`. Users edit recognized/speech text, retranslate a corrected cue, generate candidates, listen, accept fitting takes and assemble the exact saved accepted audio. Editing invalidates only that cue; failed or overlong regeneration preserves its previous accepted take. Audition-only overflow is explicit; normal production fitting remains strict. Final assembly requires every cue accepted, verifies saved hashes and source timing, and publishes one new WAV without rerunning STT/translation/separation/speech. Single voice/audio only: video, timing edits, stems and multi-speaker review remain open.

Persistence: atomic snapshot/manifest publication, revision checks, per-instance render lock, existing cancellable worker/cleanup, owned asset paths/reparse rejection, SHA-256 audio checks, bounded base64 WAV preview transport, no stored provider credentials. Configuration digest detects model connections/active settings changes; prepare a new review after a change. Records/takes survive temporary cleanup/restart; no auto-pruning/deletion UI or list pagination beyond the most recent 50 reviews. Concurrent separate app instances sharing storage remain unvalidated.

Added ten review regressions plus one production/audition timing regression. Initial backend 480 PASS/81.319s; final after preview-size and provider-lifetime fixes 480 PASS/89.524s (`2026-10-04-cue-review-backend-final.log`). All existing 83 frontend checks rerun passed; final TypeScript/Vite build passed (large-bundle warning remains). Model providers now release before stage garbage collection and the bridge collects after review operations; no measured latency reduction/admission guarantee claimed. QA app inventory168 files/no mismatches; only stale generated assets removed from that owned copy.

Real offline truncated15s review failed recognition bounds, preserved separately. Complete Sample2 (122.531708s), CPU, explicit voice-only review profile produced21 review cues and2 playable candidate files in708.156s. Cue1=6.565s in6.640s fits; cue2=9.098s in2.600s unfit and unaccepted. Suspect recognition/awkward translations remain; no human acceptance and no final output. Workspace removed; durable diagnostics retained under docs/validation/2026-10-04-cue-review-runtime. This fixture's explicit engine connections do not alter production state.

Desktop checks retained failures and repaired same-value selection/editor clearing. An intermediate apparent control PASS had null duration because the test's NaN comparison was insufficient; superseded and not audio acceptance. Strict HTMLAudio metadata stayed stalled in hidden tests for data/Blob URLs. Final `CueAudioPlayer` uses built-in Web Audio byte decoding and explicit play/stop, closing context/source and invalidating stale asynchronous work on changes. No dependency added. Final desktop PASS26.391s: native decoder reads1.500s syntheticWAV, stop, acceptance persistence, overlong/incomplete blocking and isolated edits, no JS errors. Hidden QA bypasses only context-resume gesture permission and suppresses audible output. Audible visible-app playback/layout and human voice quality remain unverified. Finalcodecopy refreshed.

Detailed changes/evidence/limits: docs/CUE_REVIEW_ITERATION_2026-10-04.md. Product/release readiness updated. Automatic full dub, reliable recognition/translation/voice delivery, CPU latency, video/multi-speaker review and remaining distribution/platform gates remain open. No new tool/framework/engine/model download, commit, push or release.

## 2026-10-04 — cue review correctness and retained audio audit

Fixed accepted-take assembly being blocked by changed model settings, revision commits racing across cooperating processes, and insufficient saved-record validation. Reused the installed JSON persistence lock; no dependency added. Long operations recheck expected revision under the commit lock. Validated finite ordered cue timing, windows and take metadata; accepted overflow and unsafe asset names are rejected. Competing subprocess regression proves exactly one writer wins. Existing real 21-cue review remains readable.

Focused 13 PASS/12.839s; full backend 483 PASS/66.201s. Refreshed 168-file QA app with no mismatches; hidden desktop PASS/21.688s, native 1.500s decode, stop, acceptance, isolated edits and overflow/incomplete blocking. No audible or visual acceptance claimed. Frontend unchanged; retained prior 83 checks/build. Receipts use cue-review-audit names, preserving earlier evidence.

Retained cue2 is 9.098s for a 2.600s window, with 8.10s activity above -45dBFS and only 0.478s trailing quiet: tail trimming cannot repair the overflow. Waveform measurements do not prove naturalness, words or semantic quality. Cleaned reference119.204s has not been verified as clean single-speaker audio. Fresh provider setup repeats per regeneration; no measured optimization claimed. Video still regenerates its own speech and does not consume accepted review takes. Detailed scope, findings and remaining gates: CUE_REVIEW_AUDIT_2026-10-04.md. No new engine/model download, commit, push or release.

### Controlled reference follow-up — 4 October 2026

Existing offline CPU XTTS comparison completed in200.937s using the same Hindi text, seed1234, temperature.75 and approved1.342 pace. Saved full reference produced6.868s; a cleaned6.640s first-cue reference produced4.202s; repeating the short reference yielded identical raw/processed hashes. Neither fits the2.600s slot. Model loading39.031s once; synthesis72.563s/full and34.531–42.735s/short. Installed XTTS caps conditioning at30s despite the119.204s saved reference. Naturalness, reference cleanliness/speaker identity and translation meaning still need listening review. No production settings/cache/new tool/model download changed. New diagnostic script dev/compare_review_reference.py and detailed report VOICE_REFERENCE_COMPARISON_2026-10-04.md; receipt validation/2026-10-04-reference-comparison.json. Prior backend483/UI evidence retained, no new production edits. Release decision remains not ready.

### Speech intelligibility rejection and diagnostic controls — 4 October 2026

User rejected both reference comparison takes: "both are gibberish after first 2-3 words". Recorded rejection in the original comparison receipt/report; duration reduction and repeat hashes are not quality success. Follow-up with unchanged offline XTTS and exact reference from earlier approved Hindi cases completed131.719s, model load37.360s: Hindi seed1234 raw4.238s/paced3.143s, seed7 raw4.436s/paced3.293s, English control2.172s. Tokenizer round-trips retain full input with zero unknown tokens. All WAVs decode, workspace removed. Listening to raw Hindi versus processed and English is pending; no root cause or quality fix claimed. Both Hindi controls still overflow2.600s. Added dev/diagnose_review_speech.py, detailed SPEECH_INTELLIGIBILITY_DIAGNOSIS_2026-10-04.md and separate speech-diagnosis receipt/log/audio. No production settings/new tool/engine/download/accepted audio changed; prior backend483/UI evidence retained. Release remains not ready.

### Hindi delivery clarification and controls — 4 October 2026

User clarified latest Hindi: "Words are clear; delivery sounds artificial"; English accepted for the specific control. Updated speech-diagnosis receipt/report without marking overall quality accepted. Added dev/compare_hindi_delivery.py: same reference/text/seed/approved pace, compare existing raw take with loudness only (without existing EQ/compression), and temperature0.90 with otherwise existing mastering. Completed69.406s/load37.844s/new synthesis26.750s. No-EQ/compression3.143s; sampling variant3.105s; both still overflow2.600s. Raw/mastered/listening controls retained, workspace removed, decoding/whitespace checks passed. Listening pending; no naturalness improvement claimed or default promoted. Full evidence HINDI_DELIVERY_COMPARISON_2026-10-04.md and hindi-delivery receipt/log. No production/new dependency/model download changes; prior backend/UI evidence retained.

### Preferred Hindi B and longer-passage gate — 4 October 2026

User chose B (temperature0.90) in the short delivery comparison. Preference recorded, not global naturalness acceptance. Tested same sampling candidate on earlier approved longer quality text/reference/seed/mastering/pace. New diagnostic dev/compare_long_hindi_delivery.py completed107.563s/load37.532s/synthesis64.516s; raw8.836s/paced6.565s, saved baseline5.778s. WAVs decode; workspace removed. Log shows Hindi danda-separated sentences remain one split entry despite split_sentences=True; cause of artificial delivery unproven and no punctuation conversion added. Listening pending, no default/accepted take/engine changes. Evidence appended to HINDI_DELIVERY_COMPARISON_2026-10-04.md; long-hindi-delivery receipt/log/audio preserved separately. No commit/push/release.

### Mid-passage slowdown and negative boundary control — 4 October 2026

User reports longer B good until middle, then slowed; whole-passage quality unaccepted. Installed synthesizer uses English segmenter and ignored danda for sentence splitting. Diagnostic --sentence-boundaries changes engine-input danda to periods, confirms2 entries, preserves words/reference/seed/temp0.90/mastering/pace. Run145.547s, load37.250s, synthesis100.750s, final10.368s versus previous B6.565s. Activity above-45dBFS9.290s versus5.960s: increase not solely pauses; no word alignment or human quality claim. Negative timing result, no rollout. Artifacts and HINDI_SENTENCE_BOUNDARIES_2026-10-04.md preserved; prior feedback receipt updated. Next controlled input needed: short reviewed human Hindi reference; existing controls use English source audio, causal role unproven. No production defaults, dependency/model download, accepted files, commit/push/release changed.

### Supplied Hindi references — 4 October 2026

User provided Downloads/Hindi_F_Sujata.mp3 and HIN_M_AbhishekS.mp3. Read-only originals, copied and converted complete17.528s/19.775s recordings to mono24kHz references (no guessed cuts/trim/EQ/reference normalization). Same longer text, seed1234/temp0.90/mastering/approved1.342 pace. Added dev/compare_native_hindi_references.py. Completed186.453s, load38.125s once; Sujata raw9.393s/listening6.987s/synthesis74.532s; Abhishek raw7.327s/listening5.445s/synthesis63.454s. All output decodes/signals; original hashes unchanged; workspace removed. Listening pending, shorter length is not quality evidence. Original punctuation remains1 engine entry; failed boundary route not adopted. Detailed NATIVE_HINDI_REFERENCE_COMPARISON_2026-10-04.md plus native-hindi receipt/log/audio. No production defaults/reference policy/cache/dependency/model download change, commit/push/release. Prior regression receipts retained as production unchanged.

### Residual Hindi noise/distortion — 4 October 2026

User positively received both supplied-reference takes but reports little noise/distortion; final acceptance pending. Added dev/compare_hindi_noise.py, reuses verified raw speech with existing loudness/approved tempo but removes extra EQ/compression, no new inference. Level audit: raw one full-scale sample each/+0.03dBTP; all mastered/paced files zero full/near-full-scale samples, baseline finals -1.50/-1.38dBTP. No sustained final saturation established; root cause remains unresolved. Alternative finals -1.50/-1.51dBTP, Sujata6.988s versus6.987s, Abhishek5.445s both. Completed6.344s, all decode/timing/hash/cleanup checks pass. HINDI_NOISE_REVIEW_2026-10-04.md plus hindi-noise receipt/log/audio; native feedback recorded. No production/new tool/denoiser/model download changes; previous baseline/user originals preserved. Listening pending; no claimed denoising/quality fix.

### Localized Hindi artifacts and raw control — 4 October 2026

User locates distortion at Sujata start and Abhishek ending after no-EQ/compression comparison; route not accepted as repair. Added dev/audit_hindi_edges.py; actual raw/processed edge audit saved finite JSON. Sujata first sample0.01071 raw/0.01370 processed; potential small boundary step does not prove audible complaint. Abhishek last250ms exact silence and finalsample0, so reported ending not explained by abrupt file endpoint. Both last100ms jumps0. No speculative fade/gate/word cuts applied. Exact raw synthesis (before loudness/mastering/tempo) provided next to distinguish synthesis/reference from postprocessing; naturally longer9.393s/7.327s, no default-pace rollback. HINDI_NOISE_REVIEW_2026-10-04.md and hindi-noise feedback receipt updated. Original audio/defaults/models unchanged; no new inference/tool/download; regression evidence retained.

### Raw Hindi listening accepted; processing isolation — 4 October 2026

User accepts both exact native-reference raw takes: "both are beautiful". Receipt records raw-specific acceptance for this passage/two references; processed derivatives remain reported distorted. This implicates processing for these cases, not a universal generator failure. No-EQ/compression derivatives still used loudness normalization plus tempo, so cannot yet attribute defect to one. Next existing loudness-only/unpaced controls isolate normalization, retaining raw9.393s/7.327s and original speech. No regeneration/default/reference/pace-policy change; next listening gate pending. HINDI_NOISE_REVIEW_2026-10-04.md updated; original audio preserved.

### Tempo-stage isolation and bundled alternate — 4 October 2026

User confirms both loudness-only takes clean like raw. Case-specific contrast isolates added atempo1.342 as stage associated with rejected distortion; not universal algorithm failure. Existing FFmpeg lists rubberband/help confirms tempo/pitch; no installation. Added dev/compare_hindi_tempo.py, same inputs, rubberband tempo1.342/pitch1 defaults, safety gain only on overshoot. Completed2.593s; Sujata6.999s versus6.988s, TP-1.55/LUFS-16.62/gain-0.54dB; Abhishek5.460s versus5.445s, TP-1.59/LUFS-16.32/no correction. Levels differ; no perfect loudness-match/quality/pitch proof claimed. Decode/duration/cleanup/whitespace pass. HINDI_TEMPO_COMPARISON_2026-10-04.md and hindi-tempo artifacts. Listening pending, production unchanged, prior tests retained. No inference/models/new tool/download/commit/push/release changes.

### Accepted speech tempo repair in production — 4 October 2026

User accepts alternate tempo clips: "beautiful". Recorded scope in hindi-tempo receipt. Replaced shared speed_change atempo with bundled rubberband tempo/pitch1; finite speed validation, explicit sample format, duration/signal validation, measured gain-only headroom correction, actionable unsupported-filter error without fallback. Existing pace/timing guards/model/reference/mastering/generation defaults unchanged; no new installation. dev/verify_production_tempo.py reproduces both accepted samples byte-for-byte PCM. Four meaningful regressions added: pitch/timing/headroom, missing filter, invalid tempo and cancellation. Focused115/116 had cancellation fixture calling nonexistent cancel; corrected request_stop and failed receipts preserved. Complete487 PASS95.016s includes fix. QA168files/no mismatch, hidden cue desktopPASS30.860s/no JS errors; no audible/layout desktop claim. Frontend unchanged retained83/build; whitespace passes. Detailed SPEECH_TEMPO_FIX_2026-10-04.md, readiness/product updated. Full generation/translation/video/platform/resource gates remain open; no commit/push/release.

### Real44-second moving-video baseline — 4 October 2026

User authorized existing sample. Added dev/verify_real_video_dub.py using actual Sample2 moving frames, isolated existing Whisper tiny/NLLB/XTTS, supplied Abhishek reference, current default generation/mastering and accepted tempo; background/subtitles/stems enabled, optional lip/face/filter disabled. Elapsed572.734s; Demucs inference progress3min38s,9 recognized/translated cues. Cue1 fits5.381s/6.640s (99.985s); cue2 fails3.011s/2.600s after40.953s, guard refused word cutting. No final video. Source/ref/clean ref/separation worker log and stems/SRT/cue report/firstcue retained; workspace removed. Late raw-capture retained0, explicitly not failed-cue audio evidence. Transcript/source suspect Me hasthisreport/Next day walkie-talkie altar/fellowshot; Hindi fragmented/literal/gendered/mixed English;44s boundary clips nextsentence into0.6s cue. Sourcecue2 excerpt saved for wording clarification. REAL_VIDEO_DUB_ITERATION_2026-10-04.md details findings and reviewed-track repair sequence; readiness/product updated. No new production tool/model/default/download/commit/push/release; prior487 backend/83 frontend retained. Full mix/leak/subtitle/video acceptance and human semantics remain open.

### Bounded cue retry and proposed script review — 4 October 2026

User “ok” acknowledged, not interpreted as ambiguous source confirmation. Retained15s recognition repeats “Me, has this report”; word probability0.769 does not certify wording. Added REAL_VIDEO_SCRIPT_REVIEW_2026-10-04.md with unapplied Hindi proposals and unresolved context flags. Added offline dev/retry_real_video_cue.py: reuse saved clean reference, unchanged production defaults and tempo, two unseeded takes, diagnostic overflow retention only, no truncation/acceptance/video. Initial driver JSON read failed before inference under Windows default encoding; explicit UTF-8 fixed, failed log preserved. Completed93.953s; trial1 6.134s, trial2 5.832s, neither fits2.600s. Both raw/processed takes retained, four WAV decode checks pass, owned workspace removed. Compared with baseline3.011s this exposes generation-duration variability, not a statistical reliability estimate or established cause. No new packages/downloads/production changes; prior487/83 tests retained, not rerun. Release remains blocked on source/translation review, fitting speech and real-video completion.

### XTTS native playback rate repair and controlled duration investigation — 4 October 2026

Found installed checkpoint loader writes conditioning22050-Hz rate for native24000-Hz HiFi decoder samples; playback8.8435% longer and pitch0.91875 of native. Application TTSHandler now sets writer to validated actual loaded decoder output rate after normal/recovery initialization, no vendor/model edits. Three regressions: real decoder waveform duration/pitch, custom rate with CPU recovery, invalid metadata. First focused invocation portable import path failed before tests; original log retained, corrected81 PASS73.209s. Full backend490 PASS124.375s; QA app refreshed168 files/no mismatches. Added offline diagnose_xtts_timing.py: seed7/temp.75 clean5.291 raw/3.943 processed, exact repeat SHA/duration, unprocessed6.635/4.944, all overflow2.600s; no seeded production change. Diagnostic232.766s overlaps tests, not isolated performance. Retained native raw samples relabeled without resampling; compare_native_playback_rate.py reproduces accepted loudness-only/tempo stages with native headers: Sujata6.431 vs6.999s, Abhishek5.016 vs5.460s, LUFS close, peak differences documented. All19 new WAVs decode, originals retained, owned workspace removed. Human quality pending; defaulttemperature/tempo/mastering/ref processing unchanged. XTTS_PLAYBACK_RATE_REPAIR_2026-10-04.md and readiness/product updated; no new installs/downloads/commit/push/release. Existing real-video baseline remains failed.

### Sujata perceived echo controls — 4 October 2026

User “beautiful” on native-rate voices with residual Sujata echo. Mono chain has no explicit echo/reverb/double voice; origin remains unknown. Added dev/review_sujata_echo.py using retained waveform, no synthesis. Existing RubberBand window=short trial returns exact current WAV hash, no improvement; not promoted. Raw/native and normalized/no-tempo controls both8.630s matched−17.99/−18.00LUFS, peaks−1.73/−5.09dBTP; unchanged current6.431s retained. All inputs/results validated; raw hash matches prior receipt, temporary workspaces removed. Final sujata-echo-9a09f414 folder, earlier window-only/intermediate unmatched copies and logs preserved. SUJATA_ECHO_REVIEW_2026-10-04.md documents conditional diagnosis/listening requirement. No production/default/ref/Abhishek change, no new installs/downloads; previous490 checks retained. Full video remains failed, no release.

### Sujata opening distortion: fixed-sampling reference control — 4 October 2026

User hears little opening-word distortion in both raw/native and normalized/no-tempo controls, otherwise mostly same/good. Artifact precedes loudness/tempo; precise cause unconfirmed. Existing Coqui saver peak-normalizes to32767; baseline single full-scale sample at0.310125s does not establish sustained clipping. Added dev/review_sujata_reference.py: retained full reference through existing mono80Hz high-pass/adaptive edge trim/peak normalization, same seed1234/temp.90/text/speed1.0, native24000Hz output, accepted loudness-only and tempo1.342 stages. Reference duration17.528s unchanged; filtering/level is actual preparation difference, no removed reference speech. New raw8.118s vs8.630 baseline, processed6.049s vs6.431; final−16.56LUFS vs−16.57, TP−2.20 vs−1.55, gain+0.24dB. Synthesis68.391s; decode/timing/peak checks, retained hashes and cleanup pass. Raw and final retained in sujata-reference-d18b58a6; quality/listening pending. SUJATA_REFERENCE_CONTROL_2026-10-04.md details combined-preparation limitations, no asserted echo fix. No production/default/Abhishek/new package/model/download change;490 prior checks retained. Release/video gates remain open.

### Accepted voice examples and varied-text coverage — 4 October 2026

User “beautiful” accepts exact cleaned-reference Sujata6.049s take. Acceptance receipt updated; record_hindi_voice_acceptance.py records exact hashes/settings/listening scopes alongside earlier native Abhishek, not all-text or video approval. Added verify_hindi_voice_coverage.py: question, negation, time/long clause for each voice, one cached existing CPU model, seed1234/temp.90/native24k/loudness-only/tempo1.342; Sujata cleaned reference, Abhishek unprocessed reference, hashes preserved. Completed204.703s/model14.969s/synthesis174.092s, six cases pass decode/timing/peak,20 generated WAV decode checks, workspaces removed. Sujata final4.181/3.840/5.286s; Abhishek3.871/6.121/4.388s; long Abhishek negation flagged for listening, not discarded or forcibly shortened. Review montages15.107/16.180s include900ms separators, actual LUFS−16.50..−17.68 so no perfect-level-match claim. Detailed HINDI_VOICE_COVERAGE_2026-10-04.md and receipts preserve full raw/norm/final. Production remains .75/unseeded/additional mastering; diagnostic profile not silently promoted. Human coverage acceptance pending, previous490 checks retained without rerun. No new installs/downloads/commit/push/release; real-video baseline still failed.

### Varied-text listening rejection and exact raw controls — 4 October 2026

User reports both voices have distortion/stutters. Batch receipt records rejected montage-level quality; earlier accepted exact examples remain preserved, no all-six individual fault/cause inferred. Added isolate_hindi_coverage_artifacts.py: exact retained raw negation takes at native24k, gain-only near−18LUFS, no inference/normalization/tempo/EQ/comp/edit. Sujata5.153s/−18.47LUFS/−1.55dBTP; Abhishek8.214s/−17.99/−2.68; decode/source SHA/exact duration/peak/cleanup pass. Folder hindi-raw-controls-8cc1a42c; raw listening pending. Installed config sampling inspected: diagnostictemp.90 overrides config.75, inherited repetition5/topk50/topp.85/length1/do_sampleTrue reach GPT; signature repetition10 does not describe actual config route. No blind parameter promotion or costly new six-take sweep. HINDI_COVERAGE_REJECTION_2026-10-04.md, coverage/readiness updated;490 prior checks retained, no production/new tool/download/commit/push/release. Reliable Hindi quality and full-video gates remain open.

### Abhishek raw language failure and one greedy control — 4 October 2026

User reports other-language opening followed by Hindi in Abhishek raw; exact raw receipt records rejection, other language not independently identified, no Sujata verdict inferred. Failure exists before output processing despite explicit Hindi text/language routing. Added diagnose_hindi_language_drift.py: same reference/text/seed/native24k, do_sampleFalse/num_beams1, inherited penalties unchanged, temperature argument inactive under greedy selection, no output tempo/normalization/EQ/edit. Tokenizer first[hi],20 tokens/zero unknown/full roundtrip; does not certify speech. Completed81.703s/synthesis42.344s, raw4.545s versus sampled8.214s; gain-only−2.81dB yields−18.01LUFS/−2.81dBTP. Decode/signal/format/exact duration/original hashes/peak/cleanup pass. Raw and control retained hindi-greedy-e59ab24c; Hindi-only/negation/naturalness listening pending, shorter not success proof. HINDI_LANGUAGE_DRIFT_2026-10-04.md details. No production/default/new package/model/download/accepted audio change; previous490 checks retained, no release.

### Exact greedy Abhishek take passes human content/fluency check — 4 October 2026

User answers “yes” to starts directly in Hindi/preserves every word/no stuttering for exact presented4.545s gain-only greedy take. Receipt records scoped acceptance and listening WAV SHA. This is not global naturalness/varied-text/Sujata/tempo/video acceptance. Greedy remains a diagnostic candidate requiring other rejected-text coverage before default promotion. No new inference, production changes, packages, downloads or test rerun; original accepted/rejected assets retained. Release remains blocked.

### Further greedy Hindi coverage on both voices — 4 October 2026

User requests continue. Added verify_hindi_greedy_coverage.py, two remaining rejected question/meeting passages for each voice, cached existing offline CPU model once, identical references/text/native24k, greedy num_beams1, inherited penalties, no tempo/normalization/EQ/edit. Completed103.469s/model20.016s/synthesis79.922s, four cases mechanical pass/ten generated WAV decode/reference hashes/cleanup pass. All first[hi], zero unknown/full roundtrip; audible quality pending. Sujata5.985/7.425s versus sampled5.611/7.094 (longer); Abhishek4.129/5.707 versus5.195/5.889 (shorter), no global fit claim. Gain-only levels−18.50..−17.99LUFS, peaks−1.55..−3.85dBTP; not perfectly level/dynamics matched. Two raw-control montages14.309/10.736s with900ms separators, folder greedy-coverage-f0745810, HINDI_GREEDY_COVERAGE_2026-10-04.md and receipt/log retained. Previously accepted Abhishek negation untouched; Sujata negation/tempo quality/runtime profile/full video still unverified. No production/new tool/model/download change, previous490 checks retained, no release.

### Four raw greedy takes accepted; full processing gate — 4 October 2026

User “yes” confirms both raw montages entirely Hindi/no distortion-stutters/natural. Four-take acceptance recorded, not global/default/processed approval. Added verify_greedy_hindi_processing.py using verified raw hashes, existing loudness-only normalization and productionRubberBand1.342/pitch1, no inference/ref/text change or extra EQ/comp/fade/gate/cut. Four timing/peak cases pass/ten WAV decode/workspace removed: Sujata4.460/5.533s at−17.84/−17.34LUFS; Abhishek3.076/4.253s at−16.37/−16.91; peaks safe, not level matched. Intermediates/final/reviews retained greedy-processed-d2a35976; processed listening pending. HINDI_GREEDY_PROCESSING_2026-10-04.md covers combined-stage test and runtime gap. No production/package/model/download/commit/push/release;490 checks retained; video/other gates open.

### Accepted Hindi decoding and processing integrated — 4 October 2026

User “yes” accepts both processed four-take montages natural/clear/no distortion-stutters; receipt records exact scope. Production TTSHandler Hindi uses do_sampleFalse/num_beams1, no seed, .75temperature inactive; other languages keep sampling defaults. Pipeline clonedHindi uses existing loudness-only normalization instead of extra AudioEngineerEQ/comp; other actor/language mastering paths unchanged, tempo1.342 and no-word-cut guards kept. Three regressions added for Hindi decoding/reference, English sampling preservation, Hindi normalization failure context/cleanup. Focused64 PASS21.494s; full493 PASS93.946s. verify_production_hindi_quality.py actual segment path reproduces all four approved PCM using retained synthesis; verify_live_hindi_quality.py fresh actual XTTS adapter/handler/segment produces identical rawSHA/final4.460s PCM with no set productionseed,59.640s. Both receipts/raw/final retained and owned workspaces removed; QA168 files/no mismatches, whitespace passes. HINDI_QUALITY_PRODUCTION_2026-10-04.md and readiness updated. Reference-preparation difference (Abhi diagnostic unprocessed vsfullpipelinecleaning), realcuefit/STT/translation/video/platform/optional gates still open. No new engine/framework/model/download/commit/push/release; old44s failure not reclassified.
