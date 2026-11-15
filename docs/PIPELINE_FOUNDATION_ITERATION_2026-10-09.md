# ReFlow Studio: first pipeline-foundation implementation

**Date:** 9 October 2026. **Scope:** first implementation increment following the architecture audit. **Release status:** pending. No new tool, framework, model, package or runtime was installed.

## 1. What this iteration changes

The ordinary automatic pipeline now compiles a versioned fixed-template plan, freezes its engine selections and settings, preserves source/translated cue evidence, and writes a durable record of real execution. These changes provide application operations and evidence on which later checkpoints, dialogue adaptation, a quality supervisor and an optional AI manager can build.

This work does not add a quality judge, prompt-driven agent, trained SLM or automatic dialogue adaptation. It does not turn the node workspace into an arbitrary graph executor. Existing engines and media behavior are retained.

The motivating problem was concrete: automatic recognition/translation reused `text`, engine selections/settings could be reread during execution, and temporary job cleanup removed much of the evidence needed to explain a failure. Manual review and evaluation receipts already retained useful information, but that was not the normal automatic run contract.

## 2. Implementation inventory

| File | Change in this iteration | Purpose |
| --- | --- | --- |
| `core/pipeline_contracts.py` | New versioned fixed-template plan, common frontend mapping, cue identity/lineage helpers and read-only registry/settings snapshots | Establish reusable boundaries without a new dependency |
| `core/run_manifest.py` | New durable execution record, atomic JSON/cue publication, provider observations, file/audio identities and bounded Windows publication retry | Preserve actual results and failures outside temporary job workspaces |
| `core/model_registry.py` | Add `snapshot()` using one locked registry read | Freeze entries and active selections together |
| `core/pipeline.py` | Compile/snapshot at `run()`, retain cue provenance through grouping/translation, observe engines/media/timing, finalize success/failure/cancellation records | Connect the contracts to ordinary automatic execution |
| `bridge/api.py` | Delegate render-parameter mapping to the shared mapper; log the run-record path after a normal execution | Keep Dashboard and Nodes on the same mapping and make the record discoverable |
| `core/providers/stt/whisper_turbo_local.py` | Retain the actual worker interpreter path | Identify the isolated runtime used for recognition |
| `core/providers/tts/indicf5_local.py` | Retain the worker interpreter and the validated profile used for estimation/synthesis | Record the actual voice recipe rather than stale constructor metadata |
| `dev/test_pipeline_foundation.py` | New disposable-state contract/lifecycle/evidence tests | Check meaningful invariants and negative paths |
| `dev/test_parallel_speech.py` | Update its existing two-worker gate to recognize observed method calls | Preserve the concurrency behavior test after introducing the observer wrapper |
| `dev/test_feature_session.py` | Retry a transient Windows request-file sharing denial within the existing test deadline | Still require actual request removal and prompt worker shutdown |
| `dev/verify_workflows.py` | Add a read-only snapshot to its explicit fixture registry | Keep older evaluation drivers compatible with the new run entry |
| `dev/run_cleanup_checks.py` | Include foundation tests | Keep the curated check runner current |
| `dev/verify_pipeline_foundation.py` | New live offline validation driver for short known, full known and independent-source cases | Exercise installed engines without substituted text, takes or in-memory engine selections |

These are the changes made in this iteration. The working tree already contained earlier repairs; the entire Git diff must not be attributed to this increment. No commit, push, deployment, model deletion or cache purge was performed.

## 3. Shared plan and frozen selections

`PipelineSpec` emits `reflow.pipeline-spec.v1`. It supports the existing four templates: `video_dub`, `video_dub_lipsync`, `audio_dub` and `subtitle_translate`. Unknown templates and unsupported template parameters are rejected. Defaults are filled from the existing method defaults. The lip-sync template still forces lip sync.

