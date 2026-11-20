# Next chat: native testing and scoped repairs

Prepared 2026-11-20. Read AGENTS.md, ROADMAP.md and this file before acting. This is a handoff, not authorization to install tools/models, send media to services, spend money, delete state or publish remote changes.

## What ReFlow is for

ReFlow coordinates extraction, source separation, transcription, dialogue adaptation/translation, character/reference selection, speech generation, timing/review and media export. Its original purpose is family-friendly editing while preserving untouched performance. Natural multi-character dubbing is the broader goal. Censor-only editing, clean replacement, translation, subtitles and visual lip sync need separate acceptance evidence.

The owner wants the existing app perfected before broad expansion. Work sequence is the ROADMAP.md order: prepare one source push, inspect the native app in a new chat, reproduce/fix defects, then qualify the pipeline from a continuous scene to an episode. Do not start overnight batches as a substitute for scene acceptance.

## Current source and security checkpoint

- Locate the actual Git checkout; do not assume the environment's old cwd or a path in an October report still exists. The active work has been in the GitHub/ReFlow-Studio checkout on main. Review git status before editing.
- Previous source checkpoint: ef6e478, Security fix and resolution. Its main CodeQL and native-build runs succeeded; the owner reported all vulnerability/code-scanning alerts closed after that push. Recheck current hosted status rather than promising that future scans will remain empty.
- This preparation batch adds community guidance/forms, current roadmap/handoff, AGENTS.md, corrected checkout documentation, source-export inclusion, and the desktop packaging 26.3 requirement from PR #20. PR_REVIEW_2026-11-20.md records recommendations for all 13 PRs. Recommendations do not mean GitHub PRs were closed or merged. Read the actual latest commit after the owner pushes this batch.
- The security work isolated F5/MuseTalk, removed base-runtime fallback, updated coordinated CPU dependencies, fixed Wav2Lip audio compatibility and publisher check/read races, and removed an unused IndicF5 source copy. Read SECURITY_REMEDIATION_2026-11-20.md for exact evidence and limits. Do not reintroduce the removed training/server code.

## Environment and permission boundaries

The old roughly 70-GB app directory was deleted by the owner. GitHub source is not a backup of ignored models, checkpoints, voices, runtimes, settings, outputs or media. Inspect current files before reporting what is installed or recoverable.

At the preceding checkpoint, the desktop .venv existed and separate runtime_profiles/chatterbox-trial, community1-trial and security-validation directories existed. Verify now; do not assume their contents are intact. Existing trial packages are not a universal safe engine/runtime. No fresh end-to-end public F5 installation, trained inference or GPU qualification was established in the latest security work.

Prior model trials and downloads were individually authorized with limits. The security-validation trial was capped at 1 GB downloaded/4 GB disk; its last receipt charged about 667 MB and measured about 2.78 GB disk. Those are historical measurements, not an unused quota or permission for additional unrelated downloads. The working runtimes were preserved. New software/models, OS security changes, paid APIs and remote media uploads need explicit authorization.

Computer Use succeeded for the owner in another new chat. This old chat still had no node_repl/controller exposed. Discover the tools in the new chat, read the installed Computer Use skill, and initialize through its supported entry point if available. Do not launch helpers or invent a protocol as a workaround. A browser tab alone grants no control or authentication.

## First native session

1. Verify checkout, latest commit, clean/dirty source state, actual desktop interpreter, available controller and running app/job processes. Read saved job/queue state before opening or closing anything.
2. Preserve settings, accepted takes, queue and recovery data. Use a disposable app-state fixture or an explicitly reviewed snapshot for destructive scenarios; do not factory-reset the owner's app.
3. Launch through the documented existing entry point. Record cold/warm time to usable controls, startup recovery and icon behaviour. Do not confuse model cold start with GUI startup.
4. Work through NATIVE-02/03: keyboard/focus, themes/DPI/resize, navigation/log persistence, dashboard selections, nodes, marketplace, review playback, safe close and retry/resume. Record pass/fail/blocked rather than inferring success from source tests.
5. On a failure, preserve diagnostics safely, reproduce a minimal case, add a regression at the owning layer, patch narrowly, rerun the relevant check, and repeat the exact native action. Do not weaken tests or add a new model to hide an unrelated UI defect.
6. Update ROADMAP.md and a sanitized test record. Review a source-only diff before the owner commits/pushes fixes. Keep private media, full logs and personal machine details in ignored local evidence.

## Then qualify the pipeline

Use one permitted short continuous multi-character scene first. The owner previously preferred a gentler Perrine candidate, a calmer innkeeper retake, and a natural mother sample, but individual auditions do not prove automatic matching or episode consistency. Confirm the actual saved recipes and available media rather than reconstructing them from memory.

Prior source-level matching checks had substantial unresolved cues; natural, meaning-preserving timing adaptation and consistent episode-level delivery remain open. Existing review can retain valid takes and expose unresolved lines; it does not guarantee automatic translation meaning or acting. Do not silently skip cues, insert source-language speech into an output labelled fully dubbed, aggressively time-stretch speech to mask bad wording, or claim an RTX is active without measurement.

Measure recognition/translation/reference prep/model loading/generation/retries/export separately. Verify source meaning, named characters, negation/gender, pronunciation, speech boundaries, natural delivery and background preservation. Inspect songs, overlapping speakers and off-screen dialogue explicitly. Test censor-only editing independently. Full-episode, batch/movie and optional visual lip-sync gates come later.

## Checks and references

Follow CONTRIBUTING.md for packaging, cloud boundary, publisher and frontend checks. Different backend suites require different environments; record missing optional dependencies as limits. Source tests, synthetic process/media tests, native interaction, real model inference and human listening are different evidence levels.

Authoritative current pointers: ROADMAP.md (task status), PROJECT_DIRECTION.md (purpose/limits), REVIEW_WORKFLOW_2026-11-15.md (saved takes and recovery), OPTIONAL_RUNTIME_SECURITY.md (engine setup), PR_REVIEW_2026-11-20.md (dependency decisions), and the security remediation report. Older reports are history, not instructions to recreate deleted environments.
