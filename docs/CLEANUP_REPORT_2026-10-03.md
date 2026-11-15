# Cleanup and size audit - 3 October 2026

> A later clearance pass removed another 151 MB of compiler archives and stale/empty artifacts. See [the follow-up clearance report](cleanup/2026-10-03-followup/CLEARANCE_REPORT.md) and its latest size summary. The measurements below describe the original cleanup snapshot.


**The workspace was reduced from 28.949 GiB to 6.016 GiB, freeing 22.932 GiB (79.22%).**

| Measurement | Before | After |
| --- | ---: | ---: |
| Whole workspace, decimal GB | 31.083 | 6.460 |
| Whole workspace, GiB | 28.949 | 6.016 |
| Files | 123,580 | 110,336 |
| Filtered shipping files (estimate) | Not measured | 2.994 GB / 2.788 GiB |

The complete runtime still exceeds 500 MB. Exact byte measurements and scope
are in `cleanup/2026-10-03/after-summary.json`. Full initial/surviving/removal
file inventories are compressed in `cleanup/2026-10-03/file-inventories.zip`.
The surviving-file CSV excludes audit artifacts themselves; final totals
include them. The ZIP is evidence, not a backup of removed file content.

## Scope and project review

The request was to investigate ReFlow Studio as a DevOps/debugging lead,
remove heavy disposable files and caches, aim for 500 MB if feasible, and
thoroughly document every change. Permission to remove replaceable model
weights and download them again when needed was explicitly received.

