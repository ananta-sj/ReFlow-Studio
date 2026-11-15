# Portable app walkthrough — 10 October 2026

## Scope and authorization

This iteration follows the user's instruction to continue development without live model calls. It checks the existing Windows portable application's actual pywebview interface, rather than treating frontend builds or mocked browser pages as interactive acceptance. Computer Use inspected the application through its returned native window and accessibility state. No new package, framework, model or evaluation service was installed. No speech/translation inference, model download, paid call, render, deletion or factory reset was initiated.

The walkthrough is partial. It does not establish release readiness or independent full-video quality. The last full backend regression result before this iteration was 742 tests across 42 modules; that historical result remains in its original receipt.

## Startup and method

Reflow was not initially running. The existing `build/windows-portable/python.exe -B main.py` was launched. An initial detached hidden launch did not leave a targetable process; a terminal-managed launch produced the real Reflow Studio window and completed boot. The frontend was loaded from the actual `frontend/dist/index.html` file URL. No alternate HTTP application or fake bridge was substituted.

Startup initially showed “CONNECTING TO PYTHON CORE…”, then “OPERATIONAL” and the integrity message “Runtime imports verified. Model assets are checked when selected.” This describes the startup library check only; optional model execution remains unverified.

Accessibility and screenshots were inspected together where useful. The screenshot immediately following an action could still show the previous painted frame; later observations confirmed the loaded view. Consequently transient first captures were not treated as failures.

## Observations and repairs

| Area | Actual observation | Result |
| --- | --- | --- |
| Basic Dashboard | Video template, source/target selectors, setup checks, reference selector and disabled start button loaded | Navigation/empty-source state observed |
| Voice selector | Default `CLONED_USER` had no corresponding dropdown item; there were no installed voice-category entries, so its display was blank | Repaired |
| Setup check | Selected Hindi translation and speech engines with English target reported “Needs setup”, with explicit Hindi-only limitations | Correct mismatch disclosure observed; no model loading |
| Advanced mode | Advanced configuration, estimates placeholder and Nodes navigation appeared | Observed |
| Nodes | Ten stage nodes, fixed edges, optional switches, voice combo, parallel worker selector and device selector loaded | Initial graph/control presence observed |
| Recognition node | Read-only label said “Whisper (CPU)” despite a pinned recognition engine being selected in the registry | Repaired to display the active engine's name |
| Empty queue | Assets showed “No videos queued”; pause/resume were disabled and start controls stayed disabled | Observed |
| Marketplace | Recommendations, stage tabs and existing connections loaded | Browsing observed; no download/connect/search action submitted |
| Local file dialog | Add Video opened the real native Open dialog | Open/cancel observed; successful selection and subsequent estimate display not verified |
| Restart | Rebuilt Dashboard showed the repaired voice label, but Advanced reset to Basic | Voice repair verified; preference persistence gap recorded |

### Voice-selector implementation

`frontend/src/pages/Dashboard.tsx` now includes the backend's existing `CLONED_USER` value as “Use selected speech engine / reference audio”. This describes the selection without promising speaker identity: a selected speech engine may use its own configured reference. The selector has an accessible “Voice Model” label and a missing-selection placeholder. Installed voice entries remain additional choices; no model selection was automatically changed.

The actual rebuilt portable Dashboard displayed “Use selected speech engine / reference audio” after restarting. A subsequent dropdown-opening automation attempt returned “coordinate input geometry is unavailable”, so opening and selecting the option was not successfully verified through that tool. The visible selected-value repair is verified; the report does not equate it with a completed dropdown interaction test. A non-empty stale voice ID may still require explicit visible fallback handling, because Radix placeholders are not guaranteed to display for a non-empty unmatched value.

### Recognition-node implementation

`bridge/api.py:get_graph_definition` now reads the active STT entry and displays its name in the recognition node. When no STT entry is selected it reports “Built-in Whisper (CPU)”. A nameless selected entry uses “Selected recognition engine”. This avoids making an incorrect CPU claim for an optional pinned GPU route; it does not add hardware discovery or promise that a selected engine can run.

This is a response-only label: saved graph values are not rewritten. The graph's `CLONED_USER` option uses the same descriptive wording as Dashboard. A regression test checks active selection, fallback and preservation of stored node values using a disposable in-memory graph and mocked registry. No real registry mutation or model creation is involved. The final Python label repair has backend test coverage; it was made after the second app launch and was not rechecked in a third native launch.

## Issues still open

