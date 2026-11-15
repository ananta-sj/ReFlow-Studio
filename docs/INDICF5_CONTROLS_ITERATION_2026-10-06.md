# Hindi voice controls and review integration — 6 October 2026

## Purpose and authorization

After accepting the retained 52-second Hindi video, the user instructed us to
continue. This iteration exposes the previously validated engine through the
existing Marketplace and repairs checks that still assumed XTTS. It introduces
no package, framework, model download or external service. Existing user model
connections, defaults, source files and original references are preserved.

## User flow

Marketplace → TTS now contains a Hindi voices section. It lists confirmed local
profiles, shows each exact Hindi reference transcript, plays the reference using
the existing audio player, and requires an explicit matching-words checkbox.
The user selects CPU or the prepared NVIDIA GPU runtime and clicks Connect.
The connected model appears in the existing list; its star selects it. As with
other model connections, a first connection can become active when no active
TTS selection exists. Existing active selections are preserved. Connecting the
same profile again updates its processor without creating duplicate entries.

The dubbing workspace still requires selecting Hindi, a cloned user voice and
uploading the displayed reference WAV or its hash-confirmed original audio.
It does not yet automatically fill the reference file or support creating a new
profile from arbitrary recordings. Only Abhishek currently has the confirmed
profile used by the accepted video. No universal voice-quality promise is made.

The selected processor is specific to Hindi speech. This is necessary because
the main portable runtime uses CPU Torch, while the approved isolated IndicF5
runtime supports the NVIDIA GPU. Other stages retain their workspace processor.
Prepared-runtime discovery checks files/metadata; actual worker startup performs
the deeper Torch, package-origin, CUDA and checkpoint checks already documented.
A displayed GPU option is not a fresh driver health probe on every page load.

## Changes and rationale

- `core/indicf5_profiles.py`: discovers local profiles under the Hindi reference
  library, revalidates confirmation/audio hashes, lists available runtimes/model
  assets, and supplies bounded WAV previews without starting a model. Rejects
  invalid identifiers and profile traversal; bad profiles are excluded.
- `bridge/api.py`: adds read-only listing/preview and explicitly confirmed
  connection. Connection is locked and refused during rendering/downloads.
  Model selection rechecks IndicF5 reference/runtime readiness. Registry writes
  use the existing transactional store. Resource estimates show the speech
  processor and warn that IndicF5 timings/memory remain uncalibrated. They do
  not promise parallel speedup for its serialized worker.
- `core/providers/resolve.py`: forwards the connected Hindi speech processor.
- `core/providers/tts/indicf5_local.py`: rejects unsupported device identifiers;
  current isolated route supports CPU or the first NVIDIA GPU.
- `core/runtime_checks.py`: selected IndicF5 requires its own confirmed profile
  and isolated runtime rather than importing the unrelated XTTS engine. Other
  TTS routes retain their checks.
- `core/cue_review.py`: saves the exact confirmed reference excerpt instead of
  cleaning it. A mismatched upload fails. Successful cue generation releases
  the IndicF5 worker before later review operations. Failure/cancellation still
  uses the job's existing cleanup callbacks. Other engines retain cleaning.
- `frontend/src/lib/api.ts`: typed bridge methods and library response.
- `frontend/src/pages/Marketplace.tsx`: reference playback/transcript,
  confirmation, processor choice, connection/error states and model labels.
- `frontend/src/lib/use-marketplace.ts`: failed model activation now displays
  the backend reason instead of appearing to do nothing.
- `dev/test_indicf5_controls.py` and `dev/test_cue_review.py`: checks for
  read-only previews, confirmation, duplicate prevention, busy guards, invalid
  devices/paths, changed references, provider routing, runtime failure, XTTS-free
  startup, serial-speech estimation and exact review-reference preservation.
- `dev/verify_indicf5_app_video.py`: optional real background-separation test,
  CPU for non-speech stages and GPU via connected Hindi metadata, plus exported
  stem duration/decoding checks. Reviewed recognition/translation fixtures remain
  explicitly labelled; automatic translation quality is not substituted.

## Verification and limits

Initial backend run: 63 checks passed in 19.666 seconds; log
`docs/validation/2026-10-06-indicf5-controls-tests.log`.
Subsequent control/integration/cue/model/language run: 59 checks passed in
35.550 seconds; log `docs/validation/2026-10-06-indicf5-controls-final-tests.log`.
The final production frontend build passed TypeScript and Vite, with the
existing bundle-size advisory. No new dependencies were installed. A browser
visual/playback interaction has not been verified in this iteration.

After estimate routing/serial-worker corrections, 44 control and architecture
checks passed in 3.086 seconds; log
`docs/validation/2026-10-06-indicf5-controls-estimate-tests.log`. These overlapping
runs are separate checks, not a sum of unique tests.

Real bridge read-only discovery found Abhishek, valid local model files, both
prepared runtime options and a working WAV-preview response. Receipt:
`docs/validation/2026-10-06-indicf5-controls-local-discovery.json`. It neither
loaded speech weights nor changed the actual user registry.

A fresh reviewed-script video run with real CPU Demucs separation, isolated GPU
Hindi speech, mixing and stem exports completed. Log:
`docs/validation/2026-10-06-indicf5-background-video.log`. Its result must be
read from `docs/validation/2026-10-06-indicf5-app-video-2918783c.json`.
All eight cues, one reused/released GPU worker, video/audio/subtitle streams,
full video decoding, 52-second exported vocals/background/dubbed stems, original
source hash preservation and job-workspace cleanup passed. Total time after
helper imports was 463.484 seconds; the pipeline timer reported 7 minutes
32 seconds. CPU separation materially increases runtime, so the earlier
speech-only rendering time must not be advertised for this workflow.

Output:
`docs/validation/2026-10-06-indicf5-app-video-2918783c/outputs/source_DUBBED_HI_5ee318a4f90d/source_DUBBED_HI_5ee318a4f90d.mp4`.
The sibling bundle contains vocals, background, dubbed and master stems. Source
recognition and translated text still use the approved fixtures. This source
was not chosen as a music/ambience preservation reference. The technical
`background_preservation_tested` flag certifies exercise of separation/mixing;
`separation_quality_verified` and `human_quality_accepted` remain false.
The retained MP4's subtitle stream is tagged `eng` despite Hindi text, a further
export-metadata issue to repair separately. Technical completion cannot certify natural ambient
preservation or removal of the original dialogue; those need listening review.

Subsequent user listening reply: **"no english leaks"**. Original-English
suppression is accepted for this exact background-enabled video, pinned by its
SHA256 in `docs/validation/2026-10-06-indicf5-background-listening-review.json`.
The original technical receipt remains unchanged. This reply does not separately
confirm absence of separation noise, preservation of music/ambience, automatic
translation fidelity, other source material or release readiness.

## Why TTS is only one part of dubbing

TTS generates the new spoken text, with reference-conditioned voice identity.
This route uses a fixed confirmed reference and sentence-length pace heuristic;
it does not infer and reproduce each source scene's emotion, emphasis or acting.
Source separation handles dialogue/background isolation, translation handles
meaning, timing handles scene fit, and mixing recombines dialogue/background.
The finished product must coordinate all these. The accepted passage validates
its own delivery, not arbitrary language, material or emotional transfer.

Remaining gates: automatic Hindi translation fidelity; emotional continuity
across varied scenes; clean source-dialogue suppression with music/ambience;
additional voices/material; end-to-end UI playback; new-reference onboarding;
portable/runtime setup and packaging across operating systems. No release-ready
declaration follows from this iteration.
