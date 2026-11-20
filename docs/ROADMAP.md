# ReFlow Studio delivery plan

Updated 2026-11-20. This is the current public, sanitized work plan. Historical reports preserve earlier evidence; they do not override the current checkout or establish current acceptance.

## Purpose and delivery order

ReFlow began with family-friendly editing: remove or replace unwanted words while retaining the original performance elsewhere. Its broader goal is natural multilingual dubbing with consistent characters, meaningful adaptation, preserved scene audio and optional lip sync. See PROJECT_DIRECTION.md for the distinction between censor-only, clean replacement and translation/dubbing.

Owner-approved order: decide existing PRs -> community documentation and planning -> one reviewed source push -> native interactive testing in a new chat -> reproduced fixes and another validation/push -> pipeline qualification. Preserve existing features before expanding the product. A full episode or movie remains an acceptance goal, not a promised capability.

## Work board

Use Backlog, Ready, In progress, Blocked and Done as board columns. Optional GitHub Projects can mirror this table later. No external board, issues, labels or agent task has been created automatically; never publish private diagnostics or exploit details just to populate a board.

| ID | Deliverable / status | Depends on | Completion evidence |
| --- | --- | --- | --- |
| PREP-01 | PR decisions recorded; local #20 change included | none | PR_REVIEW_2026-11-20.md covers all 13 heads. Owner still needs push/checks and remote closures. |
| PREP-02 | Community files prepared | none | Contributing, conduct, accessibility, issue forms and PR template included in source export; links/schema checked. GitHub checklist recognition awaits push. |
| PREP-03 | Consolidated source checkpoint / ready after local checks | PREP-01,02 | Owner reviews staged files, commits/pushes main; CodeQL, PR checks and four native builds pass. No models, credentials, media or environments staged. |
| NATIVE-01 | Native preflight / ready next chat | PREP-03 | Record actual checkout/commit/runtime/controller, preserve app/job state, confirm desktop startup prerequisites. Do not install or clear data by assumption. |
| NATIVE-02 | Complete existing UI interaction matrix / pending | NATIVE-01 | Startup, navigation, logs, settings, nodes, marketplace and dialogue review checked in both themes; taskbar/tray/window icons, keyboard focus, dialogs, scaling, resize and safe close all have observations. |
| NATIVE-03 | Recovery and ownership under real interaction / pending | NATIVE-01 | Controlled short synthetic job: cancel, retry, restart/resume and queue ordering; no duplicate work, lost accepted take, deleted imported asset or false success. |
| FIX-01 | Fix reproduced UI/lifecycle defects / pending | relevant native finding | Minimal failing regression, scoped fix, repeat exact interaction; preserve old outputs/state; update evidence and push after review. |
| ENGINE-01 | Clean setup and device qualification / pending | NATIVE baseline or independent safe preparation | Fresh public F5/MuseTalk recipe installation, actual decoder/engine smoke checks, measured device use and supported CPU/GPU behaviour. Existing private trials are not automatically production-qualified. New downloads/services need permission. |
| DUB-01 | Freeze one continuous multi-character benchmark / pending | usable qualified engines + permitted media | Source cues, character/reference examples and expected meaning defined; include fast/slow lines, a speaker change, silence/background and a cut. Keep private media/evidence out of Git. |
| DUB-02 | Qualify automatic first pass and review / pending | DUB-01 | Every dialogue cue is accounted for; report wrong/unresolved character matches, meaning/gender/negation, pronunciation, pacing, clipped speech, emotion and background artefacts. Bounded retries save valid takes and expose unresolved decisions. Human listening required. |
| CENSOR-01 | Qualify the original censor-only objective / pending | usable transcription/alignment/media path | Only intended word intervals beep/mute; untouched dialogue remains original; music/effects and export sync checked. Clean synthesized replacement is a separate acceptance case. |
| LIP-01 | Qualify optional lip sync separately / backlog | continuous audio dub accepted | Check on/off-screen speech, multiple faces, cuts and anime. Correct voice timing is not proof of visual lip sync. Unsupported cases remain explicit. |
| EP-01 | Qualify one complete episode / backlog | DUB-02 and relevant fixes | All intended dialogue accounted for, unresolved lines not silently passed, character consistency maintained, export checked end-to-end. Record per-stage time, retries, memory and recovery evidence. |
| BATCH-01 | Qualify multiple episodes and long media / backlog | EP-01 | Restart/interruption and CPU/GPU pressure tested with reusable stages; no repeated silent failure or partial output reported complete. Movie acceptance is a later distinct test. |
| DEP-01 | Smaller frontend maintenance / deferred | native baseline | Recreate #29 first, then #30/#28 one at a time on current main; current CI/build/audit plus chart/icon/dialog/focus observations pass. |
| DEP-02 | Compiler/types and animation migrations / deferred | native baseline | Split old #27; review TypeScript/Node/Anime type compatibility separately from minor tooling. Treat old #31 Motion as its own migration. |
| DEP-03 | GitHub Actions major migrations / deferred | stable release baseline | Recreate old #15-19 as a coordinated, reviewed workflow change; all platform builds, artifact transfers and preview publication checks pass. |
| RELEASE-01 | Release qualification / backlog | relevant native/engine/scene/episode gates | Third-party model/runtime terms, platform limitations, package contents, instructions, checksums and release claims reviewed. Desktop Preview remains labelled until the intended workflow passes. |

