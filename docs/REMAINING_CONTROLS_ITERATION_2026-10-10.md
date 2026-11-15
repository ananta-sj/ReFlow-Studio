# Language, optional stages and graph failure handling — 10 October 2026

## Outcome

Native control validation now covers changing source language from English to Auto and target language from Hindi to Spanish, enabling lip sync, enhancement, content filtering, audio-stem export and subtitle burn-in, and carrying those choices through graph display, estimates and the actual render-start request. The isolated fixture prevented model execution. This validates control plumbing, not Spanish dubbing quality or execution of those engines.

Two frontend failure paths were repaired: bridge exceptions during direct graph edits now produce a visible explanation, and older graph responses can no longer overwrite a newer reload. Frontend fixtures also verify the shared voice selection returns to the remaining actor after an extra voice node is removed.

No new framework, dependency, model, runtime, API connection or paid call was added. No user data was removed. Release readiness remains pending.

## Repairs and implementation boundaries

| File | Change |
| --- | --- |
| `frontend/src/lib/graph-actions.ts` | Small application helper, using the existing confirmation UI, that returns a successful bridge acknowledgement or `null`. Rejections display their supplied reason. Exceptions explain that the backend may have received the request and advise refreshing before retrying. |
| `frontend/src/pages/Nodes.tsx` | Routes toggle, parameter, duplicate, remove and position mutations through the helper. Local selections update only after successful acknowledgement. Failed position writes reload the graph. |
| `frontend/src/pages/Nodes.tsx` | Numbers graph-definition requests. Responses and errors from older requests are ignored. Unmount cleanup invalidates outstanding reads. Current read failures display “Graph could not be loaded.” |
| `dev/verify_graph_controls.cjs` | Expands the existing actual-module harness to 14 checks, including graph action exceptions, real page callbacks, read ordering/unmount behavior and return to singleton. |
| `dev/run_control_walkthrough.py` | Records successful optional-node mutations and the owned fixture's final UI preferences in its receipt. Existing worker-start guard and fake actor files remain in use. |

Previously, direct node callbacks awaited bridge methods without catching transport exceptions. Those exceptions could escape the event handler without explaining why the edit failed. The helper now handles that case without pretending the backend rejected or rolled back an operation it might already have committed. It does not automatically retry, since retrying an uncertain duplicate/remove operation could produce a second mutation.

The read-order guard addresses asynchronous graph reloads. It does not serialize simultaneous mutations, create an atomic transaction across all settings, or settle differing mutation completion order. Edits already started when the page unmounts may still complete at the backend. Active-job configuration behavior and additional concurrent-edit cases remain open.

## Native walkthrough

The existing Windows Computer Use skill operated only the rebuilt “Reflow control walkthrough” window. The fixture directory is `C:/Projects/Reflow Studio/temp/native-controls-16ozhdr2`. All registry, preferences, graph, settings and recovery paths are redirected into that directory before bridge modules capture their storage paths. The media is a synthetic one-second blue video. Actor checkpoint files contain fixture text, not actual voice-model weights.

Manual input detection paused the walkthrough. The user confirmed the test window could remain idle. Further input attempts were also rejected until a fresh window-state capture cleared the stale observation; testing continued with refreshed observations. No other application was operated. Screenshots were inspected during the walkthrough; saved evidence contains accessibility text and bridge receipts.

| Native action | Result |
| --- | --- |
| Select Auto source language | Dashboard shows Auto. Saved fixture preferences, estimates and guarded render parameters contain `source_language=auto`. This does not validate actual language detection. |
| Select Spanish target language | Dashboard shows Spanish; the Nodes translation label reads `Spanish (es)`. Saved preferences, estimates and guarded parameters contain `lang=es`. |
| Enable lip sync, enhancement and content filtering | Dashboard switches turn on, corresponding graph nodes are enabled in the final graph receipt, and estimates/render flags agree. |
| Enable audio stems and subtitle burn-in | Both controls turn on. Subtitle size appears after burn-in is enabled. Estimate input flags and render parameters contain `export_stems=true` and `burn_subs=true`. Including subtitles remains on. |
| Start from Nodes and confirm the batch | Confirmation names Spanish. The actual request reaches the fixture worker boundary with all six optional flags enabled and `keep_bg=false`. Execution is rejected with the deliberate “model execution is disabled” explanation. The queue returns to a draft; session is idle and not busy. |
| Zoom to the separation node and attempt to enable it | Fixture deliberately rejects graph publication. “Node change unavailable” displays the supplied reason. The displayed switch remains off and shared `keepBg` remains false. The raw fixture graph retains its deliberately stale separation value; this is why the shared render configuration projects the visible node state. |
| Close the fixture normally | Window closes, process exits 0 and final receipt is retained. |

