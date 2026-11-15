# Graph layout and native control validation — 10 October 2026

## Outcome and scope

The Nodes page now gives the pipeline canvas, resource controls and render controls separate layout space. The estimate card and Start/Stop controls previously sat on top of React Flow. At the supported minimum-width window they covered later stages and could intercept clicks. Moving them outside the canvas prevents that overlap without changing pipeline order, accepted-job settings, model routes or device policy.

A second repair makes active-stage highlighting and edge animation follow the current render state even when the graph definition arrives late. Native validation also exercised a subtitle switch and a singleton voice change that remained open in the previous report.

This iteration uses existing dependencies and an isolated fixture. It includes no installs, downloads, live model inference, API calls, speech generation, user-data deletion or cache cleanup. Release readiness remains pending.

## Implementation

| File | Change and reason |
| --- | --- |
| `frontend/src/pages/Nodes.tsx` | Uses a shrinking flex canvas next to a fixed-width, independently scrolling resource sidebar. The render footer occupies its own row below both. `min-h-0` and `min-w-0` allow the canvas to shrink within available space. Named canvas/resource regions improve accessibility. |
| `frontend/src/pages/Nodes.tsx` | Projects each node's `active` property and each edge's `animated` property from the current render hook at rendering time. Previously, an asynchronous graph response could install values from the initial callback closure after the active-state effect had already run. No node position is changed by this projection. |
| `dev/verify_graph_controls.cjs` | Adds a contract check for late-loaded node/edge data while render state changes. Accepts an optional receipt path so later runs retain the previous iteration's evidence. Uses the existing TypeScript compiler and Node runtime. |

The resource sidebar is 18 rem wide. Device selection, worker selection, estimate disclosures and unknown-VRAM presentation remain available. The footer retains Start/Stop, progress, errors and still-working indicators. Modal batch confirmation and backend request handling are unchanged.

The full horizontal pipeline still becomes small in Fit View, especially with the existing global hardware sidebar visible. Users must zoom and pan for detailed editing. This repair removes obstruction; it does not claim that every node label is readable simultaneously at the minimum window size. Only the 1200 × 800 fixture window was checked natively in this iteration. Smaller heights, maximized windows, display scaling and active-render footer expansion still need visual checks.

## Native walkthrough and isolation

The existing `dev/run_control_walkthrough.py --graph` fixture ran against the rebuilt production frontend. Its owned directory is `C:/Projects/Reflow Studio/temp/native-controls-j6xpaute`. The fixture redirects registry, settings, preferences, graph and recovery storage before bridge modules capture storage paths. It contains one synthetic blue, one-second video and two explicitly fake voice checkpoints. Those checkpoint files are control fixtures, not usable model weights.

Its worker-start override records the actual request and returns “QA fixture: model execution is disabled.” This permits request-boundary validation without loading models. The separation-stage persistence rejection is deliberate fixture behavior retained from the previous iteration, not a newly discovered production failure.

The Windows Computer Use skill was used to inspect and operate only the owned “Reflow control walkthrough” window. Each state-derived input was followed by a refreshed observation. Some immediate captures showed the preceding frame; additional captures verified settled state before choosing subsequent controls. Screenshots were inspected during testing; saved evidence contains accessibility observations and bridge records, not archived screenshots.

| Action | Observed result and evidence boundary |
| --- | --- |
| Open Nodes | All ten stages appear in Fit View inside the canvas. The estimates occupy a separate sidebar and Start occupies a separate footer. No stage is underneath those controls. |
| Zoom in using controls and wheel | Translation, voice, lip-sync and subtitles become accessible for editing. Other stages leave the viewport as expected when zooming. Resource controls and the Start footer remain stationary outside the canvas. |
| Turn subtitles off | The node dims and its switch turns off. Final persisted graph has `subtitles.enabled=false`. |
| Confirm one guarded batch start | Captured render parameters contain `include_subtitles=false`. The fixture rejects execution and the application displays the reason. The queue item returns to `draft`; session is idle and not busy. No worker/model runs. |
| Change the only voice node from actor A to actor B | The selector updates to actor B, estimates clear while recalculating and then return. Final estimate flags use the same actor ID as the final graph cast. |
| Navigate to Dashboard | Dashboard's Voice Model selector also shows actor B. This validates singleton configuration sharing across the two pages. |
| Close fixture normally | The owned window closes and the fixture process exits with code 0. Its final receipt is retained. |

The guarded start occurred before the singleton voice change. This iteration therefore proves subtitle propagation at the render boundary and singleton voice propagation to graph, Dashboard and estimates; it does not claim a second render-boundary check for actor B. Multi-actor render-boundary validation remains documented in the previous graph-controls iteration.

## Verification and retained evidence

Nine frontend contract checks passed against the actual transpiled modules. The new check starts with stale graph metadata, changes the render stage/running state, and verifies both highlight activation/deactivation and edge animation without altering raw node data. Existing checks cover graph-switch projection, restored language/source/singleton labels, persistence and transport rejection warnings, actual Nodes wiring and render-parameter agreement.

Production build and lint both exit 0. Existing large-chunk, ineffective dynamic-import and lint warnings remain; this is not a warning-free build. No backend production code changed, so the complete backend suite was not rerun for this frontend iteration. The previous iteration's 748-test, 43-module pass remains historical evidence rather than a new result for this change.

Integrity verification confirms:

- Frontend source hashes match the current contract receipt.
- User-local `models.json`, `settings.json`, `graph.json`, `hardware_profile.json` and `ui_preferences.json` match recorded hashes from the prior iteration.
- The accepted video remains unchanged at SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`.
- Native subtitle state and guarded render parameters agree; singleton cast and final estimates agree; rejected start leaves the queue as a draft.

Evidence prefix: `docs/validation/2026-10-10-graph-layout-`:

| File suffix | Contents |
| --- | --- |
| `contracts.json`, `contracts.log` | Nine checks and tested source hashes. |
| `build.log`, `lint.log` | Build/lint output, including retained warnings. |
| `ui.json` | Initial Nodes text, subtitle-off observation, guarded rejection, actor-B graph and Dashboard accessibility trees. |
| `bridge.json` | Actual estimate flags/results, guarded-start request, final graph/cast, idle session and retained queue draft. |
| `integrity.json` | Source/state comparisons, accepted-video preservation, native boundary checks and process/build/lint exit codes. |

## Remaining work

1. Check the layout at minimum height, larger windows and display scaling, plus resource-panel scrolling and expanded active-render progress/error content. Consider a more compact graph overview or adjustable panels if detailed editing remains cumbersome.
2. Finish native language-menu changes, other optional switches, voice removal/return to singleton, and concurrent graph/config changes. No deletion was performed in this iteration.
3. Validate active job advancement, cancellation and genuine crash/relaunch/checkpoint reuse with authorized model execution. Contract tests for highlights do not establish those full workflows.
4. Calibrate resource estimates, resolve optional-engine readiness gaps, assess fresh full-video output, evaluate live hybrid assistance and complete clean-machine Windows/Linux/macOS packaging checks.

All retained fixtures are disposable test assets; no user models or videos were removed.