The payload contains the template/input kind, requested parameters, effective parameters, expected stage sequence, normalization warnings, existing-provider fallback policy and a retry limit of zero for inference. Returned payloads/parameters are deep copies; changing the caller's nested cast/style objects cannot change the compiled job.

The frontend mapper preserves its existing accepted fields. Dashboard and Nodes already use the bridge; they now delegate to one mapper. A future manager can invoke the same supported application path. There is no separate agent execution path in this iteration.

Unsupported `other:` compute devices normalize to CPU with an explicit warning. The requested device remains distinguishable from the effective device in the current plan. A selected engine's existing isolated-runtime/device policy can still override the general workspace processor; actual provider observations record that route where available. This iteration does not redefine device selection.

At `run()` start, `ModelRegistry.snapshot()` takes one locked read and returns a read-only adapter-compatible object with `list`, `get`, `get_active` and `get_active_map`. Settings are similarly copied once. Provider resolution and runtime preflight use these frozen objects during the run. The pipeline restores its original objects after completion, exceptions or generator close.

This freezes configuration selections, not all external content. It does not copy model weights, lock remote services or make every file at a selected path immutable. Existing artifact/reference validation remains responsible for checking those files. Exact weight/runtime provisioning and broader capability descriptors remain separate work.

## 4. Cue identity, original text and grouping lineage

Automatic cues carry `reflow.cue.v1` metadata while retaining legacy `start`, `end` and `text` fields for existing consumers:

- `cue_id`: deterministic identity scoped to the source hash during a normal run.
- `parent_ids`: original cue identities used by a grouped child.
- `source_text`, `source_start`, `source_end`: source evidence retained through translation.
- `translated_text`: completed translation before optional text moderation.
- `adapted_text`: the later moderated wording when it differs; this field does not imply an automatic dialogue-adaptation engine exists.
- `revision`: text transformation revision.
- `source_fragments`: original fragments retained when cues are merged/grouped.

Identities are assigned before sentence/short-cue grouping. A merge creates a child identity from its parent identities. Reordering existing canonical cues does not replace their identities. Equal words/timings from different source namespaces receive different identities. Provider-supplied fields cannot replace the canonical original text; a provider identity can be retained separately as `provider_cue_id`.

Recognition evidence is saved before grouping and again after grouping. Each completed translation and the final speech-input transcript are saved. A failed recognizer with a real worker transcript retains that raw worker evidence, even if it contains only punctuation. Source-language selection/detection/probability are recorded without forcing an uncertain source to English.

The saved manual-review workflow continues to use its existing revision/index API and persistence format. Its recognition payload benefits from the new cue metadata, but a complete migration of review edits/combinations/takes to the common cue contract is **not** completed here. Historical review files and accepted media were not rewritten.

## 5. Durable run evidence

Normal runs create `Outputs/run_records/<run-id>/manifest.json` under their configured output root. Evaluation runs use their separate validation output root. Run folders also contain hashed cue JSON artifacts. They survive normal owned-job temporary cleanup.

`reflow.run-manifest.v1` records:

- Run identity, creation/final timestamps and running/completed/failed/cancelled status.
- Compiled plan; source path/bytes/SHA-256; core Python version, interpreter and platform.
- Selected model IDs, kinds, artifact paths/presets and limited voice metadata; configuration/instruction digests.
- Settings snapshot with the translation host omitted, plus the full settings digest.
- Actual operation status, elapsed wall time, adapter identity and supported engine/device/runtime/reference details.
- Translation input/output and cue identity; raw/grouped/final cue artifacts.
- Generated artifact bytes/hash and PCM WAV rate/channels/frame count/duration where readable.
- Native timing prediction/window, applied speed, resulting duration, actor and native-delivery flag.
- Media-command output identities and existing media-validation observations.
- Final exported artifact identity or failure/cancellation type.

Provider operations are observed around their existing method calls. They still call the real adapter. A default translator's actual underlying mode/model/device can be recorded after fallback. This iteration does not select a new fallback policy or add model retries.