Enabling additional stages changed the displayed CPU estimate from 5 seconds to 13 seconds. This is a heuristic response to selected stages, not measured rendering performance. The estimate continued to disclose uncalibrated budgets, unknown CPU VRAM and audio-buffer assumptions. Fake actor-file sizes make this fixture unsuitable for memory calibration.

No node or user file was removed through the native UI. The return-to-singleton path was checked through the actual frontend callback with a controlled bridge response, alongside existing backend removal tests; it is not recorded as native removal acceptance.

## Validation

- **14 frontend contract checks passed.** New coverage exercises both returned rejections and thrown exceptions; toggle/parameter/duplicate/remove callbacks retain choices when transport fails; position failure requests a reload; newest graph read wins; obsolete errors and unmounted reads are ignored; removal of an extra actor returns shared selection to the surviving singleton. Prior projection and render-parameter checks remain included.
- **39 focused backend tests passed in 5.961 seconds.** `dev.test_deletion_safety` includes graph parameter restrictions, cast ordering/ID allocation after middle removal, graph persistence and publication rollback. These tests use owned fixtures.
- **Production build and lint passed**, with existing warnings. No backend production code changed, and the full backend suite was not rerun for this iteration. The previous 748-test result remains historical evidence.
- Source hashes match the tested frontend receipt. The five user-local state files (`models.json`, `settings.json`, `graph.json`, `hardware_profile.json`, `ui_preferences.json`) match the prior recorded hashes.
- The accepted video remains at SHA-256 `0e4dc4a51253b5b4a0172ec2842647f0f2b643480135d6c27e4876b0442bf0a2`.

Evidence prefix: `docs/validation/2026-10-10-remaining-controls-`:

| Suffix | Contents |
| --- | --- |
| `contracts.json`, `contracts.log` | 14 actual-module checks and source hashes. |
| `backend-focused.log` | All 39 focused backend checks and elapsed time. |
| `build.log`, `lint.log` | Build/lint outputs and retained warnings. |
| `ui.json` | Source Auto, Dashboard settings, Nodes Spanish label, guarded start rejection and direct-node rejection observations. |
| `bridge.json` | Estimates, enabled-node mutation receipts, render-start parameters, final graph/cast, queue/session and fixture preferences. |
| `integrity.json` | Source and user-state comparisons, native flags/language agreement, rejection handling, video preservation and process/test outcomes. |

The script searches initially used a PowerShell wildcard as an `rg` filename, which `rg` treated literally. Searches were corrected to use `-g 'test_*.py'`; this affected discovery only. Manual-input rejections affected automation timing, not application behavior. No application test failure occurred in this iteration.

## What remains

1. Native removal/return-to-singleton and direct success edits of every optional graph switch remain unverified natively. Current native optional-stage success coverage comes from Dashboard; the direct node rejection is verified. Additional concurrency cases remain open.
2. Check minimum-height, display scaling, maximized layout and resource-panel overflow, including expanded progress/error content during active rendering.
3. Verify real queue advancement, cancellation, failure handling and crash/relaunch/checkpoint reuse. A guarded rejected start cannot establish successful processing or recovery.
4. Run authorized model-based, independent full-video validation; measure actual CPU/GPU resources and worker throughput; resolve remaining engine/download readiness gaps; evaluate live hybrid assistance; complete clean-machine packaging across supported platforms.

Live model testing remains deferred under the user's earlier instruction. The next useful development work is active-job control/recovery validation with isolated workers, while keeping genuine model/end-to-end acceptance clearly separate.
