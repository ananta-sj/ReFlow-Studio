# Windows portable release iteration — 12 October 2026

Status: **in progress; not approved for release**. The user selected Windows portable as the first release target. Linux and macOS remain experimental. This report consolidates the remaining gates rather than treating historical test counts as an all-feature certification.

## Scope and constraints

The user requested validation of every remaining feature and pipeline, repairs, and detailed documentation. Existing models and runtimes can be exercised locally. New tools, frameworks, models or support packages require the user's approval where not already authorized. No paid API calls are authorized. The temporary Ollama/Qwen trial must be removed after verification. Original settings, registry, graph, hardware profile, UI preferences and accepted media are protected.

## Work completed in this pass

1. Replaced stale portable instructions in `README.txt`. Removed automatic Ollama/Llama selection, bundled-offline translation, fixed speed guarantees, self-healing Linux/macOS and nonexistent packaged diagnostic-script claims. Documented current engine selection, explicit optional setup, review, recovery, fixed node order and alternating cast limitations.
2. Added `core/application_lock.py` and applied it at the desktop entry point in `main.py`. A nonblocking OS file lock admits one desktop owner per portable folder before bridge construction. Normal closure and process death release ownership. The persistent marker is not deleted, avoiding an inode replacement race. Different portable folders remain independent. The guard does not implement process ownership for arbitrary external scripts importing the bridge.
3. Added three real subprocess tests covering duplicate launch exclusion, normal release, abrupt killed-process release and separate-folder ownership. All pass. These are OS lock tests, not native UI crash/recovery tests with running models.
4. Ran the full backend suite: **766 tests, 45 modules, zero failures/errors**. Its receipt binds current source hashes and confirms the five protected app-state files are unchanged. The test runner now supports a separate Windows release label so earlier receipts are preserved.
5. Audited existing frontend production dependencies through npm's advisory service: **zero reported vulnerabilities** in that production dependency audit. This does not certify Python dependencies, operating-system components, all development dependencies or undisclosed vulnerabilities.
6. Rechecked six existing optional/core engine dependency routes without model loading: NudeNet, MuseTalk, RVC, GFPGAN and Wav2Lip pass import/device probes. F5 initially timed out after 90 seconds during `f5_tts.api` import. A justified recheck after the large portable copy completed **passed**, identifying Torch 2.9.1+cpu in its isolated runtime. Both observations are retained. No packages were installed. Disk contention is a possible explanation for the first timeout, not a demonstrated root cause. These checks do not establish loaded-model output quality.
7. Built a fresh model-free portable assembly at `dist/windows-release-candidate-2026-10-12`: **2,824,627,188 payload bytes, 42,956 manifest entries**. Nine relocated-runtime/content checks pass, including current application hashes, core imports, no personal model connections, protected-state/cache exclusion and duplicate lock rejection. This is a same-machine test, not a clean-machine Windows certification. Subsequent native onboarding creates disposable QA settings inside this copy; do not publish that used QA directory as a pristine artifact.
8. Full npm audit subsequently found two build-dependency advisories. Updated only **nanoid 3.3.16 → 3.3.20** and **source-map-js 1.2.1 → 1.2.2**, within the existing dependency tree, with install scripts disabled. Root `package.json` is unchanged. The old lock file and audit are retained. Full post-update audit reports zero advisories; frontend build/lint and **47 frontend contracts** across resource, preference, graph, recovery and Dashboard checks pass. Existing lint and bundle-size warnings remain. Built frontend index still matches the already assembled candidate.
9. Native Windows acceptance using the candidate's own embedded Python and five-step onboarding: fresh window opened, AirLLM and model selections remained off, onboarding persisted, optional tour dismissed, video review panel displayed, empty-source render/review actions remained disabled, and selected-setup inspection visibly labelled unverified engines rather than claiming end-to-end readiness. An actual second desktop launch returned exit 1 with the already-open message while the first window stayed open. Alt+F4 closed the window; the running command exited 0. Reopening the same candidate succeeded with onboarding/tour remaining completed. Advanced configuration, the ten-node graph and the empty Marketplace rendered. No render/model/install/download/provider call was requested. A first detached `Start-Process` attempt did not yield a sustained visible window; the direct owned launch succeeded. Immediate capture after close briefly reported `foreground window did not report a process id`; a refreshed inventory showed only Codex, confirming the target was closed. Neither unsuccessful harness observation is hidden as a successful UI test.

