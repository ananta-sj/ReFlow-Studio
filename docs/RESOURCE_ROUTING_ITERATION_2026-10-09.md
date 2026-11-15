# Resource routing and parallel planning — 9 October 2026

## Scope and authorization

The user authorized continued architecture work with live model calls deferred. This iteration traces processor selection and segment scheduling, repairs resource estimates for mixed execution routes, and verifies the shared load calculations. It uses existing dependencies, synthetic/provider fixtures and frontend tooling already installed in the project. No models, packages or frameworks were added; no weights were loaded; no inference, downloads or external provider requests occurred. The accepted dub is not regenerated.

The result is a more faithful planning estimate, not measured model throughput or guaranteed memory fit. Release, independent full-video acceptance and live quality validation remain pending.

## Audit findings

1. The combined `tts_rvc` estimate assigned speech generation and voice conversion to one device, even when execution uses different processors. An IndicF5 base model can use its separately selected CPU while an RVC actor uses the workspace GPU. The old override was additionally gated on the cast containing `CLONED_USER`, although non-F5 actors also use the base TTS before conversion. Generic F5 can instead use its optional CPU environment alongside other GPU speech routes.
2. GPU estimates were summed under the first non-CPU route. Fixed first-GPU recognition/translation and speech on another selected GPU could therefore be charged to the wrong processor. Dashboard and Nodes compared the same aggregate against the selected device's capacity.
3. Zero default memory for an unmodeled GPU stage could look like zero usage. Background separation has no calibrated/default model-memory budget in the current monitor, so a complete GPU budget cannot be claimed for that route.
4. Audio buffers were counted even in an internal text-only estimate; sequential speech also used the parallel two-worker-window formula. The nine-second clip assumption was not disclosed as an assumption.
5. Missing additional memory or telemetry could become zero in the gauge, and late estimate/hardware responses could overwrite the currently selected configuration/device's results.

These were found by reading existing execution/estimate code and checking fixture cases. No live mixed-GPU render or memory measurement was used to establish them.

## Processor and memory correction

`PythonBridge._speech_resource_components` builds the speech estimate from the requested cast and active base TTS, using the same route choices as execution. `CLONED_USER` adds base speech without a conversion model; non-F5 actors require base speech and their selected conversion; generic F5 voices bypass the base TTS. Duplicate voice IDs count once. Optional generic F5 uses CPU when its existing interpreter is ready; otherwise the current direct-provider workspace device remains the assumption. IndicF5 respects its `speech_device` for any actor that needs base speech, not only `CLONED_USER`. Unaccelerated `other:` adapters normalize to CPU, and `cuda` normalizes to `cuda:0`.

Device cost factors are applied to each speech component before composing the combined stage ETA. The combined stage then receives no second factor. Base speech cost plus the highest estimated conversion cost is a conservative per-cue heuristic when actor frequencies are unknown, not a measured weighted average. Existing model-size/default cost assumptions and monitor device factors remain heuristic. Increasing segment workers does not apply an unmeasured inference speed discount.

`peak_vram_by_device_mb` groups estimated local model memory under its actual route. CPU allocations do not become GPU memory. Unknown GPU stage memory propagates as `null` for that processor, even if another stage on that processor has a known estimate; an unknown allocation does not erase a different processor's known budget. The warnings identify the incomplete stage. These budgets add model estimates across enabled stages. They are deliberately labeled cumulative planning budgets, not observed simultaneous peaks; activation/workspace overhead can still exceed model-size heuristics.

The old `peak_vram_mb` field remains for response compatibility. It is the largest known per-device budget when all included GPU allocations have estimates, or `null` when one is incomplete. It is not the sum of separate GPUs and must not be compared indiscriminately against an arbitrary selected device. Updated Dashboard/Nodes use the per-device map. Older backend responses without that map remain supported by the shared helper.

API/local-service providers retain the existing convention of no app-managed model VRAM and no local GPU timing discount. Their service-side resources and latency are not measured here; a local service can consume resources outside this estimate. CPU model RAM is not included in `audio_buffer_ram_mb`; the interface explicitly says model memory is additional. GPU routes not observable to the main interpreter still represent configured routes, not newly established device availability. Existing setup/runtime inspection serves that separate purpose.

## Parallel processing and buffer contract

`core/parallel_policy.py:segment_buffer_window` centralizes the already-supported integer worker range 1–8 and the scheduling window. Sequential execution retains one segment; parallel execution keeps the existing `2 × workers` submission/mixing window. `_dub_all_segments` and the estimate use the same function. This does not add model-level concurrency: shared mutable inference remains serialized, while preparation/mastering can overlap and results mix in source order.

