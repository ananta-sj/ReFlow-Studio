# Selected-engine setup inspection — 9 October 2026

## Purpose and scope

The user requested continued development without live model calls. This increment starts A07 by exposing a read-only inspection of the selected pipeline on the Dashboard. It uses existing template plans, registry snapshots, artifact contracts, speech-language guards, offline policy and isolated-runtime resolvers. No tool/framework/package/model was installed, no download initiated, no provider contacted and no inference worker launched.

The inspection deliberately does not declare the software ready for release. A file/runtime selection check cannot establish model loading, dependencies, hardware availability, output quality or end-to-end success. The existing execution preflight remains authoritative when a job starts.

## User experience

**Check selected setup** shows each required inspected feature as Files checked, Needs setup or Not verified. Findings include selected model/voice labels and specific reasons. Exceptions for one feature become a Needs setup finding while the remaining checks continue. There is no automatic install, repair, cloud fallback or provider request. Starting a job is unchanged; the report is advisory, not a new acceptance gate.

Changing requested pipeline parameters clears displayed findings. An in-flight response for old parameters is discarded. Marketplace/connection changes outside these parameters require clicking Check selected setup again; reports are point-in-time previews. Calls are disabled during an active render. The inspection button is not dependent on a selected media file because it checks configuration, not input contents.

## Shared plan and checks

The bridge freezes the registry and reuses the execution template/cast mapping. PipelineSpec expands the lip-sync template and determines which optional features belong to this job. Subtitle-only plans skip media preparation, separation, recognition and speech; keeping source text skips translation. Active text moderation is inspected. Cast voices receive separate findings.

Media programs are located on the application's path without executing them. Selected local STT/translation/TTS/filter/enhancer/lip-sync artifacts use existing contracts. Pinned Whisper Turbo and IndicTrans2 additionally require their existing interpreter resolvers. IndicTrans2 checks English source and Hindi target; automatic audio-source identification remains unresolved until recognition. Subtitle translation through NLLB/IndicTrans2 requires an explicit source selection.

IndicF5 verifies the confirmed reference profile/audio identity, an explicitly supplied reference when present, supported runtime-device selection and existing interpreter. Speech checks reuse existing target-language/cast guards, including the validated Hindi-only IndicF5 route and F5 language declarations. Keeping an automatically detected source leaves speech language Not verified until recognition.

F5/MuseTalk file selections check the existing optional-runtime interpreter when applicable. RVC inspection checks only checkpoint existence/nonzero size: its full artifact contract loads tensor weights, so it is intentionally deferred. Built-in fallbacks, AirLLM, API routes and background separation retain explicit unverified details instead of importing or starting engines. API URL/preset configuration and offline restrictions are checked; credentials, accounts, availability and provider compatibility are not contacted or proven.

The report explicitly explains device routing: the pinned Whisper Turbo route uses the first NVIDIA GPU; IndicF5 uses its selected profile's speech device. These can differ from the Dashboard device. GPU presence/capacity is not probed by this report. Other routes do not gain a new hardware-support claim.

## Installed-selection observation

`validation/2026-10-09-engine-readiness-installed.json` records an actual read-only inspection of the current video configuration for English-to-Hindi, confirmed user voice and background separation disabled. Media executables, local Whisper Turbo, IndicTrans2 and Hindi Abhishek/IndicF5 contracts/interpreters passed these limited checks. Both recognition and speech report their existing GPU routing. Saved registry/settings hashes were unchanged. This is an installation observation, not a new inference or video-quality result.

This check does not repair the previously noted stale IndicTrans2 runtime preparation label or make that metadata authoritative. Resolver/file checks are reported directly. A measured runtime-capability inventory, fresh GPU/dependency probes, cross-platform behavior and provider compatibility remain future A07 work.

## Implementation and verification

New `core/engine_readiness.py` owns the inspection report and scopes it through PipelineSpec. `bridge/api.py` exposes the snapshot-backed read-only method. `frontend/src/lib/api.ts` types it; `frontend/src/pages/Dashboard.tsx` presents findings and discards outdated parameter responses. `dev/test_engine_readiness.py` covers plan scoping, missing media/runtime, incompatible translation languages, explicit subtitle source, offline APIs, no credential/HTTP access, no RVC tensor loading, forced lip-sync and execution cast mapping. The backend evidence runner includes the new source and Dashboard hashes and a distinct label.

The first focused run passed nine tests; the subsequent explicit-subtitle-source test is included in the complete suite. Frontend build and source lint passed with existing warnings. Retained logs: `validation/2026-10-09-engine-readiness-frontend-build.log` and `validation/2026-10-09-engine-readiness-frontend-lint.log`. Browser interaction was not newly exercised. Complete backend results are recorded in `validation/2026-10-09-engine-readiness-backend-complete.json` and the matching log; final totals are appended below after completion.

The first complete run executed 694 tests with one error: Windows denied `os.replace` while the existing review-preparation test published its temporary directory (`WinError 5`). That test passed ten consecutive isolated repeats without code changes. The underlying cause was not established; no speculative production retry/exception suppression was added. Failed evidence is retained as `validation/2026-10-09-engine-readiness-backend-first-run.json/.log`; repeated-test evidence is `validation/2026-10-09-review-publication-repeat.log`. A second complete run is used for the final result, while the intermittent failure remains documented.

**Final complete result: 694 tests across 39 modules passed in 107.359 seconds**, with zero failures/errors, unchanged tested production sources and unchanged saved registry/settings. A separate final integrity check confirmed every recorded source hash still matches and the accepted editorial video is unchanged (SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`). Receipt: `validation/2026-10-09-engine-readiness-evidence-integrity.json`. A passing rerun does not explain or eliminate the earlier intermittent Windows publication failure; monitor and reproduce it before introducing a targeted repair.

## Remaining work

A07 remains partial: runtime package/driver execution, full stage/device/platform declarations, install-repair guidance and measured resource profiles need further work. This check does not validate input media, acoustic naturalness, semantic preservation, actual speech timing or background leakage. Model-download behavior and existing render guards are unchanged. Live dialogue-assistance quality evaluation remains deferred by the user, and automatic quality acceptance and the optional manager remain incomplete. Release remains pending.
