# Smaller portable core: reviewable proposal

Status: withdrawn. The user dropped the 500 MB target and prioritized making
ReFlow a dependable, distinctive product. No approval for this migration was
given; the measured proposal is retained only as historical analysis. Existing working
runtime, environments, media and custom models remain preserved. No installation
or packaging migration has been performed for this proposal.

## What the current manifest proves

The measured Windows portable manifest contains approximately:

| Component | Bytes | Decimal MB |
| --- | ---: | ---: |
| Python plus installed main AI packages and vendor resources | 2,350,165,430 | 2,350.17 |
| FFmpeg and FFprobe programs | 201,298,432 | 201.30 |
| FFmpeg shared libraries for Python audio decoders | 264,685,056 | 264.69 |
| Application and vendored engine source | 6,267,467 | 6.27 |
| Desktop frontend, assets and other root files | 1,894,860 | 1.89 |

Source: `validation/2026-10-04-portable-manifest.json`. This is unpacked size;
archive compression is a separate measurement. The current core already omits
downloaded models, caches, Git history, user files and optional runtime profiles.
Deleting replaceable weights again would reduce installed workspace size, but
would not reduce this measured core. Blind removal of NumPy, Torch, language
dictionaries, Torchcrepe or FFmpeg libraries would break existing engines.

## Proposed change and user impact

Retain a small desktop Python runtime, pywebview, bridge, frontend, application
source, FFmpeg and FFprobe in the initial package. Move the existing main AI
dependency set and Python decoder FFmpeg shared libraries into an optional main
AI runtime, following the isolation already used for F5, MuseTalk and NudeNet.
This proposes no new UI framework or AI engine. The desktop dependency closure
must be measured and tested; it has not yet been built or verified.

The three measured non-runtime groups total **209,460,759 bytes**, leaving
**290,539,241 bytes** below a decimal 500 MB target for desktop Python, its
dependencies and packaging overhead. This is a budget, not an accepted build.
Moving components between packages changes initial delivery size, not the total
disk required for all offline features. First use needs an explicit optional
runtime setup followed by model recovery; subsequent verified offline use must
not require the network. Existing full portable delivery should remain available
as an alternative during migration.

## Required implementation work

1. Remove main-AI imports from desktop startup paths. `config.py` currently
   imports Torch unconditionally. Hardware discovery, template listing, integrity
   reporting and local-checkpoint inspection also need a desktop-safe boundary.
   Do not hide actual engine unavailability behind successful integrity results.
2. Dispatch the existing render pipeline to a job-owned worker using the main
   optional interpreter. Preserve source-language events, node progress, queue
   ownership, exceptions, cancellation, atomic publication and cleanup. Exchange
   settings and registry snapshots deliberately; never switch to unrelated user
   defaults or mutate user selections during worker startup.
3. Share existing project paths for models, outputs, credentials and optional
   profiles. Pass credentials only as needed and preserve current storage rules.
   Relative portability must survive relocation of the complete folder.
4. Prepare a pinned, platform-specific optional runtime manifest and transactional
   setup with validation and cancellation. Failed setup must preserve the last
   working environment. GPU packages require explicit platform/backend support;
   a CPU-only Windows receipt cannot validate CUDA, Linux or macOS.
5. Keep FFmpeg programs in the core for probing/preview/export. Supply shared
   decoder libraries to the AI worker that needs them. Verify DLL resolution from
   the selected worker runtime without relying on external system libraries.
6. Make setup size, network requirements and readiness clear in the UI before
   downloading. Avoid promising offline inference until required assets exist.

## Acceptance gates before calling this complete

- Measured unpacked core and archive; reproducible contents with no user data.
- Clean relocated desktop boot, all six pages and ten Nodes, with AI packages
  genuinely absent from the desktop interpreter.
- Existing backend/frontend checks and build; new worker protocol, setup failure,
  cancelled setup/render, unavailable runtime and stale-output checks.
- Real subtitle, audio dubbing and complete video chain through the optional
  worker; source timing, stems and subtitle preservation.
- Real stop request terminates only owned workers and leaves prior media intact.
- Completed setup can run the supported chain with network access disabled.
- Windows acceptance first; Linux/macOS remain explicit gates until run on those
  platforms. Main engine and model distribution permissions remain a separate
  release review.

This proposal does not authorize deleting original environments, downloaded
models, custom voices, QA artifacts or Git history. It does not fix the recorded
translation-quality failures or supply the missing authorized RVC checkpoint.