## Native test record

For each interaction record: ID, commit/package, OS/architecture/DPI, runtime, action/fixture, expected result, observed result, pass/fail/blocked, evidence and follow-up. Measure cold and warm startup separately from model loading. Do not set arbitrary performance or accessibility compliance claims without measurements.

Marketplace checks must distinguish downloaded, verified, compatible, installed, tested and selected. Show actual storage/progress when known; preview ownership before deletion. Use disposable owned fixtures for deletion/reset/interruption scenarios and protect active/shared/imported files.

## Pipeline acceptance record

Record meaning, character identity, reference suitability, pronunciation, naturalness/emotion, duration/window, clipping/speed changes, background residue and export sync separately. Do not average away a wrong speaker or missing dialogue. Maintain a mapping from source cue to translated wording, generated take, decision and final output.

Start with existing assets and engines. Model shopping is not the default repair path. Any proposed alternative needs a specific failed criterion, licence review, download/disk/RAM/VRAM bounds and owner authorization. Local-first operation and optional API use do not authorize uploads or spending.

Language and output-mode expansion, unrestricted customization, new marketplace features and billing/agent integrations stay behind the existing-app and scene gates. Supported-language lists must distinguish transcription, translation, speech and accent support; one engine's language list is not end-to-end coverage.

## Next session

Read NEXT_CHAT_HANDOFF.md. Start at NATIVE-01, not at a full-episode dub. Existing source/synthetic test successes and the closed security-alert checkpoint do not prove native usability or studio-quality dubbing.


## Preparation validation — 2026-11-20

This batch passed 36 packaging tests, 21 cloud-boundary regressions and 31 simulated UI tests. Publisher/version checks passed 32 cases with one POSIX-only FIFO check skipped on Windows. Frontend lint exited without errors, retaining existing warnings; the production build passed with existing chunk-size, dynamic-import and future-config-loader warnings. These were not suppressed. Review chart hook behaviour and startup/rendering observations during native testing before making performance claims.

The two issue forms and issue configuration parsed successfully, their required fields/IDs were checked, and 29 relative links in the contributor/handoff documents resolved. Source-export tests cover the new community/planning files. The existing isolated packaging 26.3 install passed a requirements/version parser smoke check; the desktop environment itself was not upgraded. Independent source review found no blocking issue in this batch. Native interaction, a clean public engine install and trained dubbing remain untested here.
