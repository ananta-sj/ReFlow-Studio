# Source-language interface and build clearance — 2026-10-03

## Authorization and delivered behavior

The user approved adding the source-language selector and detection feedback, temporarily restoring existing npm dependencies, rebuilding/verifying the frontend, then removing the restored build dependencies and cache. This report covers that interface stage and its small backend event bridge. No new package, framework, AI model, or external testing library was added. No commit, push, or deployment occurred. Existing uncommitted work was preserved.

The Dashboard now offers a separate Source Language selector with Auto and the backend's 28 reviewed source choices. The target selector is labeled Target Language. Every video, audio, and subtitle request includes source_language independently of lang. Manual choices are saved in the existing render configuration and restored on subsequent loads. Old saved configurations without this field migrate to Auto. Missing/blank source values in saved configuration also default to Auto.

The selector is disabled during a render so its value cannot suggest that an in-flight job changed source. Source choices are fetched from the backend rather than copied into frontend code. A catalog fetch failure produces a visible error and disables the selector. Manual mode explains that the remembered choice applies to future jobs and overrides translation, not transcription. Auto explains the 80% requirement for M2M100/NLLB. Subtitle mode explains that there is no audio detection and fixed-vocabulary providers require a manual choice. Selecting a catalog entry does not certify that the active translation engine supports it; existing exact-map checks produce errors for unsupported choices.

During a render, the report displays the detected language and confidence separately from the translation source. A manual override can therefore display detected Hindi and selected French without mislabeling either. Missing language/confidence is shown as unavailable. Unresolved Auto explains that fixed-vocabulary translators need manual selection while prompt-based translators may infer the source. A short note explains that confidence does not establish accuracy or a monolingual recording. The report includes the current input filename and remains visible on normal completion/error in the mounted Dashboard.

Confidence percentages are displayed to two decimals, rounded downward. This prevents a value just below 0.80 from appearing as an accepted 80.00%. Raw confidence and backend decisions are not altered. Provider labels are rendered as React text, so markup in a label is escaped.

## Changes by file

### frontend/src/lib/api.ts

Adds optional source_language to the existing RenderParams interface. Optional typing keeps legacy interrupted-job payloads valid. Adds SourceLanguageFeedback with canonical source code/name, origin, resolution status, detected language/name, probability, and minimum threshold. Types list_source_languages and exposes bridge.listSourceLanguages().

### frontend/src/lib/use-render-config.ts

Adds sourceLanguage with default auto to the existing shared configuration. The existing localStorage persistence automatically saves manual selection. On loading older/invalid missing-string settings, migration supplies auto. No separate preference store or new state-management package was introduced.

### frontend/src/lib/render-params.ts — new

Centralizes the existing Dashboard parameter construction in buildRenderParams(). Source and target are shared across all input types. Subtitle requests contain language parameters only; audio requests retain speech/background/device parameters; video requests additionally retain visual and quality settings. This helper lets checks exercise the actual parameter builder instead of copying its logic into a test. No pipeline template or media operation was added.

### frontend/src/lib/use-render.ts

Stores runtime source feedback and the current input path alongside the existing render status. Listens for render_started to reset previous job state/feedback, including backend queue advancement and resumed-job starts. Listens for source_language to update feedback. Existing terminal events retain the completed/failed job's report, and stop clears it. Explicit starts also reset feedback immediately. Feedback uses the existing event subscription mechanism and is runtime state, not persisted detection history.

### frontend/src/components/shared/SourceLanguageReport.tsx — new

Renders detected language/confidence, effective manual/Auto translation source, unresolved guidance, and the accuracy note. Uses role=status and aria-live=polite. This small component allows meaningful rendered-text checks with the project's existing React renderer, without adding a browser-test framework.

### frontend/src/pages/Dashboard.tsx

Loads the source catalog, shows the source selector/help/error, labels the target selector, and calls the shared parameter builder. Source/target controls have accessible labels. Displays the input filename and SourceLanguageReport in the existing progress card. Existing render confirmation, browsing, queue selection, templates, stage settings, and media actions remain in place.

### core/pipeline.py

Adds _report_source_language() and calls it after source resolution in audio, video, and subtitle paths. The optional callback carries a JSON-compatible feedback payload. It reports original transcription detection separately from a manual translation-source override. Subtitle jobs supply no fabricated detection metadata. Callback delivery failures are logged and do not abort translation. CLI/direct pipeline use works without registering a callback.

### bridge/api.py

Emits render_started before each job's pipeline construction, allowing the UI to clear the preceding job's feedback. Registers a source-language callback on that pipeline and forwards payloads through the existing push channel. Suppresses feedback after stop. No new transport or server is part of the product.

### dev/test_source_language.py and dev/test_render_queue.py

Add six backend regressions: original detection versus manual source, unresolved low confidence, feedback failure isolation, subtitle metadata absence, per-job start events in a two-job queue, and bridge forwarding suppressed after stop.

### frontend/dev/verify-source-language.mjs — new

Uses Node assertions plus existing TypeScript, React, and React DOM server rendering. It compiles temporary native-ESM test modules inside node_modules/.source-language-ssr, with source aliases resolved for Node. This is test-fixture output, not a new runtime, package, or production build route. Uses isolated fake localStorage/window objects; it does not alter the user's actual preferences or call the real backend. Temporary compiled fixtures are removed with node_modules.

