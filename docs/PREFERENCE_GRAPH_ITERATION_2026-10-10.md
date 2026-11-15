# Preference persistence and graph configuration — 10 October 2026

## Outcome

Reflow now saves its own interface preferences outside the private WebView session. Advanced mode survived a close/relaunch of the actual Windows portable app. The Nodes language, source filename and singleton voice display derive from current render configuration; voice edits in a singleton node update Dashboard's rendering choice. Multiple voice nodes retain independent selections, with explicit transitions when adding/removing instances.

Validation passed **747 backend tests across 43 modules in 97.031 seconds**, eight frontend runtime contract checks, production build and lint. This is architecture/control-flow evidence, not speech or translation quality validation. Release readiness remains pending.

## Scope

The user authorized continued development while deferring live model calls. No new dependency, framework, model, service, download or paid request was introduced. Tests use the existing Python, TypeScript, Node, JSON/file-lock infrastructure and disposable fixtures. Native inspection uses the existing Computer Use plugin. The app's ordinary boot imports were allowed; no TTS/STT/translation inference was started.

The private WebView mode remains unchanged. No browser cookies, account state or browser profile were made persistent. App-owned state is stored separately from Python engine settings and model registry connections.

## Why the repair was needed

The previous actual app walkthrough showed Advanced resetting to Basic after restart. The frontend stored experience level, render configuration, theme, accent, tooltip visibility and tour completion in localStorage, while pywebview opened an InPrivate session. Module comments promised restart persistence that this session configuration did not provide.

Two graph/config mismatches were also found in source inspection. The translation node displayed its saved/default language instead of Dashboard's actual target. The bridge resolves a single actor from Dashboard's `voice` parameter, so changing only a singleton graph node's saved voice could leave rendering on a different voice. A graph with two or more actors intentionally uses its independent per-node choices.

## Preference storage

`core/ui_preferences.py` owns `ui_preferences.json` next to the application configuration. It reuses `JsonStore` transactions, cooperating-process file locks, atomic publication and corrupt-byte recovery. Only six app-owned keys are accepted:

| Key | Value validation |
| --- | --- |
| `reflow-theme` | dark or light |
| `reflow-experience-level` | basic, advanced or expert |
| `reflow.accentColor` | six-digit hex color |
| `reflow.helpTooltipsEnabled` | true/false string |
| `reflow.tourComplete` | true/false string |
| `reflow.renderConfig` | JSON object of known render preference fields |

Values are bounded to 16,384 characters. Render fields use explicit boolean types, bounded integer ranges, known template IDs, known target/source language codes, bounded non-empty voice strings and nullable reference-audio paths. Arbitrary fields such as API keys and device IDs are rejected. Device IDs are not added as a new persistent preference by this iteration. Unknown/invalid updates leave the last saved file intact.

Reference-audio paths and model identifiers are app preferences, not proof that files or models remain available. Existing setup checks must continue to validate selected routes. This file does not contain media data or provider credentials.

`PythonBridge` exposes `get_ui_preferences` and `update_ui_preferences`. The backing object is private and marked non-serializable, so pywebview does not traverse the store/file-lock objects when building its API surface. Existing persistence warning handling is reused.

## Frontend hydration and writes

`frontend/src/lib/preference-storage.ts` is the single frontend storage boundary. `main.tsx` loads saved preferences before mounting React, so initial theme/experience/render hooks read the restored cache rather than writing defaults over it. The six existing hooks use this boundary; Python settings defaults remain the first-run seed when no saved render configuration exists.

Only the six app-owned keys are considered for migration from an existing localStorage session. Saved JSON preferences take precedence. Migration submits individual keys so an invalid legacy value does not block otherwise valid keys. The private session is not converted into a persistent browser profile.

Changes update the session cache immediately and serialize their bridge writes in user order. Identical values skip redundant writes. Failed writes warn in the console and, where available, the application log; they do not claim success or automatically retry. A subsequent different edit can save again. The normal custom-window close action waits for queued writes. Native Alt-F4/forced termination/power loss are not guaranteed to flush an in-flight preference write; atomic publication protects the previously saved file.

The render hook subscribes before loading defaults. Previously, a synchronous restored-config path could notify before the first subscriber existed. A runtime check now confirms that a restored Hindi render configuration reaches the first mounted subscriber.

## Nodes/config behavior

`frontend/src/lib/graph-config.ts` projects the node display from current shared configuration without rewriting saved layout or stored values:

- Language follows the selected target and displays no-translation mode explicitly.
- Input filename follows the first queued source.
- One voice node displays Dashboard's voice.
- Two or more voice nodes keep their own choices.