An operation marked completed means the observed call returned and its evidence was recorded. It does not certify translation accuracy, speech naturalness, downstream validation or checkpoint usability.

Credentials, arbitrary request headers, API endpoints and full request presets are excluded from model summaries. Complete configuration is represented by a digest. Provider exception messages may contain private request data, so the run manifest records error types/operation identity; the existing user-facing error/log path retains diagnostic handling.

Temporary generated media is hashed while it exists and labelled `temporary-unless-exported`. The manifest does **not** pretend those files remain playable after cleanup. JSON cue evidence and final exports are durable. This is an observation system, not a checkpoint cache.

Operation elapsed times include the work inside the observed call, such as startup/inference/shutdown. Cue processing and speech calls overlap in scope; their durations must not simply be added together. Tiny timing-observation durations are not calibrated timing-adjustment benchmarks. No resource-estimate calibration or peak RAM/VRAM claim is made here.

## 6. Failure, cancellation and Windows persistence behavior

Runs without an output, missing/empty outputs, provider exceptions and native timing overflow do not receive successful completion records. Generator close and `RenderCancelled` receive cancelled status. Original settings/registry references are restored. Existing job ownership and worker cleanup continue to apply.

Record creation occurs before inference. If durable publication fails, the engine call is not started. Existing complete JSON remains intact through the atomic publication mechanism. A genuine inability to write can leave only the last valid running record; recovery/checkpoint handling for that state is not implemented yet.

A live independent-source attempt encountered Windows `WinError 5` during the initial atomic rename, before any inference. A fresh retry succeeded. The new record writer now retries only Windows permission errors 5/32, up to four publication attempts, with 50/100/200 ms waits. Persistent permission errors still propagate. Tests verify both transient recovery and bounded failure preserving previous bytes. The original failed validation receipt is retained:

[Initial publication failure](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-independent-4f6ea002.json>).

The broader test run also encountered a sandbox-blocked loopback HTTP test and a brief worker request-file sharing race. Host-access checks resolved the socket restriction. The request-removal test now waits within its original deadline for Windows to release the file; it still asserts removal and the same fail-fast cleanup behavior.

## 7. Real execution evidence

All three inference cases used the saved stronger Whisper, IndicTrans2 and Abhishek IndicF5 selections, offline. No transcript/translation fixtures, imported generated takes, forced source language or temporary model selection were used. Background separation was disabled for these cases and is not newly certified.

| Case | Real result | Retained evidence |
| --- | --- | --- |
| Known source, 4-second sign-off excerpt | Complete 4.000-second video; full decode and audio/video/subtitle streams verified | One cue, real translation/speech/timing observations, four cue JSON artifacts and export identity |
| Full known source, 122.5-second excerpt | All 14 grouped cues translated; native duration preflight rejected the first cue: predicted 7.381 s, available 6.400 s | All 14 source/raw translated cues, 17 cue artifacts and failed timing-preflight operation; zero speech calls and no published dub |
| Independent source, first 8 seconds of `Sample/3.mp4` | Recognition rejected nonspoken output: “No spoken words were recognized” | Raw worker transcript and failed STT operation; zero translation/speech calls and no published dub |

Receipts:

- [Successful known excerpt](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-known-e955199a.json>).
- [Full-source timing failure](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-full-known-91f5371e.json>).
- [Independent-source recognition failure](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-independent-260aea04.json>).
- [Cross-checked evidence audit](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-evidence-audit.json>).

The successful excerpt's export hash is `a9475a10e1636774bea42e12ad41e6768c84bca4d57c286d7e377d665d476692`, identical to the earlier automatic excerpt. This is evidence that the instrumentation preserved that known output. It is not a new listening acceptance or general quality certification.

The evidence audit verifies original/excerpt source hashes, retained cue-artifact hashes, unique final cue identities, preserved source/raw translation text, cleanup and unchanged saved state. It also verifies that the previously accepted full Hindi video still matches its recorded hash.

