# Graph controls, render flags and populated estimates — 10 October 2026

## Outcome

Fixed a graph-display race: a late graph load could restore saved switch values after shared render preferences had already been applied. Displayed optional switches now derive directly from the current shared render configuration, including after graph reloads. Rejected graph-mirror saves now produce a warning instead of silently failing. The graph's minimum zoom was lowered so the full-width pipeline can be zoomed out at the supported minimum window size.

Native disposable-state testing verified a populated CPU estimate, restored Hindi target/English source, voice duplication, independent second-actor selection, four-worker selection, estimate refreshes and the resulting render-start payload. Worker execution remained blocked. Final backend validation passed 748 tests across 43 modules in 93.562 seconds; eight frontend runtime checks, build, lint and integrity checks passed.

## Scope and fixture isolation

The user's instruction to continue development without live model calls remains active. No dependency, model, framework or runtime was added or downloaded. No provider inference or paid call was made. These are application control checks, not generated-audio or video-quality tests.

The existing native walkthrough host adds a `--graph` fixture mode. It uses fresh directories beneath workspace `temp/`, its own settings/graph/preferences/registry, a one-second synthetic blue video, and two explicitly labelled **QA actor A/B (fixture)** registry entries. Their checkpoint files contain short fixture text, not model weights. Their installed labels exist only to exercise available-voice controls and route estimation. The real registry and model connections are untouched. Estimated checkpoint memory from these tiny files cannot be used to calibrate real model memory.

The host seeds Advanced mode, completed fixture onboarding/tour, Hindi target, manual English source, actor A and background preservation off. It adds the synthetic source as one draft. Normal graph, voice, estimate and batch APIs run; `_start_worker` captures the request and returns a refusal before inference. To exercise a saved-graph mismatch and warning, `set_node_enabled` deliberately rejects the fixture's `separate` graph-mirror update. Other graph APIs remain real.

The host records calls to the actual all-device estimate method and its results. Raw graph cast is logged alongside those calls; for a singleton, actual estimation uses the Dashboard voice rather than the raw singleton graph default. The final multi-actor estimate and render request both use the graph's two actor IDs.

## Root cause and authority

Nodes previously loaded saved nodes asynchronously, while a separate effect copied optional flags into local node state only when shared configuration values changed. If the effect ran before the graph response, it updated an empty array; the later response then installed stale saved switches. An unchanged configuration value would not rerun that effect. A displayed switch could therefore contradict the flags sent for rendering.

`projectGraphNode` now accepts the existing shared stage map and projects each mapped optional flag onto the node definition. Nodes passes that same projected `enabled` value to `StageNode`. The separate synchronization effect was removed. Projection leaves source node definitions untouched, keeps unmapped/fixed node states, and retains existing source/language/singleton-voice display behavior. Multiple actor choices remain independent.

Shared render flags already own the optional stages of new jobs through `buildRenderParams` and the backend template contract. Graph switch storage is their mirror. A refused mirror write does not invalidate a user's future-job choice, and accepted jobs retain their frozen parameters. Therefore the repair reports mirror failure and retains the shared setting; it does not roll back the setting to a potentially stale graph flag. In the native rejection fixture, saved `separate.enabled` remained true while the displayed/rendered background choice remained false. The captured request contained `keep_bg: false`, as intended.

Direct Nodes switch changes still wait for their graph API result before updating shared configuration. Their existing rejection alert remains. No provider/pipeline execution contract was changed. Mirror requests remain asynchronous; this iteration does not introduce an atomic multi-setting graph transaction or certify concurrent edit ordering under an active render.

## Source changes

| File | Change |
| --- | --- |
| `frontend/src/lib/graph-config.ts` | Projects mapped optional `enabled` values from current configuration, with an optional mapping argument for existing callers |
| `frontend/src/pages/Nodes.tsx` | Passes projected definition/state directly to graph nodes; removes the timing-sensitive copying effect; sets minimum zoom to 0.1 |
| `frontend/src/lib/use-render-config.ts` | Reports rejected/exceptional mirror updates through console and the application's warning log; preserves future-job flags |
| `dev/run_control_walkthrough.py` | Adds isolated graph fixture mode, explicit non-model actors, an injected graph-publication refusal, estimate records and final graph/cast receipt fields |
| `dev/verify_graph_controls.cjs` | Tests actual transpiled projection/config/Nodes/render-parameter modules with existing TypeScript and Node fixtures |
| `dev/verify_dialogue_backend.py` | Adds the graph-controls label and new verification/render-mapper source hashes |

No global state file, runtime, model file or user media was changed by these repairs. Built frontend assets were regenerated from the modified sources.

## Native acceptance