Evidence: [backend receipt](validation/2026-10-12-windows-release-backend-complete.json), [lock tests](validation/2026-10-12-application-lock-tests.log), [npm audit](validation/2026-10-12-frontend-runtime-audit.json), [runtime probes](validation/2026-10-12-windows-optional-runtime-probes.json).

Additional evidence: [candidate audit](validation/2026-10-12-windows-portable-candidate-audit.json), [full npm audit before patch](validation/2026-10-12-frontend-full-audit.json), [full npm audit after patch](validation/2026-10-12-frontend-full-audit-after-update.json), [dependency update](validation/2026-10-12-frontend-security-update.log), [native duplicate rejection](validation/2026-10-12-portable-native-duplicate.log). Advisory references: [nanoid](https://github.com/advisories/GHSA-2v37-7h3g-55p8), [source-map-js](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

10. The current core XTTS engine passed a **real offline model load and cancellation** at an observed generation-token boundary in **0.094 seconds**. The preexisting disposable output bytes were preserved, staging files were absent and the owned workspace was removed. Total check took 45.078 seconds. This proves this tested XTTS route works despite the metadata consistency failures; it does not certify all XTTS languages, complete speech quality or a reproducible rebuild. Existing Transformers deprecation warnings are retained. Evidence: [live XTTS receipt](validation/2026-10-12-xtts-live-cancellation.json) and [F5 recheck](validation/2026-10-12-f5-runtime-probe-after-copy.json).

## Temporary dialogue model trial and mandatory cleanup

Used standalone Ollama v0.40.3 in one owned temporary directory, never a global installer. Official ZIP SHA-256 was verified. The approved Qwen tag was `qwen3:4b-instruct-2507-q4_K_M`, full model digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`. Models, home, scratch, CUDA cache and server logs were redirected to that directory; the server used a private loopback port. No app connection or settings were saved. Existing normal Ollama locations were absent before and remain absent.

Three bounded cases used actual previously captured English/Hindi cue evidence and the existing native IndicF5 duration estimator. No speech was synthesized. The writer and reviewer were the same model with different prompts; this is an advisory self-review, not independent semantic verification.

| Case | Result | Release implication |
| --- | --- | --- |
| Complete opening | Request hit the existing 60-second service timeout | Cold-start behavior needs explicit evaluation; failed request is retained, not converted to a pass |
| Complete establishing-shot sentence, 5-second budget | One candidate predicted 4.811 seconds, but reviewer flagged changed meaning; another predicted 5.408 seconds | Fitting duration alone cannot justify using a rewrite |
| Cropped incomplete-context passage, 8-second budget | Three candidates predicted 9.493–10.197 seconds; none fit | Automatic shortening gate remains open; incomplete source context is an additional limitation |

All candidates remained unapproved and subject to human review. No candidate replaced any transcript, take or accepted output. Trial `completed:false` and process exit 1 are preserved because one case failed. That failure does not mean cleanup failed.

The evaluator stopped its owned server and removed **5,965,218,657 bytes** of runtime, archive, weights and temporary material. Independent cleanup audit passed **7/7** checks: directory absent, evaluator confirmation, normal Ollama paths preserved, no global installation, protected state unchanged, human-accepted short video unchanged and no paid calls. Only JSON evidence and a bounded diagnostic log remain.

Evidence: [trial receipt](validation/2026-10-12-ollama-eval-c_lslq8w.json), [cleanup receipt](validation/2026-10-12-ollama-eval-c_lslq8w-cleanup.json). Reinstalling or retaining this trial is not authorized by a request to continue other development.

## New release blockers

### Core environment is not dependency-consistent

An actual `pip check` returned exit **1**. The installed runtime has duplicate distribution metadata, including different Torch, torchaudio, torchvision, tokenizers, protobuf, thinc, blis and other versions. It also has a pip metadata directory missing `METADATA`. Installed TTS reports the original `TTS==0.22.0`; the source requirements describe `coqui-tts`. Consequently, rebuilding from requirements and copying this runtime are not equivalent release processes.

Reported missing requirements include `spacy-legacy`, `spacy-loggers`, `aiohttp`, `encodec`, `g2pkk`, `umap-learn` and `unidecode`. Reported conflicts include NumPy/blis/TTS, SciPy/TTS, hydra/fairseq, OmegaConf/fairseq/RVC and thinc/blis. These diagnostics do not establish that each exercised render is broken: several isolated routes and a real short render passed. They establish that the shared bundle cannot currently be represented as a reproducible, dependency-consistent all-engine runtime.

Do not remove duplicate metadata to manufacture a clean result: overlapping packages can have overwritten files. Do not upgrade NumPy/Torch in the working environment blindly. Concrete repair proposal: create a **separate fresh core candidate**, install a deliberately reviewed core dependency set with required support packages, retain the current working runtime and every optional profile, isolate incompatible engine families, require dependency checks and real engine acceptance, then switch the portable builder only after acceptance. No new AI engine, manager model or framework is proposed. Download sizes and exact pins must be determined before installation. Existing broad `requirements.txt` is not a release lock file.

Evidence: [dependency inventory](validation/2026-10-12-release-dependency-inventory.json), [captured dependency errors](validation/2026-10-12-core-dependency-check-captured.log), [runtime identity](validation/2026-10-12-core-runtime-identity.log).

### Distribution terms are not ready

The root `LICENSE.txt` contains Python's license/history. It is not an explicit license grant for Reflow's own code. The user asked to discuss licensing before choosing; no application license has been assigned.

The [licensing discussion brief](LICENSE_DECISION_BRIEF_2026-10-12.md) compares permissive, reciprocal-source and proprietary directions and identifies the separate distribution preparation. It records no selection or implied permission to relicense third-party work.

The actual FFmpeg binary configuration contains `--enable-gpl --enable-version3` and GPL components. No license/notice/copying files were found under the bundled FFmpeg tree. Its corresponding source/notice/distribution obligations need a concrete preparation step before publication. [FFmpeg's own legal guidance](https://ffmpeg.org/legal.html) explains that enabled GPL components change the applicable FFmpeg licensing; this report does not infer that every separate application must therefore use a particular license.

The vendored Wav2Lip README contains restrictions on commercial use. Those conditions must be evaluated independently of Reflow's own license. Model rights, gated access conditions and voice-reference consent cannot be inferred from the app license. The inventory captures installed-package license text hashes and declared metadata; it is not legal clearance.

### Current CI is not the intended release path

`.github/workflows/build.yml` installs broad source requirements and builds PyInstaller executables on three OS runners. It does not produce or validate the portable candidate assembled from the current bundled runtime and has no comprehensive release quality gate. Treat it as an experimental executable-build workflow until it is aligned with a verified portable runtime recipe. No GitHub workflow was dispatched and no release was published.

### The validated Hindi setup is not yet turnkey for a new user

The model-free candidate's Hindi voice panel correctly reports that no confirmed reference exists and the IndicF5 assets are absent. However, the panel only connects an existing manually prepared profile; it does not enroll a new user's reference or set up the gated Hindi engine. IndicTrans2 and stronger Whisper likewise have installed-model connection controls and evaluation-named runtime locations. The portable builder's optional profile choices currently cover vision, F5 and MuseTalk, not these Hindi evaluation profiles.

A new user therefore cannot reproduce the human-accepted Hindi workflow from the core ZIP with the current in-app setup alone. An explicit setup path, gated-access instructions, reproducible runtime/model installation, user-owned reference enrollment and relocation acceptance are release work, not solved by copying the current user's reviewed voices into a download. No personal voice/reference or account credential was bundled.

## Consolidated acceptance matrix

| Area | Available evidence | Remaining acceptance or repair |
| --- | --- | --- |
| Preprocessing/background | Real fixed-seed Demucs CPU repeatability and short-video stems; FFmpeg media tests | Music-rich/noisy inputs, varying media formats and long inputs; background level/leakage review |
| Speech recognition | Real Whisper Turbo GPU cues; language, metadata, completeness contracts | Multiple speakers, silence/noise, other source languages and long continuous material |
| Translation | IndicTrans2/NLLB real comparisons and completeness tests | Consistent meaning and natural wording across complete dense passages; other target-language acceptance |
| Speech/timing | Human-accepted 6.9-second Hindi output; native duration guards, other historical voice reviews | Long natural delivery, both voice profiles across varied text, expressive phrasing, dense dialogue fit without dropping meaning |
| Dialogue reviewer | Local service wiring and bounded live requests exercised; unsafe/overlong candidates remain unapproved | Successful quality cases and service startup/timeout UX; temporary service already removed |
| Standard audio/video/subtitle workflows | Backend contracts and actual short video with audio/subtitles/stems | Current full long video, audio-only and subtitle exports, visible review route, media variants and output metadata |
| Optional visuals/voices | Five dependency probes pass; historical single-engine smoke evidence exists | Current moving-face lip-sync/enhancement/filter chains; genuine authorized RVC voice checkpoint; full selected-provider executions |
| Nodes/cast | Fixed-order editing, persistence and native historical controls tested | No arbitrary graph execution or diarization is implemented; both limitations now explicit in portable instructions |
| Parallel/resource controls | Bounded workers/shared inference serialization and routing contracts tested | Measured end-to-end throughput, worker-inclusive RAM/VRAM, empirical estimates; do not advertise proportional speedup |
| Queue/recovery | Durable queue, synthetic process crash/restart and native restored controls; actual speech cancellation/checkpoint reuse | Native model-running abrupt crash/relaunch, output safety during shutdown, longer batch acceptance |
| Multiple instances | New OS exclusion/release subprocess tests pass | Current native duplicate launch feedback and lock holding across tray lifetime |
| UI | Prior native controls/layout evidence, current review component contracts | Current fresh portable onboarding, video review route, minimum size/DPI, visible error/recovery paths |
| Downloads/setup/offline | Transactional/cancellation/hash/offline contracts; real temporary official download | Fresh model-free selected-engine setup, interrupted/resumed gated download and useful user guidance with credentials absent |
| Distribution | Fresh assembly started; personal-state/weight exclusion by builder | Candidate manifest/content/runtime verification, runtime repair, clean Windows/WebView prerequisites, relocation, final notices/checksum |
| Security/permissions | Download/deletion/path/credential contracts; npm production audit clean | Python/runtime vulnerability assessment and exact redistribution inventory; no claim of exhaustive security certification |
| Linux/macOS | Source launchers/experimental CI | Explicitly outside first release certification; no native acceptance on this machine |

## Completion rule

Release approval requires an accepted Windows artifact, current source-bound regressions, installed-runtime consistency, representative full workflow and native recovery acceptance, model/setup behavior, and settled publication terms. Optional or experimental routes must be labelled with their actual validation status. A successful small clip or larger test count cannot substitute for these gates. The iteration continues while these independent checks and repairs are possible; required new package/model approvals and owner licensing decisions must be recorded explicitly rather than assumed.

## Current checkpoint

Final evidence integrity passed **15/15** checks, including all 47 frontend contracts, unchanged tested backend sources, only the two expected frontend package version changes, exact current built frontend files in the candidate, the five protected app-state files, both accepted videos, real XTTS cancellation, F5 recheck and temporary Ollama cleanup. [Integrity receipt](validation/2026-10-12-windows-release-integrity.json). Its `release_ready` field explicitly remains `false`.

[Native observations](validation/2026-10-12-windows-portable-native-observations.json) record the limited same-machine walkthrough, two normal exit codes and generated QA state. No native test window or temporary Ollama server is left running. The original runtime remains intact. The pending approval concerns building a separate clean runtime and adding required support packages; the user's earlier requirement to approve new additions is the reason installation has not proceeded. No automatic approval review rejected an action. Licensing remains a discussion, as requested, with no selection made.