The successful driver elapsed 238.890 s; the full-source failure 142.047 s; the independent-source failure 41.844 s. These are observations of these runs, not latency guarantees or a controlled before/after benchmark. The successful run's observed recognition/translation/speech calls took approximately 71.891/70.500/85.891 s, including runtime startup work.

The full-source failure shows why the next quality work needs an application dialogue-adaptation stage. Editorially shortened text in the accepted review video does not establish that raw automatic translation fits the source windows.

## 8. Automated checks

The first 153 focused checks passed. A broader 602-test host run then passed and preserved the real model registry. A subsequent 101 focused checks passed against later contract refinements. The final complete suite is recorded separately after adding failed-recognition evidence and Windows publication tests:

[Final backend regression log](<C:/Projects/Reflow Studio/docs/validation/2026-10-09-pipeline-foundation-backend-complete.log>).

This final log binds the tested production-source hashes and verifies that source files and the real registry stay unchanged during the run. The foundation test module covers deep-copy isolation, template routing, cast mapping, frozen selections, source-scoped identities, grouping lineage, original/raw/moderated text, partial failures, native duration rejection, raw failed recognition, credentials omitted from summaries, durable cue copies, temporary audio hashes/duration, concurrent observations, actual fallback identity, record-publication failures, successful subtitle execution, missing/no output, cancellation and state restoration.

**Final result: 607 tests passed in 151.820 s across 34 test modules**, including 26 foundation tests. The real model registry and all seven fingerprinted production files remained unchanged during the run. The earlier sandbox/initial-publication failures were retained as diagnostic evidence; they are not counted as successful validation.

No frontend source changed, so a redundant frontend build was not required for this backend increment. No live external API, new target language, new voice or new platform was certified.

## 9. Repair-plan progress and next work

This is a first implemented slice of A01–A03 in the architecture repair plan:

- **A01:** automatic cue/spec/run contracts and lineage are connected. Full review-contract migration and broader artifact/quality/capability contracts remain.
- **A02:** shared fixed-template mapping/compiler and frozen selections are connected. There is still no general graph executor or AI manager.
- **A03:** real source, cue, provider, timing, media and failure observations persist. General stage checkpoints, complete artifact retention, restoration and invalidation remain.

The next foundation increment should add stage checkpoints with explicit input/configuration/engine fingerprints and downstream invalidation. A failed timing check should be able to reuse verified recognition/translation without rerunning them. The common cue contract should extend through saved review operations with an honest migration of legacy provenance.

Then implement automatic dialogue adaptation against available cue windows, with meaning/completeness checks and bounded correction. The full-source timing failure provides a reproducible case for that feature. A quality supervisor should consume the saved evidence, preserve the best valid output and stop after a defined retry budget. The optional API/Ollama manager follows validated application operations. Training a specialist SLM remains deferred until evaluation/data justify it.

Multi-speaker identity mapping, measured resource estimates/scheduling, optional-runtime readiness consistency, clean portable provisioning and Linux/macOS release evidence remain in the architecture backlog. This increment does not mark ReFlow ready for release.

## 10. Implementation entry points

- [Shared plans/cue/snapshot contracts](<C:/Projects/Reflow Studio/core/pipeline_contracts.py>).
- [Durable run observations](<C:/Projects/Reflow Studio/core/run_manifest.py>).
- [Automatic pipeline integration](<C:/Projects/Reflow Studio/core/pipeline.py>).
- [Bridge integration](<C:/Projects/Reflow Studio/bridge/api.py>).
- [Foundation tests](<C:/Projects/Reflow Studio/dev/test_pipeline_foundation.py>).
- [Live validation driver](<C:/Projects/Reflow Studio/dev/verify_pipeline_foundation.py>).
- [Architecture audit and repair sequence](<C:/Projects/Reflow Studio/docs/ARCHITECTURE_AUDIT_AND_REPAIR_PLAN_2026-10-09.md>).