Reviewed the public [ReFlow-Studio repository](https://github.com/ananta-sj/ReFlow-Studio)
and the local working copy. The public README describes the v0.6 portable
workstation and its first-run model downloads. The local tree is a later,
substantially richer application: a React/Vite UI in `frontend`, a pywebview
entry point in `main.py`, a Python bridge, pluggable pipeline providers,
vendored Wav2Lip/MuseTalk, and old PyInstaller/installer tooling.
The local repository has **no configured Git remote**. No fetch, reset,
commit, push, release publication or history rewrite was performed.

The inspection followed actual launcher precedence rather than assuming a
folder named `build` was disposable. `Launch_Reflow.bat` first looks for a
native executable, then `build/windows-portable/python.exe`, then the
existing `.venv`, then root/system Python. The active embedded Windows
interpreter was directly queried: **CPython 3.10.11, 64-bit**, not 3.11.12.
The development `.venv/pyvenv.cfg` and interpreter also report 3.10.11.
That virtual environment depends on a separately installed base interpreter;
it is an isolated development environment, not a self-contained portable
runtime.

The Windows embedded interpreter, native extensions and FFmpeg EXEs cannot
run unchanged on Linux/macOS. The existing shell launcher creates a
platform-specific virtual environment and relies on an appropriate Python
and FFmpeg installation there. No Linux/macOS machine was available for
execution testing. The legacy native packaging workflow was retained as
source; the generated Windows installer was removed.

## Initial state and preservation

The initial inventory measured **31,083,341,771 bytes in 123,580 files**
(31.083 GB decimal / 28.949 GiB). Sizes are summed file lengths, including
Git; they are not NTFS allocated-space measurements. Compression, sparse
allocation, hard links and symbolic links can make actual disk allocation
different. MB means 1,000,000 bytes; MiB/GiB are binary units.

Before editing, Git already showed changes to `Launch_Reflow.bat`,
`bridge/api.py`, `core/hardware_monitor.py`, `core/integrity.py`,
`core/pipeline.py`, `core/providers/resolve.py`, `core/rvc/rvc_handler.py`,
and `core/srt_utils.py`. `Sample`, `core/queue_manager.py` and three existing
diagnostic scripts were untracked. These were preserved. In particular,
the bridge, hardware monitor, pipeline, provider resolver, subtitle helper,
queue manager, original tests, and sample media were not rewritten by this
cleanup. Existing edits in files that needed a small additional cleanup
change were preserved through contextual edits.

The following were intentionally retained:

- `Sample/`, `outputs/` and any final rendered videos.
- All source, frontend source and lockfile, built `frontend/dist`, assets,
  licenses, legacy packaging specifications, installer recipe and workflow.
- User settings, credentials/references, hardware profile and model registry
  identities/source URLs/custom instructions.
- Git history, refs, index and repository configuration; no Git pruning.
- Both Python environments, installed package source and metadata, runtime
  DLLs/PYDs, standard library and the Visual C++ redistributable.
- Static FFmpeg/FFprobe and the entire `ffmpeg/shared_libs` set. The shared
  libraries are used by the development runtime's TorchCodec audio backend;
  treating them as duplicate command-line binaries would break that path.
- Any custom voice checkpoint/index not positively identified as a standard,
  replaceable asset. No custom RVC voice weights were selected for deletion.
- Small XTTS configuration, vocabulary, hash and existing terms acceptance.
  Recovery does not create or accept new license agreements.

## File removal ledger

The exact operations, reasons, file counts and byte savings are in
`cleanup/2026-10-03/all-removed-targets.csv`. Full per-file paths and original
sizes are in the inventory archive. These are the substantive categories:

| Target | Original bytes | Why it was safe / how to recover |
| --- | ---: | --- |
| `installer/ReflowStudio-1.0.0-Setup.exe` | 3,092,506,905 | Generated legacy installer. Packaging sources retained. Rebuilding needs the legacy native build and installer tooling. |
| `models/_downloads` | 7,469,834,665 | Incomplete Marketplace downloads, primarily large Hugging Face partial blobs. Registry/source URLs preserved; re-download only wanted entries. |
| `models/translation` | 1,941,931,052 | M2M100 downloaded cache. The existing translator's `from_pretrained` restores it when translation is used. |
| `models/xtts/default/model.pth` | 1,867,929,118 | Standard XTTS checkpoint, restored on first default TTS use. |
| `models/xtts/default/speakers_xtts.pth` | 7,754,818 | Standard XTTS speaker embeddings, restored with the checkpoint. |
| `core/MuseTalk/models` | 7,386,280,204 | Downloaded v1 and v1.5 plus auxiliary assets. The provider uses v1.5; recovery retrieves v1.5 and required auxiliaries only, avoiding the unused second ~3.4 GB UNet. |
| `core/Wav2Lip/checkpoints/Wav2Lip_GAN.pth` | 435,801,865 | Standard GAN checkpoint; restored when lip sync is selected. |
| `gfpgan/weights/GFPGANv1.4.pth` | 348,632,874 | Standard restoration model; recovered on enhancer use. |
| `gfpgan/weights/parsing_parsenet.pth` | 85,331,193 | Standard face parsing model; recovered with GFPGAN. |
| `gfpgan/weights/detection_Resnet50_Final.pth` | 109,497,761 | Standard face detector; recovered with GFPGAN. |
| `models/rvc/hubert_base.pt` | 189,507,909 | Its SHA256 matched the copy in `rvc_python/base_model` before either was removed. Redundant root copy is not consumed by the current RVC wrapper. |
| Bundled RVC `hubert_base.pt`, `rmvpe.pt`, `rmvpe.onnx` | 732,380,624 total | Standard recoverable base assets. Their upstream URLs were also verified. Recovery happens before `RVCInference` initialization. Custom voices are separate. |
| Portable Torch `lib/dnnl.lib` | 708,668,648 | Static oneDNN archive for building/linking native extensions. Inference uses retained DLLs; Torch import and backend tests passed after removal. Reinstall the exact Torch wheel before compiling extensions against this runtime. |
| `.venv/.../~umpy` and `~umpy.libs` | 43,450,368 total | Abandoned pip upgrade/uninstall remnants. Active `numpy` and `numpy.libs` retained. |
| `frontend/node_modules` | 161,712,195 | Development dependencies. Built interface retained. Recreate with `npm ci` before editing/building the UI. |
| Wav2Lip `temp_input.wav` / `temp_input.mp4` | 27,949,083 total | Intermediate copies made by the lip-sync subprocess; original Sample and final outputs retained. |
| Processing temp folders and interpreter/tool caches | See ledger | Generated files. Includes Python bytecode and Numba compiled caches found under `__pycache__`; they can regenerate during processing. |

Three cleanup passes are retained separately so the audit reflects actual
operations: the main pass, the additional bundled RVC models, and leftover
Wav2Lip copies/caches. The ledger includes zero-byte temporary directories.
Its gross savings include caches regenerated during validation; net savings
are calculated from before/after inventories instead, avoiding double counting.
No global user cache (`pip`, Hugging Face, npm, Windows temp, etc.) outside
this workspace was deleted.

## Source and behavior changes

| File | Exact purpose of the change |
| --- | --- |
| `core/model_assets.py` (new) | Feature-specific recovery for XTTS, Wav2Lip, GFPGAN, RVC and MuseTalk. No download at module import. Existing valid files skip HTTP; known checkpoint sizes are checked. Model writes use a lock, temporary `.download` file and atomic replacement. HTTP failures, HTML responses, empty/truncated downloads and size mismatches do not install a checkpoint. Failed transfers remove the partial file and preserve any prior destination. Missing assets under `REFLOW_OFFLINE=1` produce a recovery instruction. |
| `core/integrity.py` | Normal startup checks libraries without fetching all AI weights. `--download-models` retains explicit access to the legacy Wav2Lip/GFPGAN pre-download behavior. That legacy route does not restore every model family; use the new recovery command for feature selection. |
| `core/tts/tts_handler.py` | Recover the default XTTS files when the default handler is first created. Explicit Marketplace model-path overrides keep their existing loader behavior. |
| `core/lipsync_handler.py` | Recover Wav2Lip GAN at execution time only when neither selected GAN nor standard checkpoint exists. |
| `core/enhancer.py` | Recover GFPGAN/face assets when the enhancer is instantiated. Initialize `restorer` to `None` and return safely when the GFPGAN library is absent. |
| `core/providers/lipsync/musetalk_local.py` | Recover only the v1.5 UNet, VAE, Whisper and face parsing assets before MuseTalk execution. The revisions came from the installed Hugging Face metadata. |
| `core/rvc/rvc_handler.py` | Recover RVC base models into the selected interpreter's `rvc_python` package before its existing initializer runs. Existing RVC handler changes were retained. |
| `Launch_Reflow.bat` | Anchor relative paths to the launcher's folder, so launching from another working directory still resolves the runtime/assets. Disable routine Python bytecode writes. Existing interpreter fallback was retained. |
| `LAUNCH_REFLOW.sh` | Disable routine Python bytecode writes; preserve LF line endings. No OS dependency strategy was changed. |
| `requirements.txt` | Explicitly declare `requests` and `filelock`, consumed directly by recovery. No installed package versions were upgraded or uninstalled. |
| `.gitignore` | Ignore regenerated pytest, mypy and Ruff cache directories. |
| `.gitattributes` (new) | Keep shell scripts in LF format across Git checkouts, including Windows checkouts. |
| Local `models.json` | Reconcile five installed entries whose files were absent/removed. Mark them `not_downloaded`, clear their stale paths and active selections, retain identities, source URLs, metadata and custom instructions. A preexisting error entry remains an error. The original registry is backed up in the audit. |
| `dev/cleanup_workspace.ps1` (new) | Reproducible cleanup with dry-run default, model-removal switch, explicit allowlist, checked workspace containment, Git protection, directory-link/reparse protection, and an operation ledger written after each deletion. Final media is excluded. |
| `dev/restore_models.py` (new) | Explicit feature pre-download for offline preparation. Successful explicit XTTS/MuseTalk recovery also refreshes matching Marketplace availability without choosing an active model. |
| `dev/cleanup_smoke.py` (new) | Read-only import/version diagnostics; no GUI launch or model loading. |
| `dev/run_cleanup_checks.py` (new) | Run existing backend tests plus recovery tests while excluding destructive janitor and credential-store tests. |
| `dev/test_model_assets.py` (new) | Offline regression tests for atomic recovery, truncation/failure cleanup, existing-cache reuse, offline behavior, HTML/HTTP failures and model-free normal startup. |
| `dev/verify_model_sources.py` (new) | Bounded public HTTP HEAD checks of recovery URLs; writes no model weights. |
| `dev/verify_cleanup_runtime.py` (new) | Syntax checks, entry-point import, built-UI presence, synthetic H.264 encoding and FFprobe inspection; temporary clip removed afterward. |
| `docs/CLEANUP_REPORT_2026-10-03.md`, audit directory | This report and before/after inventories, deletion plans/ledgers, registry backup, source availability checks and validation results. |
| `README.txt` | Link to the cleanup report, verified interpreter version, smaller model-free startup and recovery commands. |

Recovery for files hosted on Hugging Face uses the normal upstream resolve
URLs. MuseTalk and its auxiliaries use captured commit revisions; XTTS,
Wav2Lip and RVC use existing upstream `main` URLs with known weight sizes,
and GFPGAN/facexlib use versioned release URLs. HTTP availability and byte
sizes are checked; **this is not cryptographic verification of newly downloaded
weights**. An upstream revision change can require updating the manifest.
Very large transfers are retried from the beginning after failure; new
recovery is streaming and atomic, but not resumable. Existing Marketplace
snapshot downloads retain their original behavior.

## Verification and practical limits

- **22 tests passed**: existing subtitle, graph, hardware, registry, language,
  bridge helper, queue and path tests; eight new recovery tests.
- Twelve imports were compared before/after; results and versions matched.
  Successful imports include Torch, torchaudio, OpenCV, pywebview, TTS API,
  RVC package, faster-whisper and the Python bridge.
- Syntax parsed for the twelve initially changed/new Python files listed
  in the runtime-check script. Additional final syntax/line-ending checks
  are captured separately.
- `main` imported successfully and `frontend/dist/index.html` exists.
- Bundled FFmpeg encoded a 0.2-second H.264 clip; bundled FFprobe read its
  codec and duration. The generated clip was removed.
- The real default integrity command completed successfully and did not
  restore removed checkpoint directories.
- **All 20 model recovery URLs returned HTTP 200**; remote checkpoint lengths
  matched the known sizes where supplied. Full multi-GB re-downloads and
  real AI renders were not run, as they would immediately reverse cleanup.
- Git whitespace checking also reported an existing trailing-space line in `core/hardware_monitor.py:310`. That unrelated user edit was preserved; it is not a cleanup regression.
- No GUI interaction, clean-machine migration, native installer rebuild,
  Linux/macOS execution or full end-to-end AI render was claimed.
- Sample/output/built-interface file inventories are compared with the
  original measurement in the final audit. Original source edits are
  visible in the saved starting Git status.

Preexisting runtime divergence is significant. The launcher-selected
portable environment has Torch/torchaudio **2.7.1+cpu**, OpenCV **4.11.0**,
and original TTS **0.22.0**. It already lacked `f5_tts`, `diffusers`,
`face_alignment`, and `torchcodec` before cleanup; those same four imports
fail afterward. The development environment metadata instead reports
coqui-tts **0.27.5**, Torch **2.13.0**, torchaudio **2.11.0**, torchvision
**0.28.0**, and the newer optional packages, but lacks `rvc_python`.
Those version differences were observed, not repaired here. Metadata
presence is not proof that every development-runtime extension is ABI
compatible. The two environments cannot safely be treated as interchangeable
copies. The development environment was queried, but its entire dependency
stack was not regression-tested after cache cleanup.

`core/integrity.py` still verifies only its existing subset of library
specifications, not every optional provider or native-library import.
A passing startup integrity check therefore does not certify the absent
F5-TTS/MuseTalk dependencies. The report makes these existing gaps explicit
rather than calling this a complete new release.

## Restore and repeat cleanup

Run from the project directory on Windows. Keep internet access available
for selected features until their models have been restored.

```powershell
# No deletions: inspect a proposed routine cleanup.
.\dev\cleanup_workspace.ps1

# Apply routine cache/intermediate cleanup; final videos are retained.
.\dev\cleanup_workspace.ps1 -Apply -ReportDirectory docs/cleanup/next-run

# Also remove known replaceable AI models.
.\dev\cleanup_workspace.ps1 -Apply -RemoveReplaceableModels -ReportDirectory docs/cleanup/next-model-run

# Restore only what a planned offline job actually uses.
.\build\windows-portable\python.exe -B dev/restore_models.py xtts wav2lip
.\build\windows-portable\python.exe -B dev/restore_models.py gfpgan
.\build\windows-portable\python.exe -B dev/restore_models.py musetalk
.\build\windows-portable\python.exe -B dev/restore_models.py rvc

# Restore frontend development tools before changing the UI.
cd frontend
npm ci
npm run build
```

For M2M100 and faster-whisper, their existing loaders download on first
translation/transcription use; run the desired workload while online
before expecting offline use. Removed Marketplace entries retain their
source URLs in `models.json` and `models-before.json`; reconnect only wanted
models. Generic repository snapshots may include multiple checkpoint
formats and therefore can be much larger than one inference model.

`REFLOW_OFFLINE=1` blocks missing assets in the **new recovery helper only**;
it does not globally disable networking in existing translation, STT,
Marketplace or cloud providers. Python bytecode and Numba/tool caches can
regenerate outside the standard launcher. Use the cleanup script after
processing if keeping disk use low is more important than warm-start speed.

Deleting caches and downloads is permanent at the local file level; the
inventory archive is an audit, not a model/installer backup. Models need
internet to recover. The old installer needs a rebuild. To restore the
removed static archive for development, reinstall the same CPU Torch
2.7.1 wheel into the embedded runtime, avoiding dependency upgrades unless
undertaking a deliberate runtime rebuild.

## Why 500 MB is not achieved by safe file cleanup

The target refers to a self-contained app with the necessary runtime, not
just a compressed source checkout. AI models are already omitted after this
cleanup. The remaining embedded Python/dependency tree still exceeds
500 MB by itself; FFmpeg/FFprobe and shared FFmpeg libraries add
**465,983,488 bytes**. Simply removing DLLs, language dictionaries, numeric
engines or required native-extension packages would disable current features.
Keeping models offline requires additional gigabytes for whichever models
are selected. Compression can reduce download size but does not reduce the
expanded working set to the same number.

A full portable release should exclude `.git`, the development `.venv`,
Sample/output media, development tools and audit inventories. The final
summary includes that filtered footprint to separate repository size from
shipping size. No new release archive was generated or published.

Reaching a <=500 MB **initial download** remains a possible separate product
strategy: a bootstrap package with Python, the UI and minimal media tools,
then a verified first-run install of platform-specific dependencies and
selected models. Its installed size would still expand beyond 500 MB.
Alternatively, a smaller feature set or cloud processing changes the
runtime requirements. Neither was substituted for the user's current
fully functional local-processing requirement during this cleanup.

The recommended next engineering step is a single reproducible,
platform-specific runtime build with aligned Torch-family versions and
feature dependency groups, followed by clean-machine and real-render
validation. Only then should the redundant development environment be
removed or a new portable release advertised.
