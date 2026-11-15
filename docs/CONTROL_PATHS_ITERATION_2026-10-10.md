# Graph cast and estimate controls — 10 October 2026

## Purpose and authorization

This iteration continues architecture repair without live model calls. No engine, model, framework or dependency was installed. No inference, paid request or model download was initiated. Work covers the public estimate boundary and its Nodes refresh trigger, plus inspection of queue selection and a Windows regression-fixture correction.

## Problem and repair

Rendering resolves its cast through `_resolve_cast_list`: a graph with multiple Voice nodes supplies its actor choices; a singleton uses the shared Dashboard voice. Public `estimate_job` and `estimate_job_all_devices` previously passed incoming Dashboard flags straight to the resource calculator. Consequently, adding actors could change the render routes while estimates still represented one actor.

Both public estimate methods now obtain a graph-locked selection snapshot through `_estimate_selection`. It deep-copies caller flags and resolves the cast using the same method as render acceptance. A caller-supplied stale `cast_list` cannot override the current graph. The lock protects selection capture and is released before duration probing and resource calculation. The all-device method still probes duration once.

Nodes now includes its Voice-node choices in the estimate effect's dependency key. Adding, editing or removing a voice therefore requests a new estimate after the graph reload/local update. The existing cancellation guard prevents an older response from replacing the latest request's result. This does not alter the existing segment-alternation model or add speaker diarization.

## Exact source changes

| Source | Change |
| --- | --- |
| `bridge/api.py` | Shared graph cast snapshot at both public estimate entry points |
| `frontend/src/pages/Nodes.tsx` | Voice-node choice/count changes invalidate displayed estimates |
| `dev/test_resource_routing.py` | Regression fixture exercises singleton public estimation, graph-owned multi-cast all-device estimation, stale caller cast rejection and caller flag preservation |
| `dev/test_persistence_safety.py` | Accounts separately for injected and real Windows publication denials while retaining the exact attempt count, four-attempt bound, valid denial codes, final bytes and temporary-file cleanup assertions |
| `dev/verify_dialogue_backend.py` | Adds the `control-paths` receipt label and resource/publication test sources to the hashed inventory |

The new public estimate fixture substitutes duration probing and the calculator to isolate cast selection. Existing resource-routing tests exercise the actual calculator's CPU/GPU route splitting, actor deduplication, unknown memory, buffer bounds and text-only estimates. Neither group measures physical model resource use.

## Queue and recovery inspection

`useQueue()` filters the shared job store to `draft` and `queued` entries. Completed history is excluded from Dashboard/Nodes batch-start IDs. Batch acceptance freezes draft parameters, and the existing bridge checkpoint/rollback path handles a rejected worker start. These paths remain covered by the existing regression suite; no queue implementation change was warranted by this inspection.

Native source selection, active queue progression, cancellation and interrupted-job recovery are still separate acceptance gates. A disposable native walkthrough host was considered but was not created or run in this iteration. No new native UI acceptance is claimed. Previous native evidence remains in the earlier walkthrough and preference reports.

## Failed run and correction

The initial full suite ran 748 tests and failed one pre-existing Windows retry assertion: four attempts occurred where the fixture expected three. Its first two denials were injected; the real publication also needed a retry. Publication succeeded and the remaining suite passed. Production already retries eligible Windows denials up to four attempts.

An isolated rerun passed. Its first invocation failed to import `dev` because the embedded interpreter does not automatically include the workspace; the corrected invocation explicitly supplied the existing workspace/core import paths and passed. Both logs are retained. The fixture now checks that attempts equal three plus observed real denials, never exceed four, and that real denial codes are eligible. Permanent-denial/old-byte preservation coverage is unchanged. Production publication code was not changed.

The original full-suite log and receipt are preserved as `2026-10-10-control-paths-backend-initial.*`. Final results and integrity are recorded separately below.

## Remaining limits

Estimates remain uncalibrated heuristics, including known exclusions for downloads, service latency and some model/runtime memory. A matching cast selection does not establish measured ETA or safe capacity. Actual native multi-actor editing, file selection, populated estimates and recovery require interactive acceptance. Full model/video quality, live hybrid assistance and clean-machine/platform release validation remain pending. This iteration does not establish release readiness.

## Final validation and evidence

| Check | Result |
| --- | --- |
| Focused resource-routing tests | 10 passed, 0.048 seconds |
| Final full backend suite | 748 tests across 43 modules passed, 105.360 seconds; zero failures/errors |
| Production frontend build | Passed; existing large-chunk warning |
| Frontend lint | Passed; existing warnings |
| Tested source hashes | Match the final backend receipt |
| Saved settings/registry during suite | Unchanged |
| Graph, UI preferences, hardware, settings and registry | Match recorded end-state hashes from the previous iteration |
| Accepted video | Unchanged: SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2` |
| New native UI/model quality acceptance | Not performed |

Evidence uses the `docs/validation/2026-10-10-control-paths-` prefix: `focused.log`, `backend-initial.json/.log`, `backend-complete.json/.log`, `publication-recheck.log` (import-path invocation failure), `publication-recheck-corrected.log`, `frontend-build.log`, `frontend-lint.log`, `state-integrity.json` and `evidence-integrity.json`. The state comparison explicitly uses the prior iteration's recorded end-state rather than an invented before capture. Initial failures remain visible; the final complete suite passed after the fixture correction.