1. **Restart persistence.** The native accessibility tree identifies the WebView as `[InPrivate]`. `main.py` calls `webview.start()` without a persistence policy; the frontend stores experience/render preferences in localStorage. Advanced became Basic after closing and restarting. This demonstrates experience-level loss; other cosmetic/render preferences still need individual restart checks. Prefer an explicit local persistence design and storage ownership, rather than assuming browser localStorage survives the current session settings.
2. **Graph mirrors and single-voice controls.** Source inspection found the language node reads its saved/default graph value, while execution uses the shared Dashboard configuration. Single-voice graph changes need a control-flow audit: `_resolve_cast_list` uses Dashboard's `params['voice']` unless there are two or more graph voices. These are code-supported concerns, not completed interactive reproductions in this walkthrough. Do not call them fixed.
3. **Existing pending registry connections.** There are 37 voice entries named “pending” with status `not_downloaded`. They were already present in the before snapshot and are preserved. Their origin/replacement value is not established here; deleting them would be unjustified. This explains why Dashboard's installed-only list had no extra voice options. It does not imply that the active Hindi TTS model is missing.
4. **Device visibility.** This launched core session exposed only CPU in its device selector. The selected pinned recognition/translation engines use separate runtime routes; the setup panel disclosed that distinction. GPU selector capability and separate-runtime device discovery still need inspection outside this walkthrough. CPU-only display is not proof the installed NVIDIA GPU or optional GPU engines are unusable.
5. **File selection automation.** The tool reported an unavailable element index and continued to report focus on Search Documents after attempts to focus File name. No path was typed into that uncertain focus. Escape closed the dialog, with no queued source. This is an automation limitation observed during testing, not evidence that a human cannot select a file. Source selection, populated estimates, start-confirmation, active cancellation, queue advancement and interrupted-render prompts remain interactive acceptance gates.
6. **Model and release gates.** Optional generic F5 import remains unverified after its existing timeout; actual model execution, independent fresh-video synchronization/background/export, resource calibration, hybrid live-model quality and clean-machine/platform packaging remain open.

## State changes and preservation

The before snapshot recorded hashes for `settings.json`, `models.json` and `hardware_profile.json`; `graph.json` did not exist. Startup/config restoration created `graph.json` through the existing optional-node synchronization path. This is an actual state change and must not be reported as “all saved state unchanged”. No node positions, voice choices or stage toggles were deliberately edited during the walkthrough. Advanced was selected for inspection and reverted on restart in the private session.

The final integrity receipt compares the three existing state files, records graph creation separately, and checks the accepted video SHA-256 against its previously recorded value. The accepted video was not processed or modified.

## Validation and evidence

- Frontend production build passed; existing large-chunk/plugin-timing warnings remain.
- Frontend lint passed with existing warnings; no lint error was reported.
- Focused architecture checks passed **35 tests in 0.674 seconds**, including the new selected-recognition-label regression.
- Full validation passed **743 tests across 42 modules in 108.610 seconds**, with zero failures/errors. Tested sources matched their recorded hashes. Existing settings, model registry, hardware profile and the accepted video were unchanged; the previously absent graph file was created by normal startup. Fixture log messages about failed workers describe simulated failure-path tests, not live engine execution.
- The verification runner now accepts an ISO `--date` and the `ui-walkthrough` label so this iteration cannot overwrite the 9 October receipts. Existing invocation defaults remain compatible. Its source inventory includes the modified architecture test module.

Evidence files:

- `docs/validation/2026-10-10-ui-walkthrough-state-before.json`
- `docs/validation/2026-10-10-ui-walkthrough-frontend-build.log`
- `docs/validation/2026-10-10-ui-walkthrough-frontend-lint.log`
- `docs/validation/2026-10-10-ui-walkthrough-backend-focused.log`
- `docs/validation/2026-10-10-ui-walkthrough-backend-complete.log`
- `docs/validation/2026-10-10-ui-walkthrough-backend-complete.json`
- `docs/validation/2026-10-10-ui-walkthrough-evidence-integrity.json`

## Next development work

Resolve frontend preference ownership and graph/config mirrors before calling the UI acceptance complete. Revisit source selection/populated estimates and review controls with reliable native targeting. After those repairs, perform independent model-backed full-video validation under explicit authorization for live inference. Keep local quality supervision optional, with manual candidate acceptance and no silent external calls.


## Follow-up

The preference persistence and graph display/control concerns were addressed in [the subsequent iteration](<C:/Projects/Reflow Studio/docs/PREFERENCE_GRAPH_ITERATION_2026-10-10.md>). Actual Advanced restart and selected recognition label were verified; complete native actor-edit, language-selection and populated-estimate acceptance remain open. Historical observations above describe the earlier build.