The 26 checks cover accepted Auto wording, downward percentage display, unresolved guidance, manual versus detected languages, unavailable metadata, accessible status markup, escaping provider labels, legacy migration, saving/restoring manual choices, actual parameter construction and JSON serialization for video/audio/subtitle in Auto/manual modes, keeping speech/video fields out of unrelated templates, separate Dashboard controls, and expert parameter preview.

## Build and verification

- Existing npm lockfile restored 189 packages. package.json and package-lock.json have no diff; no version update was requested or performed.
- Final TypeScript check and Vite production build succeeded. Vite version reported 8.1.5, as resolved by the existing lockfile.
- Focused oxlint checks passed for the changed frontend production files.
- All 26 Node/rendered-UI checks passed.
- Aggregate backend suite passed all 227 tests in 17.329 seconds, exit code 0.
- Changed Python files passed AST syntax checks. Targeted git diff --check passed with only LF/CRLF conversion notices.
- The build retains the existing single-large-chunk warning. It is not a build failure; code splitting is outside this source-selection stage.

Reproduction commands, from frontend after an approved dependency restoration:

```powershell
npm.cmd ci --cache .source-language-npm-cache --no-audit --no-fund
npm.cmd run build --cache .source-language-npm-cache
.\node_modules\.bin\oxlint.cmd src/pages/Dashboard.tsx src/lib/api.ts src/lib/use-render.ts src/lib/use-render-config.ts src/lib/render-params.ts src/components/shared/SourceLanguageReport.tsx
node dev/verify-source-language.mjs
```

The backend aggregate uses the existing bundled Python with -B and workspace-local TEMP/TMP, as in preceding reports.

### Verification limitations and recovery during this stage

Live browser automation was unavailable: the session inventory had no browser surfaces, and creating an in-app browser returned unavailable. A localhost-only preview with a fake bridge was prepared, but no browser interaction was performed. Its server was stopped and its temporary files removed during clearance. No additional browser/testing tool was installed.

Rendered React markup and parameter/configuration checks do not prove dropdown click behavior, keyboard interaction, visual layout, pywebview event delivery in a running desktop window, or behavior after Dashboard navigation/remount. Those interactions remain unverified. Detection feedback is held by the mounted render hook and is not a persisted job-history view.

The sandbox initially could not resolve npm's registry. The same approved lockfile restore succeeded with network-enabled execution, keeping its cache local to the workspace. One build invocation used the repository root instead of frontend and failed before building; the corrected frontend invocation passed. An initial Vite SSR test harness encountered CommonJS module-runner incompatibility. The successful harness uses the existing TypeScript compiler and Node's native module loading instead; production code/build behavior was not changed to accommodate that harness. Temporary fixture command/path mistakes were corrected before final checks.

No actual STT/translation/TTS weights, cloud endpoint, full AI render, GPU, fresh installation, Linux, or macOS was tested. Existing backend media tests use bundled FFmpeg/FFprobe on synthetic fixtures. Source correctness policy and licensing/business scope are otherwise unchanged.

## Asset and temporary-file accounting

The original built frontend was backed up temporarily before rebuilding. A before/after SHA-256 inventory is saved in docs/cleanup/2026-10-03-source-ui/BUILD_ASSETS.json. The final dist contains 5 files totaling 1,017,087 bytes; the preceding dist totaled 1,005,244 bytes. Net built-asset increase: 11,843 bytes. The new index references index-C6t47Jvr.js and index-U3Hyr_Hw.css. The build includes the current working frontend source; no unrelated source was reset.

| Temporary path | Files | Bytes before clearance |
| --- | ---: | ---: |
| frontend/node_modules, including generated build/test caches | 11,960 | 162,465,041 |
| frontend/.source-language-npm-cache | 383 | 40,502,135 |
| temp/source-language-dist-before | 5 | 1,005,244 |
| temp/source-language-ui-qa | 3 | 5,580 |
| Total | 12,351 | 203,978,000 |

The dependency directory and npm cache alone account for 202,967,176 temporary bytes. Clearance targets are explicitly resolved and checked within the workspace, then removed using native PowerShell LiteralPath operations. Final clearance status is recorded in docs/cleanup/2026-10-03-source-ui/TEMPORARY_CLEARANCE.json. Global npm caches, the Python runtime, AI model locations, sample media, rendered outputs, and .git are outside these clearance targets.

The final compiled dist, source edits, reusable verification script, reports, and small asset/clearance ledgers are retained. Rebuilding again requires restoring the existing development dependencies; launching the built app does not require node_modules.

## Review and rollback

Review the frontend source changes, the feedback bridge, and the asset inventory together. This report supersedes the prior backend report's statement that manual selection is only available through backend calls. The current UI build now contains the selector; live interaction verification remains limited as stated above.

Do not reset the whole working tree: earlier repairs and user changes are present. To undo this stage, reverse these specific source changes and regenerate dist from the desired preceding frontend source with the existing lockfile. The temporary pre-build copy is removed after successful checks and is not a permanent rollback artifact. No snapshot commit was created.