| Step | Observed result and scope |
| --- | --- |
| Initial Dashboard | Restored Advanced mode, synthetic source, English source, Hindi target and actor A; a populated 5-second CPU estimate was present. The injected graph-save warning appeared in the real log panel. |
| Initial Nodes load | Source basename, Hindi target and actor A matched the shared configuration. Background separation displayed disabled despite the deliberately unchanged saved graph mirror. Backend/render receipts and component contract checks independently verify this disagreement was resolved by projection. |
| Voice duplication | Clicking the actual copy control created `tts_rvc_2`. The base actor A was saved before the graph became multi-cast; the new voice began with the engine/reference default. |
| Independent actor edit | The second voice's native select was opened and actor B chosen. A mouse action over WebView's popup was refused by the helper; after fresh activation/state capture, keyboard End/Return applied the observed last option. The first actor remained A. |
| Worker control | Four workers were selected in the actual interface; the estimate cleared while refreshing, then returned with its revised buffer estimate. |
| Render acceptance boundary | Start Batch reached the guarded worker boundary with `lang: hi`, `source_language: en`, both actor IDs, `keep_bg: false`, CPU device and `parallel_workers: 4`. The UI displayed the deliberate refusal; the draft and idle session remained intact. |
| Rebuilt viewport | A separate fixture launch used the final frontend build. At 1200-pixel window width, the input node was within the canvas and Zoom Out was available instead of disabled at the previous minimum. The estimate overlay still covers part of the canvas; this does not claim every stage is simultaneously unobstructed or comfortably readable. |

The functional actor/worker trace preceded the zoom-limit-only revision. The final component checks bind to final source hashes, and the separate rebuilt viewport trace checks the zoom revision. Both fixture processes exited normally and their receipts/state are retained. No native actor removal, explicit deletion, language-menu change, arbitrary source navigation, actual GPU job or model render was exercised.

## Estimate evidence and interpretation

For the same two-actor CPU fixture, one worker estimated **2.6 MB** of audio buffers and a segment window of one. Four workers estimated **14.1 MB** and a window of eight. The displayed rounded values were about 3 MB and 14 MB. ETA remained **5 seconds** in both cases, consistent with the existing minimum and absence of an assumed inference speedup.

The final speech-component IDs match the cast IDs captured at the render-start boundary. This establishes selection consistency. It does not establish model quality, actual elapsed rendering time, physical memory consumption, measured worker throughput or GPU capacity. Nine-second buffer assumptions, extra model RAM and uncalibrated estimates remain disclosed. The CPU's projected GPU load correctly remained “VRAM unreadable,” rather than inventing a capacity figure.

## Validation and failures retained

| Check | Result |
| --- | --- |
| Complete backend suite | 748 passed, 43 modules, 93.562 seconds; zero failures/errors |
| Frontend runtime checks | Eight passed: all mapped flags after late load; unmapped states; source/language/voice projection; rejected restore; rejected future choice; transport exception warning; actual Nodes wiring; render-parameter agreement |
| Frontend production build | Passed; existing large-chunk warning |
| Lint | Passed; existing warnings |
| Tested source hashes | Current files match final backend/frontend receipts |
| User-state integrity | Settings, registry, graph, preferences and hardware profile match prior recorded state |
| Accepted video | Unchanged SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2` |

The first frontend harness invocation captured its simulated hook's initial state before the restore notification, causing an English-versus-Hindi assertion failure. The harness now waits for restore and uses the subscriber's latest snapshot. Its failed log is retained. An initial integrity command used Windows' default text encoding for UTF-8 UI observations and failed decoding; the final command explicitly reads UTF-8 and passed. Neither failure required an application runtime or model change.

Evidence uses `docs/validation/2026-10-10-graph-controls-`: `backend-complete.json/.log`; `frontend-contracts.json/.log`; `frontend-contracts-initial.log`; initial/final build and lint logs; `ui-observations.json`; `workflow-bridge.json`; `viewport-bridge.json`; `evidence-integrity.json`. Original disposable directories are listed in the integrity receipt. Screenshots were inspected during the walkthrough; observation text and bridge records distinguish native acceptance from module fixtures.

## Remaining work

1. Improve the graph/estimate-panel arrangement so controls do not obscure stages; verify readable editing and layout at supported sizes. The lower zoom limit addresses clipping, not the complete layout.
2. Finish native optional-switch edits, actual language-menu switching, singleton changes, actor removal/return to singleton, and concurrent/active-work graph/config behavior. Restored language labels are verified; native language changes remain open.
3. Verify active job advancement/cancellation and genuine crash/relaunch/checkpoint reuse with authorized model execution. Current guarded starts do not replace those tests.
4. Calibrate CPU/GPU/service resources, resolve remaining optional-engine readiness gaps, assess independent full-video/model quality, evaluate live hybrid assistance and validate clean-machine/platform packaging.

Release readiness remains pending.