The CPU buffer approximation remains five full-length 48 kHz/four-byte PCM tracks plus the bounded segment window using nine-second clips. Sequential work now uses one clip rather than a parallel two-clip assumption. Only media stages count full-length audio tracks, and only speech counts segment buffers. Text-only internal estimates report zero audio buffers. The new warning explicitly states that longer clips require more RAM. This formula is not a memory cap, maximum clip-duration constraint or model-RAM estimate.

Invalid duration values (boolean, negative or nonfinite) fail before provider inspection. Zero duration is retained for the existing unreadable-probe convention; such an ETA is not a measured useful source duration. Dashboard currently requests estimates for video workflows; this iteration does not add a subtitle/audio-specific estimation UI.

## Dashboard and Nodes behavior

Both pages call `jobMemoryBudget` from `frontend/src/lib/eta.ts`. A missing allocation in a supplied per-device map means zero additional model budget on that selected processor; explicit `null` means unknown. No response is not silently converted into zero. `projectedLoadPercent` requires finite, nonnegative current use and additional budget plus finite positive capacity. Missing/invalid telemetry or budget yields no capacity claim.

The pages distinguish unavailable hardware readings from unknown model budgets, use the selected processor's budget for the gauge, list per-device budgets, and show estimate warnings. Pending requests clear earlier estimates/readings. Effect cleanup prevents older estimate/hardware responses from replacing a newer configuration/device selection; rejected requests leave the reading unavailable. No scheduling or start approval is silently added from these estimates. The existing high-load confirmation remains a heuristic, not a safety guarantee.

Frontend source/type build and shared-helper runtime checks validate the calculation contract. This iteration does not claim a new interactive browser/native-app walkthrough or visual layout acceptance.

## Validation

Existing focused tests passed **72 tests in 5.502 seconds** before adding the new resource fixtures. Final focused coverage passed **81 tests in 5.406 seconds**, including nine new resource cases. Logs: `validation/2026-10-09-resource-routing-focused.log` and `-focused-final.log`.

New cases cover CPU IndicF5 with GPU RVC and no cloned actor, optional CPU F5 with GPU base speech, duplicate voices, all-F5 bypass of an unrelated base model, fixed GPU translation with a different speech GPU, unknown memory propagation independent of stage order, text-only buffer exclusion, invalid durations, the shared worker window, unchanged ETA/model VRAM across worker counts, and unaccelerated adapter normalization. Existing serialization, out-of-order-window, mixing order, cancellation and provider integration tests remain included. Fixtures prove estimates/control flow, not actual models' resource consumption.

`dev/verify_resource_frontend.cjs` uses existing TypeScript plus Node's built-in assertions to execute the actual shared helper. All eight checks passed: selected-GPU versus aggregate, explicit unknown, absent allocation, older response compatibility, absent estimate, missing telemetry, invalid numbers and capped known capacity comparisons. Its source-bound receipt/log is `validation/2026-10-09-resource-routing-frontend-contracts.json/.log`. No testing framework was installed.

Frontend production build and lint passed; the existing bundle-size and unrelated lint warnings are retained in `validation/2026-10-09-resource-routing-frontend-build.log` and `-frontend-lint.log`.

Full backend validation passed **742 tests across 42 modules in 102.688 seconds**, with zero failures or errors. Receipt/log: `validation/2026-10-09-resource-routing-backend-complete.json/.log`. Final source hashes match the tested inventory, the frontend helper matches its source-bound runtime receipt, and saved registry/settings remained unchanged during the suite. The accepted editorial video remains unchanged with SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`. These assertions are recorded in `validation/2026-10-09-resource-routing-evidence-integrity.json`; they establish preservation and regression results, not actual model calibration or video acceptance.

## Files changed and remaining work

Production: `bridge/api.py`, shared `core/parallel_policy.py`, its use in `core/pipeline.py`, `frontend/src/lib/api.ts`, `frontend/src/lib/eta.ts`, Dashboard and Nodes. Regression additions: `dev/test_resource_routing.py`, the existing IndicTrans2 estimate assertion, frontend helper verifier, and backend runner's separate label/source inventory. `core/hardware_monitor.py` constants/heuristics are reused without a new hardware benchmark or model calibration.

Remaining gates include measured startup/throughput/activation memory, CPU model RAM and service resources, other adapter routing coverage, shared-memory platforms and physical multiple-GPU runs, interactive Dashboard/Nodes acceptance, and independent full-video/model-quality validation. Generic F5 remains import-unverified. Live assisted-review evaluation remains deferred. Release remains pending.