After a successful singleton voice edit, Nodes updates the shared render configuration. Callback decisions use current node/config refs, avoiding the original empty-state callback closure when the graph loads asynchronously.

Before adding a second voice node, Nodes saves the current singleton choice into the base graph node. If that save is rejected, duplication stops and displays the rejection. The newly added node retains the backend's existing default; this does not invent automatic speaker recognition or clone all node parameters.

When removing instances leaves one actor, the remaining actor's saved voice becomes the shared Dashboard voice. When two or more actors remain, independent cast selection continues. These asynchronous handler transitions compile successfully but have not yet received a complete real-interface multi-actor interaction test.

The recognition label repair from the previous iteration was also confirmed in the actual Nodes screen: “Whisper — stronger recognition” replaces the misleading static “Whisper (CPU)” label for the selected route. This is a selected-engine label, not a GPU execution guarantee.

## Native observations

The existing portable app was launched twice from its real source entry point and built frontend. On the first launch, Basic was selected initially. Advanced was clicked in the real interface and the local preference file showed `advanced`. The idle app was closed. On the second launch, Advanced was highlighted, the Nodes navigation was present and Advanced configuration was visible. The accessibility tree still identified the page as InPrivate. This verifies application-owned preference persistence without changing browser-session privacy.

The Nodes screen loaded its ten stage nodes and selected recognition label. Basic was restored after testing, and the idle app was closed. No graph switch, position, actor instance or model selection was deliberately changed.

Native automation had intermittent geometry/index problems: an initial accessibility-index click reported unavailable geometry; a screenshot-backed refresh enabled the Advanced action. Attempts to select Hindi through the language menu did not complete reliably. The target remained English. Hindi label projection and restored Hindi configuration are covered by runtime fixtures, not a claimed native language-selection acceptance. The observation receipt retains actual restarted Dashboard and Nodes document text.

## Validation

| Check | Result and scope |
| --- | --- |
| Backend full suite | 747 tests, 43 modules, 97.031 seconds; zero failures/errors |
| Preference focused suite | Four tests, 0.137 seconds; fresh-instance restore/merge, invalid update preservation, corrupt-byte recovery, failed publication preservation |
| Frontend contract suite | Eight checks on transpiled actual modules; private-cache absence, ordered writes, second module session restore, unknown-key rejection, first render subscriber, singleton/multiple voices and language/source labels |
| Production frontend build | Passed; existing large-chunk warnings remain |
| Lint | Passed with existing warnings |
| Native restart | Advanced persisted through actual close/relaunch; original Basic restored afterward |
| Integrity | Backend/frontend receipt sources match; accepted video unchanged |

A lint invocation from the project root failed because its package script resides under `frontend`. Its failed log is retained as `2026-10-10-preference-graph-frontend-lint-final.log`; the correct invocation passed and is recorded in `...frontend-lint-complete.log`. Earlier successful build logs are retained separately from the final build. The verification runner adds this iteration's label and modified source inventory, preserving historical receipts.

## State/evidence

The existing `settings.json`, `models.json`, `hardware_profile.json` and `graph.json` match their before hashes. The previously absent `ui_preferences.json` was created intentionally and ends with Basic mode plus the existing render defaults. Its companion lock file is part of the existing cooperating-process storage design. The accepted video remains byte-identical to the recorded SHA-256. No pending registry entries or caches were removed.

Evidence lives in `docs/validation/` under the `2026-10-10-preference-graph-` prefix: state-before JSON; focused/backend-complete logs and receipt; final frontend-contract receipt/log; build-complete and lint-complete logs; native-observations JSON; evidence-integrity JSON. These distinguish fixture control-flow coverage from actual native observations.

## Remaining work

1. Complete real-interface single/multiple actor edits, duplication/removal, language switching and the configured render payload checks.
2. Audit graph optional-stage update rejection/rollback and asynchronous graph reloads against active job state. This iteration does not redesign that existing synchronization path.
3. Check resource estimates against an actual graph cast, rather than only Dashboard's singleton selection. Populated estimates, file selection, queue advancement and active cancellation/recovery still need interactive acceptance.
4. Verify individual theme/accent/tooltip/tour/render preferences over a native restart; the shared persistence boundary and fixture tests do not constitute separate visual acceptance of every hook.
5. Complete independent full-video/model-backed validation, generic F5 readiness, resource calibration, live hybrid quality evaluation and clean-machine/platform packaging under their required authorization. No release-ready claim follows from the current test count.
