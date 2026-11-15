# Reflow Studio — Development History & Feature Documentation

This document records every feature built during the PyQt6 → web migration and the
model-marketplace initiative that followed it: what each feature is, why it was
built, how it works, how it was implemented, and every bug that was hit along the
way and how it was fixed. It's written to be readable standalone — you shouldn't
need the original chat history to understand any decision recorded here.

---

## Table of Contents

1. [Platform Migration: PyQt6 → Web App](#1-platform-migration-pyqt6--web-app)
2. [Security Model](#2-security-model)
3. [Bridge Architecture](#3-bridge-architecture)
4. [Window Chrome & Boot Experience](#4-window-chrome--boot-experience)
5. [Theming & Experience Levels](#5-theming--experience-levels)
6. [Visual Design System](#6-visual-design-system)
7. [Layout Fixes](#7-layout-fixes)
8. [Settings System](#8-settings-system)
9. [Model Marketplace — Foundation](#9-model-marketplace--foundation)
10. [Model Marketplace — Provider Abstraction](#10-model-marketplace--provider-abstraction)
11. [Model Marketplace — Cloud REST Providers](#11-model-marketplace--cloud-rest-providers)
12. [Model Marketplace — AirLLM Provider](#12-model-marketplace--airllm-provider)
13. [Model Marketplace — Frontend](#13-model-marketplace--frontend)
14. [Model Marketplace — Registry-Driven Resolution](#14-model-marketplace--registry-driven-resolution)
15. [Pipeline Permutation Templates](#15-pipeline-permutation-templates)
16. [Node Graph Editor Fixes](#16-node-graph-editor-fixes)
17. [Multi-Cast Voice Nodes](#17-multi-cast-voice-nodes)
18. [Auto-Detect Model Type](#18-auto-detect-model-type)
19. [Auto-Pick Best Model](#19-auto-pick-best-model)
20. [Full QA Audit & Feature Verification Pass](#20-full-qa-audit--feature-verification-pass)
21. [Per-Device Render-Time ETA & Radial Gauge](#21-per-device-render-time-eta--radial-gauge)
22. [Marketplace Full Reset — Retiring Auto-Seeded Models](#22-marketplace-full-reset--retiring-auto-seeded-models)
23. [Dashboard/Nodes Render-Config Unification & Persistence](#23-dashboardnodes-render-config-unification--persistence)
24. [Opt-In AirLLM Translation Provider](#24-opt-in-airllm-translation-provider)
25. [Projected System Load Gauge & NVIDIA VRAM Fix](#25-projected-system-load-gauge--nvidia-vram-fix)
26. [Generalized Per-Model ETA/VRAM Estimation](#26-generalized-per-model-etavram-estimation)
27. [Lipsync (7th) & Profanity Filter (8th) Stage Types](#27-lipsync-7th--profanity-filter-8th-stage-types)
28. [Curated Recommended Models](#28-curated-recommended-models)
29. [First-Run Setup Wizard](#29-first-run-setup-wizard)
30. [Per-Model Custom Instructions & Profanity-Filter Pipeline Wiring](#30-per-model-custom-instructions--profanity-filter-pipeline-wiring)
31. [Hardware-Aware Recommendations ("Best For This Device")](#31-hardware-aware-recommendations-best-for-this-device)
32. [Help Tooltips, Confirmation Dialogs, AirLLM Wizard Step & 24-Language Translation](#32-help-tooltips-confirmation-dialogs-airllm-wizard-step--24-language-translation)
33. [Marketplace Card Polish & Load-Based Safety Gauges](#33-marketplace-card-polish--load-based-safety-gauges)
34. [Freeze-Prevention Pass](#34-freeze-prevention-pass)
35. [Project-Local Python Environment & Minimize to System Tray](#35-project-local-python-environment--minimize-to-system-tray)
36. [Resume-Render-After-Crash](#36-resume-render-after-crash)
37. [Dead Wav2Lip File Removal & a Real .gitignore Bug](#37-dead-wav2lip-file-removal--a-real-gitignore-bug)
38. [HSV Accent Color Picker](#38-hsv-accent-color-picker)
39. [Opt-In Parallel Dubbing & Nodes Graph ETA/Load Panel](#39-opt-in-parallel-dubbing--nodes-graph-etaload-panel)
40. [First-Run Product Tour & Demo-Mode Replay](#40-first-run-product-tour--demo-mode-replay)
41. [Native Windows/Linux/macOS Executables](#41-native-windowslinuxmacos-executables)
42. [Security & Robustness Hardening Pass](#42-security--robustness-hardening-pass)
43. [Complete Bug/Issue Log](#43-complete-bugissue-log)
44. [Disk Space Breakdown](#44-disk-space-breakdown)
45. [Packaged exe Icon & a Real Windows Installer](#45-packaged-exe-icon--a-real-windows-installer)
46. [Real Local-File Inference: STT, Translation, TTS, Profanity Filter](#46-real-local-file-inference-stt-translation-tts-profanity-filter)
47. [CPU-Feasible Visual Filter (Falconsai) & a Marketplace Plumbing Gap](#47-cpu-feasible-visual-filter-falconsai--a-marketplace-plumbing-gap)
48. [F5-TTS: Real Zero-Shot Voice Cloning](#48-f5-tts-real-zero-shot-voice-cloning)
49. [MuseTalk: Vendoring a Second Lip-Sync Engine](#49-musetalk-vendoring-a-second-lip-sync-engine)
50. [Windows Console UTF-8 Crash & an OpenCV 5.0 Regression](#50-windows-console-utf-8-crash--an-opencv-50-regression)
51. [Settings Page Black Screen (a Real Rules-of-Hooks Bug)](#51-settings-page-black-screen-a-real-rules-of-hooks-bug)
52. [Dub Audio Overlap & Background Bleed-Through](#52-dub-audio-overlap--background-bleed-through)
53. [Practical Hardware-Aware Defaults, Not Just "It Technically Works"](#53-practical-hardware-aware-defaults-not-just-it-technically-works)
54. [Recommended Models List Expanded ~2.5x](#54-recommended-models-list-expanded-25x)
55. [TTS Silently Producing Zero Audio — the Torchcodec/FFmpeg DLL Bug](#55-tts-silently-producing-zero-audio--the-torchcodecffmpeg-dll-bug)

---

## 1. Platform Migration: PyQt6 → Web App

**What it is.** Reflow Studio's entire UI was rewritten from a PyQt6 desktop app to
a React 19 + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui frontend, hosted inside
a native window via `pywebview` (WinForms backend on Windows). The Python backend
(`core/`) was kept — pipeline logic, model handlers, etc. — and a new `bridge/`
layer replaced PyQt's signal/slot system.

**Why.** After seeing reference SaaS-dashboard mockups, the user wanted "the best
possible look and feel," explicitly ruling out staying on PyQt6's widget-based UI.
The requirement was a **web application that runs on the system itself**, not a
browser tab, with no compromise on visual polish.

**How it works.** `main.py` creates a `pywebview` window pointing at
`frontend/dist/index.html` (the Vite production build), with a `PythonBridge`
instance registered as the window's `js_api`. The React app talks to Python only
through `window.pywebview.api.*`; Python pushes events back into the page via
`window.evaluate_js()`.

**How it was implemented.**
- `frontend/` is a self-contained Vite project (`npm run build` → `frontend/dist/`).
- `main.py` locates the built `index.html`, resolves a `file://` URI for it, and
  calls `webview.create_window(...)`.
- The old `ui/` (PyQt6 widgets, workers, `pipeline_worker.py`) was deleted once the
  web app reached parity — `bridge/api.py` deliberately has zero import dependency
  on that tree.

**Issues faced:**
- **shadcn CLI files landing in a literal `@` folder.** The `shadcn` component
  installer misinterpreted the `@/` path alias in this project's `tsconfig.json`
  and wrote files into a directory literally named `@`. Fixed by moving the files
  to their correct locations manually.
- **Deprecated `tsconfig` `baseUrl`.** TypeScript flagged `baseUrl` as deprecated
  once combined with `paths`. Removed `baseUrl`, kept only `paths`.
- **Third-party component libraries assumed Next.js.** Components pulled from
  kokonutui/bklit-ui used `next/link`, `next/image`, and `NodeJS.Timeout` — none of
  which exist in a plain Vite app. Patched to `<a>`/`<img>` and
  `ReturnType<typeof setTimeout>`.

---

## 2. Security Model

**What it is.** A hard guarantee that Reflow Studio never opens a network port or
listens on any socket — the *only* way the page can reach Python is through the
`js_api` bridge object.

**Why.** Desktop apps that embed a web view often do so by spinning up a local HTTP
server (`http://127.0.0.1:PORT`) and pointing the webview at it. That's an open
attack surface for zero benefit in a single-user desktop tool. The user explicitly
required "no open ports/attack surface" as a hard constraint for the migration.

**How it works.** `pywebview` has an internal heuristic: if the URL passed to
`create_window()` doesn't already start with `file://`, it assumes you want a
server and spins up a `bottle` instance bound to `127.0.0.1` on a random port,
*even though nothing actually needs it for a local file*.

**How it was implemented.** `main.py` builds the window URL with
`Path(DIST_INDEX).as_uri()` (producing a real `file://...` URI), never a bare
filesystem path string. This one detail is what keeps `pywebview` from opening the
loopback server at all.

**Issue faced:** Early versions of `main.py` passed the dist path as a plain
string. `netstat`/`Get-NetTCPConnection` showed a live listening port on startup.
Root-caused by reading pywebview's own `platforms/winforms.py` / `util.py`
(`is_local_url()`) to find the `file://` requirement, fixed with the `as_uri()`
change, and **re-verified with `Get-NetTCPConnection`** showing zero listening
ports after the fix — confirmed by the user directly, not just asserted.

---

## 3. Bridge Architecture

**What it is.** Two small, focused pieces that together replace everything PyQt's
signals/slots and `QThread` workers used to do:
- `bridge/api.py` — `PythonBridge`, the entire JS-callable surface.
- `bridge/push.py` — a one-way Python → JS event channel.

**Why.** React needs a way to *call into* Python (start a render, list models,
browse a file) and Python needs a way to *push updates into* React (progress
percentages, log lines, download speed) from a background thread, without any
network layer in between.

**How it works.**
- **Calling Python from JS:** every method on `PythonBridge` is automatically
  exposed at `window.pywebview.api.<method_name>()`, returning a Promise.
  `frontend/src/lib/api.ts` wraps this in a typed `bridge.*` object so the rest of
  the frontend never touches `window.pywebview` directly.
- **Pushing from Python to JS:** `push.emit(event_name, payload)` calls
  `webview.windows[0].evaluate_js(...)`, executing
  `window.__reflow.dispatch(event_name, payload)` inside the page.
  `frontend/src/lib/events.ts` defines `dispatch()` and a `subscribe(event, fn)`
  helper that React hooks use (`use-render.ts`, `use-marketplace.ts`, etc.).

**How it was implemented.** `evaluate_js()` is documented by pywebview as
thread-safe — it marshals the call onto the GUI thread internally — which is what
lets a background `threading.Thread` (e.g. a render job or a model download) push
live progress into the page without any manual thread synchronization on the
Python side.

---

## 4. Window Chrome & Boot Experience

**What it is.** A frameless window with a custom HTML title bar (drag region,
minimize/maximize/close buttons drawn in React), a boot splash screen, and correct
maximize/restore/exact-sizing behavior.

**Why.** The reference mockups called for a fully custom look with no native OS
title bar. The user also wanted a boot animation and explicitly said the window
should "work like a normal software" — full-screen-on-maximize, not something
broken-looking.

**How it works.**
- `TitleBar.tsx` renders the drag region and window-control buttons; clicks call
  `bridge.minimizeWindow()` / `toggleMaximizeWindow()` / `closeWindow()`.
- `BootScreen.tsx` shows for a minimum duration while `bridge.runIntegrityCheck()`
  runs, so the splash never flickers for fast starts.
- `toggle_maximize_window()` in `bridge/api.py` snaps the window to the monitor's
  *working area* (excludes the taskbar) using raw Win32 calls, not
  `window.maximize()`.

**How it was implemented (window chrome specifics):**
- `main.py` creates the window with `frameless=True`.
- `_force_exact_window_size(window)` is bound to `window.events.shown`, and uses
  `SetWindowPos` to force the exact requested pixel size once the window actually
  exists — pywebview's own sizing during `create_window()` wasn't reliable.
- `toggle_maximize_window()` reads `SystemParametersInfoW(SPI_GETWORKAREA)` and
  `GetWindowRect`/`SetWindowPos` directly via `ctypes`, entirely bypassing
  pywebview's `resize()`/`move()`.

**Issues faced:**
- **Maximize covered the taskbar.** Root-caused as a WinForms quirk: a
  **borderless** form's native `WindowState.Maximized` covers the *entire*
  monitor, because borderless forms skip the OS's normal maximize-to-work-area
  negotiation (`WM_GETMINMAXINFO`) unless the app handles it directly. Confirmed
  by reading pywebview's actual `platforms/winforms.py` source, not guessed.
  - **First fix attempt made it worse.** Using `webview.screens[].frame` combined
    with `window.resize()/move()` produced a window *larger than the screen*
    (1940×1100) because pywebview's own logical-to-physical DPI scaling was being
    applied a second time on top of values that were already physical pixels.
  - **Final fix:** pure `ctypes`/Win32 calls (`GetWindowRect`, `SetWindowPos`,
    `SystemParametersInfoW`) which all operate in the same raw pixel space — no
    scaling ambiguity to get wrong. Verified by directly measuring window bounds:
    1600×900 windowed, 1920×1027 maximized (matching the real work area, taskbar
    correctly excluded).
- **Window launched at 1750×952 instead of the requested 1600×900.** Root-caused
  to WinForms' `AutoScaleMode.Dpi` not reliably honoring the requested
  `Size(int(w*scale), int(h*scale))` — the observed width/height ratios (1.094 vs
  1.058) were non-uniform, ruling out a simple single DPI-factor explanation.
  Fixed with `_force_exact_window_size()` forcing the exact size via
  `SetWindowPos` once the window exists, rather than trusting the constructor's
  sizing.
- **A confusing false alarm.** While debugging the above, a *diagnostic test
  script* (`test_maximize.py`, not the real app) auto-clicked maximize and briefly
  showed the broken oversized/4:3 window. This looked identical to the real bug
  from the user's side and caused understandable alarm; clarified as the test
  script, which was killed immediately, and the fix continued on the real code
  path.

---

## 5. Theming & Experience Levels

**What it is.** A light/dark theme toggle, and a three-tier **Basic / Advanced /
Expert** content-density system that governs how much of the app's settings and
features are visible at once.

**Why.** The user asked for both a light/dark toggle and, separately, "basic,
advanced and expert" disclosure levels applied "from settings to homepage and other
things" — a way to hide complexity from new users without removing it for power
users.

**How it works.**
- `lib/use-theme.ts` — a `dark`/`light` toggle persisted to `localStorage`.
- `lib/use-experience.ts` — `ExperienceLevel = "basic" | "advanced" | "expert"`,
  persisted to `localStorage`, with a `levelAtLeast(current, min)` ordinal helper
  every gated UI element uses (`levelAtLeast(level, "advanced")`, etc.).
- The level pills live in `PrimaryNav.tsx`, top-right, and are read by `App.tsx`,
  `Dashboard.tsx`, `Settings.tsx`, `IconRail.tsx` to conditionally render
  additional cards, nav tabs, and fields.

**Issue faced — a real design bug, not a technical one:** the first version of
this feature added a *separate* STANDARD/ADVANCED toggle that duplicated the
existing "Nodes" nav tab (both existed to reveal the same advanced view). The user
caught this immediately: *"if you give a option to switch to nodes then what's the
use of standard and advanced? Find a alternative."* Fixed by decoupling entirely —
the three-tier system became a **content-density preference** independent of page
navigation (Nodes is still its own nav tab, gated at Advanced+, but Basic/
Advanced/Expert now controls how much *each individual page* shows, not which page
you're on).

---

## 6. Visual Design System

**What it is.** The full cyberpunk/HUD visual language: a lime/blue color palette,
numbered `"0N // LABEL"` section headers, corner-bracket panel frames
(`CornerFrame.tsx`), conic-gradient circular gauges for CPU/RAM, chamfered
(clip-path) glow buttons, and a monospace "tech" display font.

**Why.** Multiple rounds of "this isn't good enough, match the reference image" —
the user provided real SaaS-dashboard mockups and wanted a from-scratch overhaul
matching that fidelity, not an approximation.

**How it works.** Reusable primitives instead of one-off styling per page:
- `CornerFrame.tsx` — four absolutely-positioned corner-bracket `<span>`s wrapping
  any content, used on hero cards throughout Dashboard/Settings/Marketplace.
- The `"0N // LABEL"` numbering convention is applied by hand per card
  (`CardTitle` text), kept sequential within each page.
- Circular gauges (`HardwareIntelligence.tsx`) use conic-gradient CSS rather than
  SVG arcs, driven by live CPU/RAM percentages from `bridge.getHardwareSnapshot()`.
- Buttons use `[clip-path:polygon(...)]` for the chamfered-corner look plus a
  `shadow-[0_0_24px_-4px_var(--primary)]` glow.

---

## 7. Layout Fixes

Two separate, unrelated visual bugs the user caught in the same pass ("what rubbish
is this ui?? why r there black borders... and why is a long block going out of
screen"):

**7.1 Black borders around the whole app.**
- **Cause:** `index.html`'s boot-splash CSS styled `#root` *directly*
  (`display:flex;justify-content:center`, etc.). React replaces `#root`'s
  *children* on mount but never touches attributes/styles applied to `#root`
  itself — so the splash's centering styles persisted invisibly after the splash
  was gone, shrink-wrapping and centering the real app inside the window.
- **Diagnosis:** confirmed via direct DOM measurement —
  `TitleBar.getBoundingClientRect()` reported `x=148` instead of `x=0`.
- **Fix:** scoped all splash-only styling to a new `.boot-splash` class instead of
  `#root`; `#root` itself now only ever gets `min-height: 100vh`.

**7.2 Sidebar content overflowing its container instead of scrolling.**
- **Cause:** `LogConsole.tsx` had its own internal hardcoded `flex-1` **and**
  `min-h-[160px]`, which fought the `flex-1 min-h-0` wrapper `App.tsx`'s sidebar
  used around it — a `min-height` on the child fighting a `flex-1` parent is
  exactly the combination that causes silent overflow instead of either fitting
  cleanly or scrolling.
- **Diagnosis:** confirmed via direct measurement — the sidebar `<aside>`'s
  `clientHeight` was 728px but its `scrollHeight` was 908px.
- **Fix:** removed `LogConsole`'s internal `flex-1`; each call site now supplies
  its own explicit sizing (`h-[220px]` in the sidebar, `flex-1` on the dedicated
  Logs page).

**7.3 Later, unrelated: wasted horizontal space.** After the marketplace work,
Dashboard and Settings still used a narrow `mx-auto max-w-3xl` single-column
layout even in wide Advanced/Expert modes, forcing unnecessary vertical scrolling.
Per the user's explicit ask ("try prioritizing horizontal expansion rather than
prioritizing vertical expansion"), both pages were rewritten to responsive CSS
Grid rows (`grid-cols-1 xl:grid-cols-3`, etc.) so cards flow side-by-side first.
Verified via screenshot: all 5 Dashboard sections and all 4 Settings sections fit
on screen at 1600×900 in Expert mode with zero scrolling.

---

## 8. Settings System

**What it is.** A persisted settings store (`core/settings.py`, `settings.json`,
gitignored) covering every user-configurable default: language, voice, task
priority/quality defaults, background-preservation default, content-filter
default, auto-cleanup-temp, Ollama host, Whisper model size, plus (added later)
auto-detect-model-type and web-search config.

**Why.** The user asked for "a settings menu that allows changing of 'n' number of
features and settings."

**How it works.** `Settings.__init__` loads `DEFAULTS` merged with whatever's in
`settings.json`; `.get(key)`, `.update(partial)`, `.reset()`. `bridge.getSettings()`
/ `updateSettings()` / `resetSettings()` expose this to the frontend;
`Settings.tsx` is a real-time-saving form (`patch()` calls `updateSettings`
immediately on every field change, no separate "Save" button for regular fields).

**How it was implemented.** A single flat JSON file next to `config.py`.
Deliberately holds only settings that affect **Python-side behavior** — purely
cosmetic frontend preferences (theme, experience level) live in the browser's
`localStorage` instead, so the same fact is never owned by two different stores at
once (a class of bug the earlier PyQt6 build had run into).

---

## 9. Model Marketplace — Foundation

This is the first of six phases building the "universal model marketplace" the
user asked for: *"get rid of the current voice model selection feature... install
something better... a marketplace... allows addition of links to hugging face
models... attaching apis to models... connection to cloud models and local
models."*

**9.1 Credential Store (`core/credential_store.py`)**
- **What:** a thin wrapper around the `keyring` package (Windows Credential
  Manager / macOS Keychain / Linux Secret Service).
- **Why:** API keys for cloud models must never sit in `models.json` as plaintext.
- **How:** `set_credential(ref, value)` / `get_credential(ref)` /
  `delete_credential(ref)`. Only a *reference name* (e.g.
  `reflow.tts.a1b2c3d4`) is ever persisted to disk; the actual secret lives in the
  OS-native store. If no keyring backend exists, `set_credential` raises
  `CredentialError` rather than silently falling back to plaintext.
- **Verified:** a real Windows Credential Manager round-trip (store → retrieve →
  delete) via a direct test script, not just code review.

**9.2 Model Registry (`core/model_registry.py`)**
- **What:** `ModelRegistry`, backed by `models.json` (gitignored). One entry per
  connected/installed model, spanning `STAGE_TYPES = ["stt", "translation", "tts",
  "voice", "enhancer", "filter"]` and `KINDS = ["local_file", "local_api",
  "cloud_api"]`. Tracks one **active** model id per stage type.
- **Why:** replaces the old single-purpose RVC-only voice list with something
  generic enough for every pluggable stage.
- **How:** `.list(stage_type)`, `.add(...)`, `.remove(id)`, `.set_active(stage,
  id)`, `.get_active(stage)`, `.get_active_map()`. The first model added for a
  stage type auto-becomes active.
- **Verified:** add/list/set_active/remove, plus reload-from-disk persistence,
  all confirmed correct via a direct test script.

**9.3 Downloader (`core/downloader.py`)**
- **What:** a generic streaming file downloader with **live speed/ETA metrics**,
  replacing `core/model_manager.py`'s RVC-only download logic.
- **Why:** the user explicitly asked for "option to download models within this
  tool with proper download metrics with download speed and other things."
- **How:** `download_with_progress(url, dest_path)` is a generator yielding
  `{"phase", "downloaded", "total", "percent", "speed_bps", "eta_seconds"}` dicts
  computed over a rolling ~0.5s window (not per-chunk, so numbers are stable, not
  noisy). `resolve_download_url()` auto-fixes Hugging Face `/blob/` (viewer) links
  to `/resolve/` (raw download) links.
- **Issue faced — download progress showing 265%.** Some CDNs
  (`raw.githubusercontent.com`) gzip-compress the HTTP response; the `requests`
  library transparently decompresses it while iterating, so the bytes actually
  written to disk end up *larger* than `Content-Length` (which reflects the
  *compressed* size) — producing a nonsensical >100% progress readout. **Fixed**
  with `headers = {"Accept-Encoding": "identity"}`, disabling server-side
  compression entirely. Verified with a real download: 265% before the fix, exact
  100% match after.

---

## 10. Model Marketplace — Provider Abstraction

**What it is.** One small abstract base class per pipeline stage type
(`core/providers/base.py`): `STTProvider`, `TranslationProvider`, `TTSProvider`,
`VoiceProvider`, `EnhancerProvider`, `FilterProvider`. `core/pipeline.py` now calls
through these typed interfaces instead of instantiating a specific handler class
(`STTHandler`, `LLMTranslator`, etc.) directly.

**Why.** This is the architectural piece that makes "swap the implementation for
any stage" possible at all — without it, adding a cloud TTS option would mean
editing `pipeline.py` itself every time.

**How it works.** Each stage gets a **local adapter** wrapping the existing
handler with zero behavior change (`core/providers/stt/whisper_local.py`,
`.../translation/ollama_m2m100_local.py`, `.../tts/xtts_local.py`,
`.../voice/rvc_local.py`, `.../enhancer/gfpgan_local.py`,
`.../filter/nudenet_local.py`). `pipeline.py`'s `process_video_gen()` calls
`stt_provider.transcribe(...)`, `translation_provider.translate(...)`, etc.,
instead of the old handler-specific method names.

**How it was implemented — the extraction was done carefully to avoid two classes
of regression:**
1. **STT subprocess isolation.** The pipeline had always run Whisper transcription
   in a **separate subprocess** (`core/run_stt.py`), deliberately, for two
   reasons: faster-whisper + CUDA is a known DLL-crash combination (so it's forced
   to CPU), and running in a separate process means a crash there can't take the
   main app down. A first draft of `WhisperLocalProvider` transcribed **in-process**
   instead, silently dropping that isolation. **Caught and fixed before it
   shipped**, by rewriting the provider to shell out to `run_stt.py` exactly as
   the original code did.
2. **Per-segment model reload.** `TranslationProvider`/`TTSProvider`/
   `VoiceProvider`'s `.translate()`/`.synthesize()`/`.convert()` are called **once
   per subtitle segment** in a loop, but the underlying handlers
   (`LLMTranslator`, `TTSHandler`, `RVCHandler`) do expensive model loading in
   their constructors. Each provider lazy-caches its handler
   (`self._handler = None` in `__init__`, built on first call only) so the
   constructor cost is paid once per video, not once per segment — this was
   **caught proactively** by reading `pipeline.py`'s actual call sites before
   writing the providers, not discovered after the fact.

**Verified:** `core.pipeline` imports and `ReflowPipeline()` instantiates cleanly
under the real runtime `sys.path` setup; all six provider modules import without
error; the superseded `apply_content_filter()` method and `stt_worker_script`
attribute have zero remaining references anywhere in the codebase.

---

## 11. Model Marketplace — Cloud REST Providers

**What it is.** A generic REST adapter per stage type
(`core/providers/*/cloud_rest.py`), each configured with an `api_base_url`, a
`credential_ref`, and a named **request preset** — instead of a bespoke SDK
integration per vendor.

**Why.** "Any possible model" realistically means "point at an HTTP endpoint with
an API key and tell it which JSON fields to use," not hand-integrating every
vendor's SDK. This was an explicit scoping decision made up front.

**How it works.** `core/providers/cloud_rest_common.py` holds the shared plumbing
(`resolve_credential()`, `request()`, `poll_until_done()` for async job-style
APIs). Each stage's `cloud_rest.py` defines a small dict of named presets:
- **TTS:** `openai_tts`, `elevenlabs_tts`, `custom`.
- **STT:** `openai_whisper`, `custom`.
- **Translation:** `openai_chat` (also covers most local servers that mimic the
  OpenAI chat-completions shape — Ollama's `/v1` endpoint, LM Studio, etc.),
  `custom`.
- **Voice:** `elevenlabs_sts`, `custom`.
- **Enhancer / Filter:** `custom` only — video-processing APIs are rarely a single
  synchronous request, so `custom` supports both a direct response and an
  async submit → poll → download job pattern via `poll_until_done()`.

`custom` always covers anything not named, via a user-supplied JSON body template
(`{"text": "{text}", "language": "{language}"}`-style placeholders).

**Issue faced — credential_ref treated as required everywhere.** The Marketplace's
"Local Service" add-flow deliberately collects **no** API key (Ollama-style local
servers usually need none) — but four of the five `cloud_rest.py` providers
(`tts`, `stt`, `voice`, `enhancer`, `filter`) called `resolve_credential()`
unconditionally, which raises if `credential_ref` is empty. A Local Service model
for any of those stages would have crashed on the very first request. **Fixed**
by making credential resolution optional everywhere (`api_key =
resolve_credential(ref) if ref else None`), matching how `translation`'s adapter
already handled it correctly. **Verified** with a real HTTP round-trip against a
local mock server with `credential_ref=None`, confirming no `Authorization` header
was sent and the response was still handled correctly.

**Verified (broader):** a local mock HTTP server test suite covered the
`openai_chat` and `custom` translation presets, the `custom` STT preset, and the
`custom` TTS preset — real request/response parsing, not mocked at the function
level. A request against a `credential_ref` with nothing stored correctly raised
`CloudRestError` with a clear message instead of a raw exception.

---

## 12. Model Marketplace — AirLLM Provider

**What it is.** `core/providers/translation/airllm_local.py`, a Translation-stage
option that runs a full-size HF language model with **layer-by-layer disk
offloading** via the [AirLLM](https://github.com/lyogavin/airllm) library.

**Why.** The user explicitly asked for AirLLM integration, "to allow running heavy
models on a low end system." It's deliberately scoped as *just another
Translation-stage provider*, not a new top-level feature — selected the same way
any other model is, via the registry.

**How it works.** `AutoModel.from_pretrained(hf_model_id)` streams each
transformer layer from disk on demand during inference instead of holding the
whole model in VRAM/RAM — trading speed for the ability to run 70B+ models on
hardware that couldn't otherwise load them at all. Lazy-cached (`self._model =
None` until first `.translate()` call) for the same reason as the other
segment-called providers.

**How it was implemented.** Standard HF tokenizer/`generate()` interface: builds a
translation prompt, tokenizes, calls `model.generate()`, then **slices off the
prompt tokens before decoding** so callers get just the translation, not the
echoed instruction (an improvement over AirLLM's own basic usage example, which
decodes the full sequence including the prompt).

**Verified:** since `airllm` isn't installed in the dev sandbox, verification was
scoped to what's checkable without it — confirmed the provider **constructs**
without importing `airllm` at all (proving the lazy-load is real, not accidental
eager import), and confirmed calling `.translate()` fails with a clear
`ModuleNotFoundError` rather than a confusing unrelated error, matching the newly
declared `airllm` dependency in `requirements.txt`/`portable_requirements.txt`.

---

## 13. Model Marketplace — Frontend

**What it is.** `frontend/src/pages/Marketplace.tsx` — a page tabbed by the 6
stage types, each showing installed models as cards (kind/status badges, a
"set active" star, a remove button), with an "+ Add Model" dialog offering three
flows: Local Download, Cloud API, Local Service.

**Why.** This is the actual replacement for the retired RVC-only "Voice Model
Library" card in `Assets.tsx` and the retired `list_voice_models`/
`import_voice_model` bridge methods.

**How it works.**
- `frontend/src/lib/use-marketplace.ts` — `useMarketplace(stageType)` hook:
  fetches the model list + active model on mount, subscribes to
  `model_download_progress` / `model_installed` / `model_download_error` push
  events (the same channel render progress uses), and exposes
  `setActive`/`remove`/`addLocal`/`addCloud`/`addLocalApi`.
- Downloading a local model runs in a **background thread**
  (`bridge/api.py`'s `_run_local_download`), pushing `model_download_progress`
  events exactly like `core/downloader.py`'s generator produces them.
- Adding a cloud/local-API model previously returned synchronously with **no**
  push event, meaning a *different* mounted tab wouldn't pick it up automatically.
  **Fixed** by having `add_cloud_model`/`add_local_api_model` also emit
  `model_installed` on success — the exact same subscription every tab already
  has now covers every add path uniformly, with no extra frontend plumbing.
- **Migration for existing users:** `core/marketplace.py`'s `seed_voice_models()`
  runs once on `PythonBridge.__init__` — if the registry has zero `voice`
  entries yet, it scans the old `models/rvc/weights/` folder and auto-registers
  any `.pth` files found, plus the always-available `CLONED_USER`
  (reference-audio-clone) option. **Verified live**: this correctly picked up
  this project's actual pre-existing RVC models (`MorganFreeman`, `TaylorSwift`,
  `trump`) on first run.
- **Install logic for downloaded voice models** (`.pth`/`.index` sorting into
  `models/rvc/weights/` and `models/rvc/logs/`) was ported from the old
  `core/model_manager.py` into `core/marketplace.py`'s
  `install_downloaded_voice_model()`, since `RVCHandler.infer()` still expects
  that exact directory convention regardless of how the file arrived.

**Issue faced — CLONED_USER value mismatch.** The built-in seeded entry was
initially named `"CLONED_USER (From Reference)"` for a friendlier display label —
but `core/settings.py`'s `default_voice` default and `Dashboard.tsx`'s initial
`useState` are both the literal string `"CLONED_USER"`. Since the Select's option
`value` is the model's `display_name`, the mismatch meant the dropdown showed
blank on load. **Fixed** by renaming the built-in entry's `display_name` to
exactly `"CLONED_USER"` (the value doubles as an identifier here, not just a
label).

**Later — user-reported bug:** the CLONED_USER entry couldn't be deleted; the UI
explicitly hid its remove button (`{!model.meta?.builtin && (...)}`). There was no
real reason to protect it — `pipeline.py`'s clone-detection is a plain substring
check (`"CLONED_USER" in actor`) entirely independent of whether a registry entry
exists. **Fixed** by removing the special case; it deletes like any other model.

---

## 14. Model Marketplace — Registry-Driven Resolution

**What it is.** `core/providers/resolve.py` — `resolve_stt()`, `resolve_translation()`,
`resolve_tts()`, `resolve_voice_for_actor()`, `resolve_enhancer()`,
`resolve_filter()`. `pipeline.py` calls these instead of hardcoding a `*_local`
provider for every stage.

**Why.** Without this, "Set Active" in the Marketplace was **cosmetic** — the
registry recorded the user's choice, but `pipeline.py` kept silently using the
local provider regardless of what was marked active. This closes that gap.

**How it works.** Each `resolve_*()` checks `ModelRegistry.get_active(stage_type)`;
if the active entry's kind is `cloud_api` or `local_api`, it returns the matching
`cloud_rest.py` provider configured with that entry's `api_base_url`/
`credential_ref`/`request_preset`. Otherwise it falls back to the `*_local`
provider with whatever construction args `pipeline.py` already computes (device,
settings) — so a render behaves **exactly as before** for anyone who's never
touched the Marketplace.

**Voice is resolved differently from the other five stages.** It's chosen **per
cast member** (the Dashboard's per-render dropdown / the graph's cast list), not a
single global "active" model — so `resolve_voice_for_actor(registry, actor_name,
device)` looks up the registry entry whose `display_name` matches the actor's
exact name, instead of `get_active("voice")`. This means multiple cast members can
genuinely mix local RVC voices and cloud voices in the same render.

**How it was implemented — avoiding a regression.** A single shared `voice_provider`
instance created once per video (as Section 10 describes) doesn't work once
different segments can use *different* actors resolving to *different* provider
classes. Resolved voice providers are **cached per actor name** across the
segment loop (`voice_providers_by_actor` dict in `pipeline.py`) — a new provider
is only constructed the first time a given actor is seen in that render, avoiding
the exact per-segment reload regression Section 10 was careful to prevent in the
first place.

**Verified:** a standalone script against a throwaway registry file confirmed
`resolve_stt()` returns the local provider on an empty registry and the cloud
provider (with the right `base_url`/preset) once a model is added and set active;
`resolve_voice_for_actor()` correctly returns a cloud provider for a matching
actor name and falls back to local for any other actor in the same registry.

---

## 15. Pipeline Permutation Templates

**What it is.** Four named pipeline flows dispatched through
`ReflowPipeline.run(template_id, input_path, params)`:
- `video_dub` — the original default flow (video → STT → translate → TTS/RVC →
  mux → video).
- `video_dub_lipsync` — `video_dub` + lip sync (already existed as a toggle;
  the template is really just syntactic sugar over it).
- `audio_dub` — audio → STT → translate → TTS/RVC → audio, **no video at all**.
- `subtitle_translate` — subtitle file → translate → subtitle file, skipping
  STT/TTS/video entirely.

Soft-subtitle attachment isn't a separate template — `merge_av()` already muxes
the `.srt` as a real subtitle stream (`-c:s mov_text`) via `burn_subs=False`,
reachable through `video_dub`'s existing `burn_subtitles` parameter.

**Why.** This is the direct implementation of the user's explicit list of desired
flows: *"video → stt → translation → tts → video, audio → stt → translation → tts
→ audio, video → ... → lipsync, ... subtitles integration as attachment, subtitle
→ translation → subtitle."*

**How it works.** `core/pipeline.py`'s `_dub_segment()` (TTS + RVC + mastering +
speed-matching for **one** transcript segment) was extracted out of
`process_video_gen()`'s inline loop body, since `audio_dub` needs the exact same
logic. `process_video_gen()`'s loop now just calls it; `process_audio_dub_gen()`
reuses it directly. `process_subtitle_translate_gen()` is backed by a new,
dependency-free SRT parser (`core/srt_utils.py`) since the input is already
correctly-timed text with no audio/video involved at all.

**Issue faced — a real bug caught during the extraction, before shipping.** The
original inline loop only overlaid a dubbed clip onto the master audio track
*inside* an `if len(clip) > 0 and target_dur > 500:` block — a segment shorter
than 500ms or with zero-length audio was silently **dropped**, not overlaid. The
first draft of the extracted `_dub_segment()` helper returned the clip
**regardless** of that check, which would have made the caller overlay
unmatched-length audio for short/empty segments — a real behavior change.
**Caught by close comparison against the original code** before it shipped;
fixed by having `_dub_segment()` also return `None` when that check fails, exactly
matching the original's skip behavior.

**How `bridge/api.py` routes to this:** `start_render()` takes an optional
`template_id` (default `"video_dub"`, so every existing caller is unaffected);
`_template_kwargs()` maps the one `RenderParams` shape the frontend always sends
into whatever kwargs each template actually accepts (e.g. `subtitle_translate`
only needs `{"target_lang": ...}`).

**Frontend:** `Dashboard.tsx` gained a Pipeline Template selector inside the
Source Input card. Changing it swaps which file picker/fields are shown (the
video queue, a single audio file, or a single subtitle file) and which param
subset gets sent — Voice/Reference Audio hide entirely for `subtitle_translate`,
and the Configuration card's video-only toggles (lip sync, enhancer, burn-subs,
content filter) hide for any non-video input.

**Verified:** a real `.srt` round-tripped through `generate_srt()` →
`parse_srt()` byte-for-byte. `subtitle_translate` was run end-to-end through
`run()` twice — once with `target_lang="source"` (pure passthrough) and once
against a local mock HTTP server standing in for an *active cloud translation
model*, confirming the template genuinely routes through the registry's active
model, not just the local default. Live-launched the app and screenshotted
Dashboard after switching templates: the source picker adapted correctly, and the
Expert "Render Params" preview showed exactly `{"lang": "en"}` for
`subtitle_translate` — matching `_template_kwargs()` precisely.

---

## 16. Node Graph Editor Fixes

**16.1 Nodes couldn't be dragged.**

- **What was wrong:** `Nodes.tsx` passed a `nodes` array to `<ReactFlow>` without
  ever wiring an `onNodesChange` handler.
- **Why that breaks dragging:** React Flow needs `onNodesChange` to actually apply
  position updates back into the state you control. Without it, dragging *looks*
  live during the gesture (React Flow's own internal transient state handles
  that), but the instant **any** unrelated re-render happens — even the hardware
  panel's periodic polling — the `nodes` array gets recomputed from the original
  server-side `x`/`y` values and the node snaps right back.
- **Fix:** rewrote `Nodes.tsx` around `useNodesState`/`useEdgesState`, so drag
  positions live in React Flow's own state after the initial load, fully
  decoupled from the server definition.
- **Verification note — synthetic events don't work here.** The first
  verification attempt dispatched synthetic `PointerEvent`s via JavaScript
  (`node.dispatchEvent(new PointerEvent(...))`). This consistently showed *no*
  position change, because drag libraries generally check `event.isTrusted`
  (always `false` for script-dispatched events, and **not spoofable** from JS) and
  ignore untrusted input. **Switched to real OS-level mouse simulation**
  (`SetCursorPos` + `mouse_event` via a small C# `DllImport` shim in PowerShell) —
  a genuinely trusted input source — and confirmed via before/after screenshots
  that the dragged node (and its connected edge) both moved and stayed moved.

**16.2 CLONED_USER couldn't be deleted.** Covered in Section 13 — same fix, applies
here as the Marketplace-side half of the same user report.

---

## 17. Multi-Cast Voice Nodes

**What it is.** The "Voice (TTS + RVC)" node on the graph can now be duplicated;
each instance has its **own independently editable** voice-model dropdown, and the
resulting list of chosen voices is what `ReflowPipeline` actually cycles through
per subtitle segment during a render.

**Why.** When asked what "add nodes" should mean — given the pipeline's execution
order is hardcoded in Python rather than truly graph-driven, so arbitrary node
addition wouldn't *do* anything — the user picked "allow duplicate stage
instances" specifically for multi-cast dubbing. This was scoped to the one stage
that already had a real underlying mechanism: `process_video_gen()` already
selects `cast_list[i % len(cast_list)]` per segment, just with no UI way to
populate more than one entry.

**How it works.**
- `core/graph_model.py`: `NodeSpec` gained a `duplicable` flag (only `True` for
  `tts_rvc` — duplicating any other stage would just be an inert second box, since
  nothing in `pipeline.py` knows what to do with two STT nodes). `Node` gained a
  `removable` flag (`False` for the fixed backbone graph, `True` only for
  runtime-added instances) so the original node can never be deleted, only added
  copies of it.
- `core/node_registry.py`: `tts_rvc`'s `voice` param changed from `kind="readonly"`
  (a static mirror of the Dashboard's single choice) to `kind="combo"` — genuinely
  editable per node, since that's the entire point of having more than one.
- `bridge/api.py`: `add_node_instance(spec_id)` / `remove_node_instance(node_id)` /
  `set_node_param(node_id, key, value)`, plus `get_cast_list()` (every Voice
  node's chosen voice, oldest first). `get_graph_definition()` injects the
  **live** list of installed voice models into the dropdown's options at request
  time, since `node_registry.py` itself has no knowledge of the model registry.
- **Zero change to the default single-voice path:** `_resolve_cast_list()` only
  uses the graph's cast list when it has **2 or more** entries (i.e. the user
  explicitly added a second Voice node); otherwise it falls back to the
  Dashboard's own single voice dropdown exactly as before this feature existed.
- **Frontend:** `StageNode.tsx` gained duplicate/remove buttons in the node
  header (marked with React Flow's `nodrag` class so clicking them doesn't
  trigger the node-drag gesture from Section 16) and a native `<select>` for
  `combo`-kind params. `Nodes.tsx` reloads the whole graph from the server after
  an add/remove (the node/edge *set* changes, unlike a drag or a toggle), rather
  than trying to patch local state.

**Verified:** a direct backend script exercised the full flow — added two extra
`tts_rvc` instances, set each one's voice independently, confirmed
`get_cast_list()`/`_template_kwargs()` returned the right multi-entry list in
insertion order; confirmed a duplicate request for a non-duplicable spec
(`"stt"`) is rejected; confirmed the base node can't be removed while an added
instance can. Live-launched the app and drove a real click sequence: duplicated
the Voice node, confirmed two `<select>` elements each listing all 4 real
installed voice models, changed the second one to `"MorganFreeman"`, and
confirmed via screenshot that both nodes render correctly wired downstream into
Lip Sync with independent voice selections.

---

## 18. Auto-Detect Model Type

**What it is.** When adding a model, instead of requiring the user to pick a stage
tab (STT/TTS/Voice/etc.) *before* they know what they're adding, `core/model_detect.py`
inspects the pasted link and suggests a stage type.

**Why.** User request: *"the user just connects the api or local or zip file and
the tool automatically detects what type of model is that... voice, tts, lipsync,
etc."*

**How it works — two tiers of signal:**
1. **Hugging Face metadata (high confidence).** For any Hugging Face link, queries
   HF's own public model API for the model's declared `pipeline_tag` (a signal
   the model's *author* set, not a guess) —
   `automatic-speech-recognition → stt`, `text-to-speech → tts`,
   `translation → translation`, `audio-to-audio → voice`,
   `image-to-image → enhancer`, `image-classification → filter`.
2. **Keyword matching (low confidence, fallback).** For anything else, or if the
   HF lookup fails/returns nothing recognized: matches known engine/architecture
   names against the URL — `whisper → stt`, `rvc`/`so-vits → voice`,
   `xtts`/`tts`/`coqui → tts`, `m2m100`/`nllb → translation`,
   `gfpgan`/`real-esrgan → enhancer`, `nudenet → filter`.
3. **API host hints (weakest, cloud/local-API links only).** A small known-host
   list (`elevenlabs`, `openai.com`, `ollama`) gives a starting guess for a base
   URL, always low confidence since one host can serve multiple task types.

**Every result is a suggestion, never applied silently** — the Marketplace's Quick
Add dialog shows it with a confirm/override dropdown.

**How it was implemented.** `bridge/api.py`'s `detect_model_type(link, link_kind)`
calls into `core/model_detect.py`. Gated behind a new `auto_detect_model_type`
setting (default **on**), with a toggle on the Settings page.

**Issue faced — a real regex bug caught before shipping.** The first version used
`\brvc\b` to match "rvc" as a whole word. Real filenames overwhelmingly separate
words with **underscores**, not spaces (`my_custom_RVC_model.zip`) — and regex
`\b` treats `_` as a word character, so there's **no** boundary between `_` and
`R`, meaning `\brvc\b` silently failed to match the single most realistic example
of exactly the filename pattern it was written for. **Caught by testing against a
realistic filename**, not just a clean one. Fixed by rewriting the short/ambiguous
keywords (`rvc`, `tts`, `asr`) with a custom boundary,
`(?<![a-zA-Z])word(?![a-zA-Z])`, that treats any *non-letter* (underscore, hyphen,
digit) as a valid separator instead of relying on `\b`.

**Verified against real Hugging Face API calls (not mocked):**
`openai/whisper-large-v3 → stt`, `facebook/nllb-200-distilled-600M → translation`,
both "high confidence" via `pipeline_tag`. Keyword fallback re-tested after the
regex fix and confirmed to correctly match underscore-separated filenames without
false-positiving on unrelated strings (e.g. a filename containing neither `rvc`
nor `tts` as a real token correctly returns no match).

---

## 19. Auto-Pick Best Model

**What it is.** An "Auto-pick best model" button (in both the per-stage Add Model
dialog and the cross-stage Quick Add dialog) that finds and suggests the best
available model for a stage instead of making the user browse manually.

**Why.** User request: *"there should be an auto option that automatically selects
the best available model... after a google or any search engine check."* Clarified
via an explicit design-fork question before building: the user chose **"Hugging
Face ranking first, web search as an optional fallback"** over a search-API-only
approach, since the HF path works today with no external dependency or API key.

**How it works — two layers:**
1. **Hugging Face ranking (always available, no setup).**
   `core/model_detect.py`'s `find_best_hf_model(stage_type)` queries HF's public
   models API sorted by **real download counts** — the same signal HF's own "Most
   Downloads" filter uses, not a fabricated score — for the pipeline tag matching
   that stage. Returns the top few candidates with repo id, URL, download count,
   and like count.
2. **Web search (opt-in enrichment).** `core/web_search.py` is a pluggable
   provider abstraction (matching the same "presets" pattern the cloud REST
   adapters use), shipped with one provider — Google Programmable Search / Custom
   Search JSON API, the most commonly available "Google search" API. Entirely
   inert until the user configures a provider + API key + search-engine ID in
   Settings; results are always shown as **candidate links to review**, never
   auto-installed — a raw search ranking isn't a strong enough trust signal to
   download and run something unattended.

**How it was implemented.** `bridge/api.py`'s `find_best_model(stage_type)`
combines both: always runs the HF ranking, and additionally runs a web search
*only if* `web_search.is_configured(...)` is true (checking a stored provider,
API key via the credential store, and engine ID). `get_search_config()` /
`set_search_credentials()` manage that configuration — the API key goes through
`core/credential_store.py` under a fixed reference name; the Google
Custom-Search-Engine ID is a public, non-secret identifier and is stored directly
in `settings.json`.

**Frontend:** a shared `AutoPickSection` component (used identically in both
dialogs) shows ranked HF candidates with their download counts, plus any web
results underneath; clicking any candidate fills the Local Download form's
name/URL fields for the user to review before submitting — nothing is added
automatically just from clicking "Auto-pick."

**Verified against the real Hugging Face API (not mocked):** `find_best_model`
for `"tts"` and `"voice"` both returned real, currently-top-ranked models with
accurate download counts. Live-launched the app and drove a full click sequence
through `pywebview`'s `evaluate_js` — opened the Voice tab's Add Model dialog,
clicked Auto-pick, confirmed three real HF results rendered with correct download
counts, clicked the top one, and confirmed the Display Name and Model URL fields
were correctly filled with that exact result's repo id and URL.

---

## 20. Full QA Audit & Feature Verification Pass

**What it is.** A complete click-through audit of every setting, toggle, and
button in the app, done in response to a direct request rather than as part of
building a new feature.

**Why.** User request: *"now check if every setting and option and feature and
click is working or not."*

**How it was done.** Live-launched the real app (not a test harness) and drove
every interactive element via `pywebview`'s `evaluate_js`, with real OS-level
mouse clicks where synthetic JS events aren't trustworthy (Radix UI's `Tabs`
component listens for `mousedown`, not `click` — confirmed by reading
`node_modules/@radix-ui/react-tabs/dist/index.mjs` directly — so a plain
`.click()` call silently does nothing on a Tabs trigger even though it works
fine on ordinary buttons/switches). OS-level synthetic clicks needed one more
correction: `getBoundingClientRect()` returns **logical** (CSS) pixels, but
`GetWindowRect()` (used to find the window's on-screen origin) returns
**physical** pixels, so the logical coordinate had to be multiplied by
`devicePixelRatio` (≈1.104 on this display) before adding it to the window
origin — otherwise clicks landed slightly off-target.

**Real bugs found and fixed as a direct result of this audit:** node dragging
not working, the CLONED_USER voice model being un-deletable, and the missing
Initialize Pipeline button on the Nodes page (see §23) — all in the Complete
Bug/Issue Log below.

**False positives retracted rather than "fixed":**
- **"Marketplace's stage tabs are broken."** Investigated and found two
  stacked bugs in the *audit's own test script* — the DPI-scaling gap above,
  plus not accounting for Radix's `mousedown` requirement — not in the app.
  Explicitly told to the user rather than silently moving on, since a claimed
  bug that turns out to be tooling error is exactly the kind of thing worth
  surfacing.
- **"Dashboard switches aren't toggling."** Reading a switch's `aria-checked`
  attribute in the *same* `evaluate_js` call that triggered its `.click()`
  reads pre-render state — React hasn't re-rendered yet within that single
  synchronous block. A follow-up check in a separate call (after a short
  delay) showed the toggle had in fact worked correctly both times.

This section exists specifically so a false alarm caught mid-audit is on the
record with its actual root cause, not left implying the app had a bug it
never had.

---

## 21. Per-Device Render-Time ETA & Radial Gauge

**What it is.** An "Estimated Render Time" card on the Dashboard (Advanced+,
video templates only) showing a radial gauge plus a full per-device breakdown
list of how long the queued job would take on every detected compute device.

**Why.** User request, remembered from earlier in the session: *"I wanted a eta
for each selected gpu/cpu... it would be best if you could add a interactive
loading bar or pie or circle whatever for the same."* The backend estimator
(`core/hardware_monitor.py`'s `estimate_eta_seconds`/`estimate_peak_vram_mb`,
exposed via `bridge/api.py`'s `estimate_job`) already existed from earlier
work, but grepping the frontend confirmed `estimateJob` was never actually
called from any page — the feature was backend-only and invisible.

**How it works.** `bridge/api.py` gained `estimate_job_all_devices(video_path,
stage_flags)`, which probes the video's duration once and returns an ETA for
**every** detected device in a single round-trip, instead of the frontend
needing one call per device. `RadialGauge.tsx` (`frontend/src/components/panels/`
— the same conic-gradient gauge already used for live CPU/RAM load) gained an
optional `centerLabel` override so it can display a duration ("21s") instead
of always assuming it's showing a percentage. Crucially, **the ring's fill
percentage isn't "how close to done"** — it's "how fast this device is
relative to the others for this exact job" (100% = fastest option available,
0% = slowest), so the gauge doubles as a decision aid for picking a device,
not just a readout.

**How it was implemented.** `Dashboard.tsx`'s new card refetches whenever the
queued video or any stage toggle (background/lipsync/enhance/content filter)
changes, showing the gauge for the currently-selected device plus the full
per-device list below it — so switching GPU/CPU in the sidebar's device
selector has a visible payoff before committing to a render.

**Verified against a real generated test video** (`ffmpeg testsrc`, 10s):
confirmed via direct DOM inspection (not just a screenshot — the gauge's glow
effect can look deceptively "filled" even near 0%) that the conic-gradient
background was exactly `conic-gradient(var(--secondary) 0%, ...)` for the
correctly-identified slowest device (CPU, 21s) against two other real detected
devices (Intel UHD 12s, NVIDIA RTX 4060 5s), with the per-device breakdown
list showing all three numbers correctly.

---

## 22. Marketplace Full Reset — Retiring Auto-Seeded Models

**What it is.** Removing every default/auto-populated entry from the model
registry, and removing the code path that silently re-added them.

**Why.** User request: *"remove all and allow connection to any possible
model... from the marketplace."* The registry previously auto-seeded a
`CLONED_USER` RVC voice-model entry (and any leftover `.pth` files) any time
the voice registry was found empty — discovered as the actual root cause when
a "remove all" the user performed kept silently coming back after an app
restart, fighting their deliberate intent to start from a clean slate.

**How it was implemented.** `core/marketplace.py`'s `seed_voice_models()` and
its single call site in `bridge/api.py` were deleted outright, not disabled
behind a flag — there's no scenario where re-seeding is wanted once a user has
explicitly cleared the registry. The Marketplace now reflects **only** what's
been explicitly connected by the user; a fresh `models.json` (or one with
everything removed) stays empty across restarts instead of self-healing back
to a default state.

**Verified:** confirmed via direct inspection that `models.json` had zero
entries after a full removal + app restart, and that core engines (Whisper,
XTTS, NudeNet — the underlying local libraries, as distinct from Marketplace
*entries* pointing at them) remained untouched and importable, in direct
response to the user's explicit follow-up question ("so u sure nothing exists
like Whisper, NudeNet, XTTS?? Or anything else?") before this change was made.

---

## 23. Dashboard/Nodes Render-Config Unification & Persistence

**What it is.** Three related fixes bundled into one change: (1) a single
shared, persisted render configuration used by both Dashboard and Nodes
instead of each keeping its own disconnected copy, (2) that configuration
surviving an app restart, and (3) an Initialize Pipeline / Stop control added
directly to the Nodes page.

**Why.** User report: *"on advanced or expert mode both node and dashboard
both work differently... the nodes window does not have its own initialize
pipeline so I have to switch to dashboard to do the same... link both such
that enabling of a node makes the dashboard options change too accordingly and
add an initialize pipeline overlay like button to node window too."* Also
folded in a separate, explicit request: *"add a system to retain the setting
and model's selected/used in the previous tool use."*

**How it works.**
- `frontend/src/lib/use-render-config.ts` (new): a shared, `localStorage`-
  persisted store for the entire render configuration — template, language,
  voice, reference audio, the four stage toggles, task priority, texture
  quality — following the same shared-module-level-state + subscriber pattern
  already established by `lib/use-queue.ts`, so no React Context is needed.
  Dashboard and Nodes both read/write through this one store instead of each
  holding a disconnected copy — the same class of bug as the earlier
  Basic/Advanced-vs-Nodes-tab duplication (§ Theming & Experience Levels),
  just for stage toggles instead of page navigation.
- A `STAGE_NODE_MAP` ties the four toggles that have a real corresponding
  pipeline node (Preserve Background / Lip Sync / Face Enhancer / Content
  Filter) to that node's id, so flipping either the Dashboard switch **or**
  the matching Nodes-graph switch updates both — and pushes the change to the
  backend graph (which isn't itself persisted across restarts) so the two stay
  in sync from the very first paint, not only after a manual toggle.
- `Nodes.tsx` gained its own render status bar and Initialize Pipeline/Stop
  button, reusing the same `useRenderJob()` hook (`frontend/src/lib/use-render.ts`)
  and video queue Dashboard already used — directly answering the reported gap
  that a graph edit required switching back to Dashboard just to run it.
- Persisting to `localStorage` means a render configuration now survives an
  app restart instead of silently resetting to defaults on every launch.

**Verified live, in both directions:** toggling "Lip Sync Engine" on Dashboard
and switching to Nodes showed the Lip Sync node's switch already checked;
toggling the Face Enhance node directly on the graph and switching back to
Dashboard showed "Face Enhancer" checked there too. Selecting a video via
Dashboard's browse flow and switching to Nodes showed its Initialize Pipeline
button go from disabled to enabled. `localStorage` correctly held the full
persisted config after a reload.

---

## 24. Opt-In AirLLM Translation Provider

**What it is.** AirLLM (`core/providers/translation/airllm_local.py` — runs a
full Hugging Face causal-LM with layer-by-layer disk offloading, trading speed
for the ability to run large models on very little VRAM) made reachable as a
real, opt-in Marketplace option.

**Why.** The provider itself had been built earlier in the session but was
completely unreachable — the registry only understood `local_file`/
`local_api`/`cloud_api` *kinds*, and `resolve_translation()` had no branch for
it at all, so connecting one would have silently done nothing. The user was
explicit that it *"should not just get used by default at every use"* — it
needed to be a deliberate, visible choice, not implicit behavior.

**How it works.** `bridge/api.py`'s `add_airllm_model(display_name,
hf_model_id, compression)` registers a normal translation-stage registry entry
— `source_url` holds the HF model id, and `request_preset="airllm"` is the
marker that distinguishes it from every other translation entry. Like any
other model, it does **nothing** until the user also sets it Active.
`core/providers/resolve.py`'s `resolve_translation()` checks for
`request_preset == "airllm"` first and constructs
`AirLLMTranslationProvider` accordingly, falling through to the normal
Ollama/M2M100 default otherwise. `Marketplace.tsx`'s `AddModelDialog` gained a
4th "AirLLM" tab (HF model id + compression level picker), shown **only** for
the Translation stage — the one architecture family AirLLM actually supports.

**Issue faced — user asked to extend it to every stage, declined with a
technical explanation instead of building fake wrappers.** After this shipped,
the user asked *"So AirLLM only works on translation model?? Add the same
feature to all the things — stt, tts, translation, voice etc."* AirLLM only
supports causal-LM (LLaMA/Mistral/Qwen-family) architectures via
`transformers` — it has no mechanism to run Whisper (STT), XTTS (TTS), or RVC
(Voice), which are fundamentally different model architectures. Building a
"fake" AirLLM wrapper for those stages that either silently didn't work or
quietly fell back to the normal engine would have been worse than not building
it — the reasoning was explained directly rather than shipping non-functional
code just to satisfy the literal request. This same judgment call recurs later
in §30 for the custom-instructions feature.

**Verified:** a direct script confirmed `resolve_translation()` returns
`OllamaM2M100LocalProvider` by default and `AirLLMTranslationProvider` (with
the correct HF model id/compression) once one is added and set active. A real
OS-level click on the Translation stage tab (DPI-corrected, per §20) confirmed
AirLLM renders as a 4th Add Model tab.

---

## 25. Projected System Load Gauge & NVIDIA VRAM Fix

**What it is.** A second gauge on the Dashboard's render-estimate card,
"Projected System Load" — a genuine percent-of-VRAM-capacity reading (current
usage + this job's projected footprint, out of the device's total) — distinct
from §21's ETA gauge, which measures relative speed rather than resource
headroom. Bundled with a real bug fix: NVIDIA GPU VRAM was reading as `None`.

**Why.** User idea, following directly from the AirLLM opt-in work: *"could we
get projected load on the system with respect to the selected setting... how's
that shown visually? With an interactive bar or pie or circle??"* While
building it, the user separately reported (with a screenshot) that selecting
the dedicated NVIDIA GPU showed **"No VRAM"** for Projected Load, which is
obviously wrong for a discrete GPU.

**How it works.** `core/hardware_monitor.py`'s `estimate_eta_seconds()` /
`estimate_peak_vram_mb()` originally took a `use_airllm` flag that swapped in
AirLLM's own (much higher cost, much lower VRAM) numbers for the "translate"
stage — see §26 for how this was later generalized beyond just AirLLM.
`bridge/api.py` checked the active registry entry and threaded the flag
through both `estimate_job()` and `estimate_job_all_devices()` automatically,
so switching AirLLM on updated the estimate with no separate UI wiring needed.

**Root cause of the VRAM bug:** this NVIDIA GPU is only visible in this
environment via a Windows WMI device query (no CUDA-enabled torch build
present), and that detection path never queried VRAM size at all — it only
reported the device's *name*. **Fix:** a new `_nvidia_smi_snapshot()` static
method runs `nvidia-smi --query-gpu=name,memory.total,memory.used
--format=csv,noheader,nounits` and returns real total **and** live used VRAM
for any NVIDIA GPU with drivers installed — independent of whether torch can
actually drive it, and more accurate than Windows' own WMI `AdapterRAM`
property, which is a known-unreliable source for adapters over 4GB.

**Verified end to end:** a direct script confirmed the ETA/VRAM estimate
genuinely changed when `use_airllm` flipped (122s / `None` MB → 480s baseline;
2600MB → 3000MB on a real detected GPU). Live-launched the app: selecting the
real NVIDIA GPU and loading a test video showed the Projected Load gauge at a
genuine **44% (3640/8188 MB)** instead of the previous blank state, with the
device's real 8.0GB VRAM total now also shown in its own label.

---

## 26. Generalized Per-Model ETA/VRAM Estimation

**What it is.** Extending §25's AirLLM-specific cost override into a fully
general mechanism: the ETA/Projected Load gauges now reflect **whichever
model is actually active** for every stage, not just a flat per-stage
constant with one special case carved out for AirLLM.

**Why.** User follow-up: *"try to implement a logic that calculates eta and
projected load on the system according to selected model and attached files,
etc."* — a fair ask, since a 200MB local TTS model and an 8GB one shouldn't
project the same cost, and a cloud API call shouldn't be estimated as if it
were a local GPU workload at all.

**How it works.** `bridge/api.py`'s `_model_resource_override(entry,
base_cost, base_vram)` derives an override per pipeline stage from the
currently active registry entry:
- **AirLLM entries** (`request_preset == "airllm"`) keep using the dedicated
  `AIRLLM_TRANSLATE_COST`/`AIRLLM_TRANSLATE_VRAM_MB` constants from §25/§24.
- **Cloud/local-API entries** (`kind in ("cloud_api", "local_api")`) get a
  flat `0.3x` cost multiplier and `0` VRAM — these are network-bound calls
  with no local GPU/CPU footprint of their own.
- **Local file entries** scale proportionally against a real, already-known
  number: the actual downloaded file size (`meta.file_size_bytes`, captured
  the moment a download finishes — see `_run_local_download()`), scaled
  against a `_REFERENCE_MODEL_MB = 1024.0` baseline the flat defaults were
  originally calibrated against. A model roughly twice the reference size
  costs roughly twice as much; clamped to a `[0.2x, 5.0x]` range so a tiny or
  enormous outlier model can't produce a nonsensical estimate.

`core/hardware_monitor.py`'s `estimate_eta_seconds()`/`estimate_peak_vram_mb()`
signatures were generalized from the old single `use_airllm` boolean to
generic `stage_cost_overrides`/`stage_vram_overrides` dicts, keyed per
pipeline stage, with a straightforward `overrides.get(stage, DEFAULT)`
lookup — so AirLLM's earlier special case is now just one instance of this
general mechanism rather than a parallel code path.

**Verified:** compared resource projections across a small local model, a
large local model, and a cloud model side by side and confirmed the estimate
moved in the correct direction and magnitude for each — smaller-than-reference
models cost less, larger cost more, cloud models cost a fraction of either
with zero projected VRAM.

---

## 27. Lipsync (7th) & Profanity Filter (8th) Stage Types

**What it is.** Two additions to the model registry's `STAGE_TYPES`: `lipsync`
(Wav2Lip, previously hardcoded directly into `pipeline.py` rather than going
through the provider-resolution pattern every other stage already used) and
`profanity_filter` (a new text-moderation stage, initially registry-only).

**Why.** Wav2Lip was the last remaining stage still bypassing the
provider-abstraction pattern established for the other six (STT, Translation,
TTS, Voice, Enhancer, Filter) — an inconsistency worth closing while building
out the Marketplace further. `profanity_filter` was added ahead of the
recommended-models work in §28, which needed an 8-category target list to
populate (including "Multilingual Profanity & Curse Word Filtering" as one of
the user's requested categories). Per an explicit user instruction mid-session,
the existing `filter` stage (NudeNet-based frame scanning) displays as
**"Visual Filter"** in the Marketplace, and the new stage displays as
**"Profanity Filter"** — distinct labels for what are genuinely different
kinds of moderation operating on completely different data (video frames vs.
transcript text).

**How it works.** Lipsync follows the exact same pattern as every other stage:
`LipSyncProvider` ABC (`execute(video_path, audio_path, output_path) -> str`)
in `core/providers/base.py`; `Wav2LipLocalProvider`
(`core/providers/lipsync/wav2lip_local.py`) as a thin wrapper around the
existing `LipSyncHandler`, zero behavior change from calling it directly;
`LipSyncCloudRestProvider` (`core/providers/lipsync/cloud_rest.py`) — video +
audio multipart upload with sync/async job-polling, matching the shape already
used by the Enhancer/Filter cloud adapters; `resolve_lipsync(registry)` in
`core/providers/resolve.py`. `core/pipeline.py`'s STAGE 5 (lip sync) was
rewired from a hardcoded `LipSyncHandler()` instantiation to
`providers.resolve_lipsync(self.registry)`.

`profanity_filter` was registered as an 8th stage type in `STAGE_TYPES` at
this point but deliberately left **registry-only** — connectable/browsable in
the Marketplace, but not yet called from `pipeline.py`, since running it
requires deciding *where* in the pipeline censoring of translated text should
actually happen. That gap was closed later, in §30.

**Verified:** direct Python resolution tests confirmed `resolve_lipsync()`
returns `Wav2LipLocalProvider` by default and `LipSyncCloudRestProvider` (with
the correct `api_base_url`) once a cloud entry is added and activated; a final
check confirmed `core/pipeline.py` still imports and `ReflowPipeline()`
instantiates cleanly with the new wiring in place.

---

## 28. Curated Recommended Models

**What it is.** A hand-picked, human-curated list of specific models worth
knowing about per stage (`core/recommended_models.py`), shown as a
"Recommended" section on every Marketplace stage tab — distinct from §19's
Auto-Pick, which live-ranks *anything* on Hugging Face by download count.
Picking a recommendation opens the existing Add Model dialog prefilled, so the
user still confirms (and, for cloud entries, still supplies their own API key)
— nothing is installed or connected automatically just from being listed here.

**Why.** The user supplied a large, explicit, categorized list of specific
models and services across all 8 stages — Kokoro/Sesame CSM/XTTS v2 for TTS,
Whisper/Faster-Whisper/SeamlessM4T for STT, SeamlessM4T v2/Aya 23/NLLB-200 for
Translation, MuseTalk/LivePortrait for Lipsync, Video2X/Anime4K/Topaz for
video enhancement, RVC/F5-TTS/OpenVoice for voice cloning, Llama-Guard-3/
NudeNet for visual filtering, and toxicity classifiers/Perspective API/OpenAI
Moderation for profanity filtering — plus named cloud services (ElevenLabs,
OpenAI, DeepL, Deepgram, AssemblyAI, and others) — asking that they appear as
**recommendations users can optionally install**, framed explicitly like a
professional software installer's curated component picker.

**How it was implemented.** Every Hugging Face repo ID in the final list was
verified to **actually exist** via live calls to the real HF API before being
hardcoded — 13 repo IDs confirmed this way across the session, including
`Systran/faster-whisper-large-v3`, `facebook/seamless-m4t-v2-large`,
`CohereForAI/aya-23-8B`, `SWivid/F5-TTS`, `myshell-ai/OpenVoiceV2`,
`TMElyralab/MuseTalk`, `KwaiVGI/LivePortrait`,
`meta-llama/Llama-Guard-3-11B-Vision`, `sesame/csm-1b`, `hexgrad/Kokoro-82M`,
`coqui/XTTS-v2`, `openai/whisper-large-v3`, and
`facebook/nllb-200-distilled-600M`. Each entry is one of three `kind`s:
`local_file` (a real, verified HF repo — installs through the normal Local
Download flow), `cloud_api` (a real API base URL — `openai_tts` and
`elevenlabs_tts`/`elevenlabs_sts` use their existing named presets from §11,
everything else uses the "custom" preset rather than a guessed, unverifiable
exact request shape for a vendor's API), or `reference` (tools that aren't a
single downloadable model at all — Video2X, Anime4K, Topaz Video AI are
GitHub projects/commercial products with their own installers, shown as an
informational link rather than a fake install button).

`bridge/api.py`'s `list_recommended_models(stage_type)` exposes the data.
`Marketplace.tsx`'s new `RecommendedSection` component renders it per stage
tab; picking a `local_file` or `cloud_api` entry prefills `AddModelDialog`
(which gained `open`/`onOpenChange`/`prefill` props to support being driven
externally, alongside its existing self-contained trigger) rather than
skipping the confirmation step entirely.

Also folded into this change, per an explicit user instruction: the existing
`filter` stage's Marketplace label was changed from **"Filter"** to **"Visual
Filter"**, and the new `profanity_filter` stage (§27) was labeled
**"Profanity Filter"** — both purely UI naming, no behavior change to either
stage's underlying engine.

**Verified:** `tsc -b` and a full `vite build` both passed cleanly after the
new component, updated `StageType` union (`"lipsync" | "profanity_filter"`
added), and `CLOUD_PRESETS`/`STAGE_TABS` entries were wired in; `model_detect.py`'s
auto-detection and Auto-Pick ranking (§18/§19) were also extended with keyword
patterns and HF pipeline-tag mappings for both new stage types, so Quick Add
and Auto-pick work for them the same as every pre-existing stage.

---

## 29. First-Run Setup Wizard

**What it is.** A multi-step wizard shown once, on first launch, instead of
dropping straight into the Dashboard — experience-level selection, a review of
starting defaults, and an optional pass at queuing recommended-model downloads
from §28 — modeled on the "select/modify/deselect settings, choose components
to install" flow familiar from professional software installers.

**Why.** Directly requested alongside the recommended-models list: *"could
there also be a setup such that on the first startup of this tool... users are
asked to select/modify/deselect multiple settings of this tool including the
option to download the recommended models... like we see in professional
software installations."*

**How it works.** `core/settings.py`'s `DEFAULTS` gained
`onboarding_complete: False`. `App.tsx` checks this once, right after the
existing integrity-check boot sequence, and shows `SetupWizard` (new,
`frontend/src/components/onboarding/SetupWizard.tsx`) as a full-screen overlay
if it's still `False`. The wizard has four steps:
1. **Experience level** — Basic/Advanced/Expert, reusing the exact same
   `useExperienceLevel()` state the top-bar switcher already drives (§5), so
   the choice takes effect immediately and isn't a separate, disconnected
   setting.
2. **Starting defaults** — the same fields Settings.tsx edits later (default
   language, preserve-background-by-default, content-filter-by-default,
   auto-clean-temp), so nothing here is wizard-exclusive configuration.
3. **Recommended models** — checkboxes over §28's curated `local_file` entries
   only (cloud entries are skipped here since they need a credential the user
   would have to type mid-wizard); nothing is queued unless explicitly
   checked.
4. **Done** — confirms what was chosen; a "Skip setup" button is available on
   every step and just marks onboarding complete without changing anything.

Finishing (or skipping) sets `onboarding_complete: true` via the same
`update_settings` bridge call Settings.tsx already uses, so the wizard never
appears again, and every choice made inside it remains fully editable
afterward from Settings or the Marketplace — the wizard is a convenience
on-ramp, not a separate source of truth.

**Verified:** `tsc -b` and a full `vite build` passed cleanly with the new
component and the `onboarding_complete` field added to both the Python
`Settings` defaults and the frontend `AppSettings` TypeScript interface.

---

## 30. Per-Model Custom Instructions & Profanity-Filter Pipeline Wiring

**What it is.** A free-text "custom instructions" box, editable per connected
model directly from its Marketplace card, that gets appended to that model's
prompt — plus, as a prerequisite for it to mean anything, making
`profanity_filter` (registered but inert since §27) into a real pipeline
stage.

**Why.** User question: *"Could there also be an option to give explicit or
external commands to the pipeline?? Like if user wants translation model to
itself filter out curse words and change the output lines — is it possible
for all pluggable stages? Such that there is a type box like thing allowing
the above?"* Answered directly rather than building it for every stage
regardless of fit (the same judgment call as §24's AirLLM-scope decision):
only Translation and Profanity Filter are genuinely backed by an instructable
LLM today. STT (Whisper), Voice (RVC), Enhancer (GFPGAN), Visual Filter
(NudeNet), and Lipsync (Wav2Lip) are fixed-function models with no mechanism
to honor arbitrary text commands — a box there would either do nothing or
silently be ignored, so it wasn't built for them. Presented as an explicit
two-question design fork to the user before implementation (which stages;
per-model vs. per-render placement) — resolved as **Translation + Profanity
Filter**, **persistent per active model** (set once in the Marketplace,
applies to every render until changed).

**How it works — Translation.** Every translation provider's `translate()`
gained a `custom_instructions` parameter: the local Ollama path
(`core/llm_translator.py`) folds it into the same prompt string sent to
`/api/generate`; the cloud REST adapter
(`core/providers/translation/cloud_rest.py`) appends it to the system message
for the `openai_chat` preset, and threads it as an optional `{custom_instructions}`
template placeholder for the "custom" preset (only substituted if the user's
own body template references it); AirLLM
(`core/providers/translation/airllm_local.py`) folds it into its causal-LM
prompt template. The one honest exception: the offline **M2M100** fallback
inside `ollama_m2m100_local.py` is a plain seq2seq model with no prompt
mechanism at all, so it silently ignores the parameter — documented directly
in `TranslationProvider`'s docstring rather than left as a surprise.

**How it works — Profanity Filter.** A new `ProfanityFilterProvider` ABC
(`filter_text(text, custom_instructions="") -> str`) plus two implementations:
`OllamaProfanityFilterProvider` (local default — rewrites a line through the
same local Ollama LLM the default translation provider already talks to,
prompted to censor/rewrite rather than translate) and
`ProfanityFilterCloudRestProvider` (`openai_chat`/`custom` presets, same
pattern as every other cloud adapter). `resolve_profanity_filter(registry,
ollama_host)` in `core/providers/resolve.py` picks between them.
`core/pipeline.py` runs this stage immediately after translation, before TTS,
at all three call sites that translate text (the shared
`_transcribe_and_translate()` helper used by video_dub/audio_dub,
`process_video_gen()`'s inline STAGE 2, and `process_subtitle_translate_gen()`)
— **opt-in purely by having a model connected and activated** for that stage,
the same "on iff connected" pattern AirLLM uses (§24), so nothing changes for
anyone who hasn't touched it. A shared `_resolve_translation_and_filter()`
helper on `ReflowPipeline` resolves both providers plus their respective
`custom_instructions` together, avoiding duplicating that lookup at all three
call sites.

**How it was implemented — persistence & UI.** `core/model_registry.py`'s
entry schema gained a `custom_instructions` field (empty string by default,
harmless to set on any stage type — but only Translation and Profanity Filter
providers ever read it). `bridge/api.py`'s `set_model_instructions(model_id,
custom_instructions)` lets it be edited any time, not just at add-time, since
instructions are the kind of thing iterated on after seeing a render's actual
output. `Marketplace.tsx`'s `ModelCard` gained an `InstructionsEditor` —
collapsed to a one-line summary/prompt by default, expanding to a `Textarea`
(new shadcn-style component, `components/ui/textarea.tsx`, matching `Input`'s
existing styling) with Save/Close — shown only for Translation and Profanity
Filter model cards.

Also costed into the existing ETA/load estimator from §26:
`core/hardware_monitor.py`'s `_STAGE_COST` gained a `profanity_filter` entry,
and `bridge/api.py`'s `_active_stages()` appends it to the estimate whenever a
profanity_filter model is active — unlike the render-time toggles (lipsync,
enhance, content filter), this stage has no Dashboard checkbox of its own, so
its presence in the estimate is driven by registry state rather than a
`RenderParams` flag.

**Verified:** `python -m py_compile` across every touched Python file, `tsc -b`,
and a full `vite build` all passed cleanly. (Full runtime import verification
wasn't possible in this particular environment — its Python interpreter has no
`torch` installed, a pre-existing environment gap unrelated to this change, not
a regression it introduced.)

---

## 31. Hardware-Aware Recommendations ("Best For This Device")

**What it is.** A "Best For This Device" badge on §28's recommended-model
cards (both the Marketplace and the first-run wizard's model picker),
computed by comparing each model's typical VRAM/RAM footprint against a
one-time snapshot of this machine's actual hardware.

**Why.** A curated list is only half the job if the user still has to guess
whether a given model will actually run on their machine — this closes that
gap with a real, per-device fit check rather than a generic size label.

**How it works.** `App.tsx` calls `capture_hardware_profile()` once on first
boot (idempotent — a no-op on every later boot), which detects this
machine's default compute device (the same one `HardwareMonitor.default_device_id()`
would pick for a real render job), its VRAM, and total system RAM, persisting
them to `hardware_profile.json` (gitignored, same pattern as
`settings.json`/`models.json`) rather than re-detecting on every launch.
`core/recommended_models.py`'s `local_file` entries gained
`approx_vram_gb` — a rough, publicly-known ballpark for that model's typical
fp16 footprint, explicitly documented as a soft hint distinct from §26's real
per-model estimator (which uses actual downloaded file sizes).
`list_recommended_models()` annotates every entry with `best_for_device` via
`_fits_device()`: a dedicated GPU gets an 85%-of-VRAM headroom check;
integrated/CPU-only falls back to a much more conservative 50%-of-RAM check.

**Verified:** a real (stubbed-dependency) run of the actual bridge methods
correctly detected this machine's real CPU/RAM and labeled small models as
best-for-device and large ones (Aya 23 8B, Llama Guard 3 Vision) as not on
this machine's real hardware — then re-verified the same entries flip to
fitting when simulating a 24GB dedicated-GPU profile.

---

## 32. Help Tooltips, Confirmation Dialogs, AirLLM Wizard Step & 24-Language Translation

Four related additions shipped together, all part of the same large
follow-up feature request.

**32.1 HelpTooltip.** A "?" icon (`components/shared/HelpTooltip.tsx`, on top
of a new `components/ui/tooltip.tsx` Radix wrapper) shown next to settings
and controls with a short plain-language explanation on hover. Applied first
across `Settings.tsx`'s fields, then (in a small follow-up commit) extended
to Dashboard's stage toggles (Preserve Background / Lip Sync / Face Enhancer
/ Burn-in Subtitles / Content Filter) and its Task Priority/Texture Quality
sliders, plus Marketplace's Local Download/Cloud API/Local Service/AirLLM
source tabs. Already-descriptive inline-labeled fields (Marketplace's Add
Model inputs, which already have explanatory placeholder text and caption
paragraphs) were deliberately left alone rather than adding a redundant
tooltip next to text that's already visible. Globally toggleable from a new
Settings "00 // INTERFACE" card (`lib/use-help-tooltips.ts`) — a purely
cosmetic frontend preference in `localStorage`, the same split
`settings.py`'s own docstring already documents for theme/experience-level.

**32.2 ConfirmDialog.** `lib/use-confirm.tsx` — an imperative
`confirmAction({...})` callable from anywhere in the app, resolving
`true`/`false`. Replaces a raw browser `confirm()` on Factory Reset with the
app's own styled dialog, and adds confirmation to Settings' Reset to
Defaults, Initialize Pipeline (both Dashboard and Nodes), and the title bar's
close button (which warns specifically if a render is currently in
progress).

**32.3 AirLLM wizard step.** The first-run wizard (§29) gained an AirLLM
step: opt-in exactly like the Marketplace's own AirLLM tab (never defaulted
on), registering and activating it for Translation only if the user
explicitly enables it and fills in a model id.

**32.4 24-language support.** `core/languages.py` — one source of truth for
24 supported translation languages, replacing 3 separate hardcoded
6-language dicts in `pipeline.py` (each silently defaulting anything
unrecognized to English) and 3 separate hardcoded 8-language frontend arrays
(Dashboard, Settings, SetupWizard) that could drift from each other and from
the backend. Every language works unconditionally with the LLM-based
translation providers; the offline M2M100 fallback needs an exact id from a
fixed ~100-language vocabulary, so 4 requested languages with no exact
M2M100 match (Hinglish, Nigerian Pidgin, Western Punjabi, and Telugu — which
turned out to be genuinely absent from M2M100 entirely) are mapped to their
closest supported relative, **verified against the live, authoritative
`FAIRSEQ_LANGUAGE_CODES` list in HuggingFace transformers' own source**
rather than assumed. `bridge/api.py`'s `list_languages()` exposes it; a
module-load assertion guarantees every language has a fallback mapping, so
it can't silently regress.

---

## 33. Marketplace Card Polish & Load-Based Safety Gauges

**What it is.** Three small, related fixes bundled into one pass: an
editorial "Best" badge on Marketplace recommendations, a card-layout
alignment fix, and a green/yellow/red load-color convention applied to the
Dashboard's resource gauges with a hard block above 95% projected load.

**Why.** As more badges (Lightweight, Best For This Device, Best) started
appearing together on the same recommendation cards, uneven heights made the
grid look broken — a real visual bug, not a new feature. Separately, the
user wanted an at-a-glance danger signal on the load gauges rather than
requiring the user to read the exact percentage.

**How it works.**
- `recommended_models.py`: exactly one entry per stage now carries
  `"best": True` (an editorial top pick, independent of §31's
  hardware-fit hint — it can land on a `cloud_api` or `reference` entry
  too), surfaced as an amber "Best" badge.
- Marketplace's Recommended cards were restructured so name/badges/note/
  action each get their own row, with `flex-wrap` on badges and
  `line-clamp` on the note, plus `items-stretch` + `mt-auto` on the action
  button — fixing the uneven card heights.
- New `lib/gauge-color.ts`: a shared green (<60%) / yellow (60-85%) / red
  (≥85%) color ramp, applied to CPU LOAD, RAM LOAD, and PROJECTED LOAD
  gauges — deliberately **not** applied to the EST. TIME gauge from §21,
  whose fill means "relative speed vs. other devices" (100% = fastest),
  where red would look backwards on the best available device.
- Dashboard's Initialize Pipeline now blocks outright (via a new
  `alertOnly` mode on the shared ConfirmDialog — a single acknowledgement
  button, no bypass) when projected VRAM load is ≥95%, with a "NOT
  RECOMMENDED" overlay on the gauge itself and the button restyled red as
  an earlier visual cue before the user even clicks it.

---

## 34. Freeze-Prevention Pass

**What it is.** A dedicated hardening pass across the render path: every
subprocess call now has a timeout, ffmpeg runs at a lower OS priority, and
long-running stages with no intermediate progress get a "still working" UI
heartbeat.

**Why.** Proactive robustness work, not a user bug report — a hang in any
external process previously had no ceiling and no user-visible signal.

**How it works.**
- Every `subprocess.run()`/`check_output()` call that lacked a timeout now
  has one: `bridge/api.py`'s `_probe_duration`, `core/pipeline.py`'s 6
  ffmpeg/ffprobe calls (via a new `_run_ffmpeg()` helper),
  `audio_separator.py`'s Demucs call, `lipsync_handler.py`'s Wav2Lip call,
  `whisper_local.py`'s transcription worker, and `rvc_handler.py`/
  `Wav2Lip/inference.py`'s resample calls. `bridge/api.py`'s render loop
  already catches any exception and turns it into a visible
  `render_error`, so a timeout now surfaces as a real, actionable error
  instead of an invisible hang. `_probe_duration` specifically runs
  synchronously on whatever thread pywebview dispatches `js_api` calls on
  (unlike a render, which runs on its own thread) every time the user
  picks a video or flips a stage toggle — so a hang there previously
  risked freezing the whole UI on an everyday action, not just during a
  render.
- `core/pipeline.py`'s ffmpeg calls now run at `BELOW_NORMAL_PRIORITY_CLASS`
  on Windows, so a heavy encode doesn't starve the OS (or this app's own
  UI thread) of CPU time while it runs.
- `lib/use-render.ts` gained a "still working" heartbeat: some stages
  (Wav2Lip, Whisper, Demucs) run as one long subprocess call with only a
  single progress event at the start and nothing again until they finish
  — normal, not stuck, but indistinguishable from a frozen app with no
  feedback for minutes at a time. After 45s with no new progress/stage
  event, Dashboard and Nodes now show a small reassuring "still working"
  indicator.

**Verified for real on this machine, not stubbed:** confirmed the
`creationflags`+`timeout` combination executes correctly and that the
timeout genuinely fires on a deliberately hung subprocess.

---

## 35. Project-Local Python Environment & Minimize to System Tray

**35.1 Project-local `.venv`.** Following a mid-session redirect — after
being asked whether to delete a stale 3.76GB packaged build to reclaim disk
space, the user instead asked for "its own personal python environment"
rather than deletion — a real `.venv` was created at the project root with
`requirements.txt` actually installed (torch, transformers, pywebview,
pystray, keyring, etc.). This replaced an earlier session-long pattern of
hand-stubbing dependencies for verification, and is what made every
subsequent "launch the real app and check for real errors" verification in
this document possible, starting with §35.2 below.

**35.2 Minimize to system tray.** New `core/tray.py` wraps `pystray` in a
`TrayController` — hides the window entirely (no taskbar entry: pywebview's
WinForms backend maps `hide()`/`show()` directly to .NET `Form.Hide()`/
`Show()`, confirmed against pywebview's own source, so a hidden top-level
form genuinely has no taskbar button) with a tray icon (Show/Quit menu) to
restore it. The render thread (`bridge/api.py`'s `start_render()`) already
runs independently of window visibility, so this is purely a "get it off my
screen without losing the job" action — a new Radio icon button in the title
bar calls it via a new `minimize_to_tray` bridge method, keeping the app
running in the background the way WinRAR does.

**Real bug caught by actually launching the app (not just compiling).** The
first version attached `TrayController` directly as `bridge.tray`, which
crashed on boot with a stack overflow. Root-caused against pywebview's own
`util.py` source: pywebview auto-generates its JS-callable API surface by
recursively walking every non-callable attribute reachable from the bridge
object. `bridge.tray` was a plain object, so pywebview recursed into it, hit
`tray.window` (the live pywebview `Window`), and kept recursing into its
native WinForms/COM proxy — which returns a fresh proxy for literally any
attribute name, so the walk never terminated. **Fixed** by only ever
exposing bound methods (`tray.minimize_to_tray`, `tray.stop`) via a new
`set_tray_handlers()` setter, never the `TrayController` or `Window` object
itself — a bound method is directly callable, so pywebview registers it and
recurses no further.

**Verified by actually launching the app end to end** with the real `.venv`
dependencies: confirmed `PythonBridge`/`ReflowPipeline`/`core.tray` all
construct correctly with real torch/pywebview/pystray, reproduced the crash
with the first version, then confirmed zero recursion errors and a stable,
visible window with the fix applied.

---

## 36. Resume-Render-After-Crash

**What it is.** An offer to resume a render after Reflow Studio closes
unexpectedly mid-job.

**Why.** Previously, a crash mid-render left no trace — the next launch
looked identical to a normal cold start, with no indication anything had
been interrupted.

**How it works.** New `core/render_state.py` persists a small marker (input
path, params, template id) to `render_state.json` whenever a render starts,
cleared by every clean exit path (finish, Stop, or the render erroring out
on its own — `bridge/api.py`'s `_run_render()`'s `finally` block and
`stop_render()` both clear it). A marker still present on the next boot
means the process itself died mid-render (crash, force-kill, power loss),
not a normal shutdown — `App.tsx` checks `bridge.get_interrupted_render()`
right after the integrity check and offers to resume via the shared
ConfirmDialog from §32.2.

**Not true mid-pipeline resume** — there's no stage-level checkpointing in
`pipeline.py`; "resuming" re-runs the same job from the start with the same
input/params. Still meaningfully better than the user having no idea a job
was interrupted at all.

**Verified live:** wrote a real `render_state.json` simulating a crashed
job, launched the actual app, and confirmed the marker was read and cleared
exactly once by the real boot sequence with zero errors in the process log.

---

## 37. Dead Wav2Lip File Removal & a Real .gitignore Bug

**What it is.** Removal of Wav2Lip's own upstream training/preprocessing/
evaluation tooling that this app never calls, prompted by the user
questioning why a full training-capable ML repo was sitting in a project
whose whole point is that the Marketplace is how users select models.

**Why.** User question: *"Why does Wav2Lip exist in the folder?? I want no
extra file to be present that a user does not want and neither need... The
files that are of no use will only complicate the task of .exe creation...
right?"* — a fair question given §41's packaging work was already planned,
where every extra bundled file makes the build heavier for no benefit.

**How it was done.** Traced the actual import graph from
`core/Wav2Lip/inference.py` (the real lip-sync engine `core/pipeline.py`
calls through) to distinguish load-bearing code from dead weight. Presented
the exact findings to the user via AskUserQuestion before deleting anything,
who confirmed "Yes, delete all of it." Removed: `color_syncnet_train.py`,
`hq_wav2lip_train.py`, `wav2lip_train.py`, `preprocess.py`, `evaluation/`,
and the entire `face_detection/` Python package (`api.py`, `models.py`,
`utils.py`, `detection/` including `sfd_detector.py` and its 86MB
`s3fd.pth`) — confirmed via grep that `face_detection` was only ever
imported by the three now-deleted training/eval scripts, since this app's
actual face detection uses a plain OpenCV Haar cascade
(`face_detection/ibug/haarcascade_frontalface_alt.xml`, a data file, kept)
instead. `models/__init__.py` was trimmed to only export `Wav2Lip` (dropped
`Wav2Lip_disc_qual` and `SyncNet_color`, both training-only; deleted the
now-unused `syncnet.py`). `inference.py`, `audio.py`, `hparams.py`,
`models/wav2lip.py`+`conv.py`, and the real checkpoint were untouched.

**A separate, real bug found while investigating this.** `.gitignore`'s
unanchored `models/` pattern matched `core/Wav2Lip/models/` (real source
code — `wav2lip.py`, `conv.py`, `__init__.py`) in addition to the intended
top-level `models/` download cache, **silently excluding that source from
git entirely**. A fresh clone would have been missing the file
`inference.py` imports `Wav2Lip` from and crashed immediately. Fixed by
anchoring `models/`, `ffmpeg/`, `temp/`, and `outputs`/`output/` to the repo
root (leading `/`) so this class of collision can't recur, and re-added the
now-visible source files.

**Verified end to end with the real `.venv`, not assumed safe:** constructed
`LipSyncHandler`, called `inference.py`'s `load_model()` against the real
checkpoint, and constructed `Wav2LipLocalProvider`/`PythonBridge` — all
succeed unchanged after the cleanup.

---

## 38. HSV Accent Color Picker

**What it is.** A from-scratch HSV color picker (`components/shared/ColorPicker.tsx`
— a draggable hue ring + saturation/value square, plus a hex field for exact
entry) replacing a fixed accent color with a fully user-chosen one.

**Why.** User request for a detailed, professional-grade color customization
option rather than a small fixed palette of presets.

**How it works.** `lib/use-accent-color.ts` overrides `--primary` by setting
the CSS custom property directly on `:root` — since `--ring`,
`--accent-foreground`, and every glow shadow in the app already reference
`var(--primary)` rather than hardcoding their own color (§6's design
system), everything derived from it updates automatically with no per-
component changes needed. Persisted to `localStorage`, the same cosmetic-
preference split `settings.py`'s docstring documents. Surfaced in Settings'
"00 // INTERFACE" card alongside the help-tooltips toggle from §32.1.

**Verified:** `hexToHsv`/`hsvToHex` round-trip tested against 7 known colors
(pure red/green/blue, black, white, and both of the app's own default theme
colors) with zero mismatches.

---

## 39. Opt-In Parallel Dubbing & Nodes Graph ETA/Load Panel

**What it is.** Optional multi-segment parallel processing for the dubbing
loop, plus bringing the Nodes graph page up to parity with Dashboard's ETA/
Projected Load panel (§21/§25/§26), which it had been missing entirely.

**Why.** Rendering processes subtitle segments one at a time by default;
for videos with many short segments, running several through TTS/RVC
concurrently is a real speedup opportunity on capable hardware — but only
safely, and only when explicitly requested.

**How it works.** `core/pipeline.py`'s new `_dub_all_segments()` generator
replaces the inline per-segment dubbing loop that was previously duplicated
across `process_video_gen` and `process_audio_dub_gen` with one shared
implementation. `parallel_workers=1` (the default) is **byte-for-byte the
original sequential loop** — every other behavior is a strict superset,
opt-in only.

For `parallel_workers>1`: each segment already writes to its own uniquely-
indexed temp file, so there's no file-collision risk running them
concurrently on a `ThreadPoolExecutor`. The real shared-state risks are
handled explicitly — an `actor_lock` protects `voice_providers_by_actor`'s
lazy check-then-insert (a genuine race under concurrency), and an
`inference_lock` serializes the actual TTS/RVC model calls whenever the
device is GPU-based, since concurrent calls into one loaded model's CUDA
context aren't safe. CPU-only rendering runs the real inference calls fully
unlocked, since separate threads calling the same model in `eval`/`no_grad`
mode is standard-safe there. The final overlay onto the voice track always
happens sequentially in segment order after every future completes,
regardless of completion order, since `AudioSegment.overlay()` mutates a
shared object and is never safe to parallelize.

`bridge/api.py` threads `parallel_workers` through `_template_kwargs()` into
both templates; a new `_parallel_speedup_factor()` feeds into the ETA/VRAM
estimator (§26) so the projection actually reflects it — CPU gets a real
(diminishing-returns) speedup, GPU only a small capped one since inference
is locked, and VRAM ticks up modestly per extra worker.

`Nodes.tsx` gained the ETA/Projected Load panel it was missing (a Parallel
Workers selector, device picker, and the same relative-speed/load gauges as
Dashboard, including §33's color ramp and ≥95%-load hard block), extracted
to shared `lib/eta.ts` rather than duplicated a second time. Node reordering
and adding node instances already existed from earlier work (§17); arbitrary
new node *types* weren't added, since they'd have no real execution
semantics against the pipeline's actual sequential data dependencies —
consistent with this project's "curated templates, not freeform graph
rewiring" design principle.

**Verified for real, not just reasoned about:** a race-condition test with a
shared counter proved the GPU-kind path serializes to exactly 1 concurrent
inference call while the CPU-kind path genuinely runs 4 concurrent calls; a
separate test confirmed the generator's yield/return protocol is identical
between the sequential and parallel paths. The ETA projection was verified
at 4 workers: ~2.95x faster on CPU vs. ~1.45x on GPU, matching the different
concurrency models above. Live-launched the app with the change and
confirmed the window opens cleanly with zero errors.

---

## 40. First-Run Product Tour & Demo-Mode Replay

**What it is.** A 9-step spotlight walkthrough (Figma/Photoshop-style: a
dimmed backdrop with a cutout around the real target element, plus a
positioned callout with Back/Next/Skip) covering Dashboard's source input
and render-estimate cards, Initialize Pipeline, the experience-level
switcher, and the Marketplace/Settings nav items — plus a settings toggle to
replay it on demand.

**Why.** A natural extension of §29's setup wizard: a one-time settings
review isn't the same as seeing the actual UI in action. The user separately
asked whether the tour could be re-triggered later ("demo mode"), rather
than being a true one-time-only experience.

**How it works.** New `lib/use-tour.ts` + `components/onboarding/ProductTour.tsx`
targets real elements via new `data-tour="..."` attributes (`PrimaryNav`'s
nav buttons + experience-level switcher, Dashboard's Source Input/Render
Estimate cards and Initialize Pipeline button) rather than fragile
class-name selectors, and navigates between pages automatically when a
step's target lives elsewhere. It runs once automatically right after the
first-run `SetupWizard` finishes, gated on a **separate** `localStorage`
flag (not `onboarding_complete`), so it's independently replayable without
re-triggering the whole wizard. Per the explicit "demo mode" request, a
"Replay Tour" button was added to Settings' "00 // INTERFACE" card that
re-runs it anytime, bypassing the once-only gate.

**Verified:** `tsc -b` and a full `vite build` both pass; launched the real
app and confirmed it boots cleanly with zero runtime errors with this wired
in.

---

## 41. Native Windows/Linux/macOS Executables

**What it is.** A real, double-clickable native executable for each of the
three desktop OSes, replacing the source-launch-only `Launch_Reflow.bat`/
`LAUNCH_REFLOW.sh` scripts as the primary way to run the app.

**Why.** User request: *"Create executable for windows, linux and mac os and
replace them with the existing .bat and .sh executable."* A `.bat`/`.sh`
that shells out to a system or portable Python install is a fine dev-loop
tool, but not the packaged, "just double-click it" experience of real
desktop software.

**How it works.** `packaging/reflow.spec` builds an **onedir** PyInstaller
bundle (a folder containing the executable + its own Python runtime, not one
self-extracting file — much faster to start for a torch/transformers-sized
dependency tree) with `noarchive=True`, which keeps every bundled `.py` file
as a real, on-disk file mirroring the source tree's own relative layout
instead of packing them into a compressed in-memory archive. This matters
because roughly 9 modules in this codebase (`core/enhancer.py`,
`core/lipsync_handler.py`, `core/rvc/rvc_handler.py`, etc.) locate data files
relative to their own `__file__` — inside a compressed archive that resolves
to a synthetic, non-filesystem path and those lookups would silently break.
`packaging/build_dist.py` runs PyInstaller, then copies the large runtime
asset folders (`ffmpeg/`, `models/`, `gfpgan/`, `core/Wav2Lip/checkpoints/`)
alongside the built executable — deliberately **not** bundled as PyInstaller
`datas`, since `core/integrity.py` already owns downloading/managing them,
and duplicating multi-GB weights into every PyInstaller analysis pass would
make every rebuild far slower for no benefit. `.github/workflows/build.yml`
adds a 3-OS CI matrix (`windows-latest`/`ubuntu-latest`/`macos-latest`),
since PyInstaller **cannot cross-compile** — a Windows build has to run on
Windows, Linux on Linux, macOS on macOS. `Launch_Reflow.bat`/
`LAUNCH_REFLOW.sh` were updated to prefer the packaged build
(`dist/ReflowStudio/...`) when present, falling back to the existing
source-launch path otherwise, rather than being deleted outright — a
developer working from source still needs a way to run it.

**Three real bugs caught by actually building and launching the exe, not
just reading the spec file:**
1. **`NameError: name '__file__' is not defined` in the spec file itself.**
   PyInstaller `exec()`s `.spec` files in a namespace with no `__file__` at
   all. Fixed using PyInstaller's own injected `SPECPATH` variable instead:
   `ROOT = os.path.dirname(os.path.abspath(SPECPATH))`.
2. **`config.py`/`main.py`'s `BASE_DIR` would have resolved incorrectly
   under a frozen build.** `os.path.dirname(os.path.abspath(__file__))`
   resolves inside PyInstaller's bundle, not next to the actual `.exe` where
   the `models`/`ffmpeg`/`gfpgan` folders `build_dist.py` copies in actually
   live. Fixed proactively (before the first build attempt, based on
   PyInstaller's documented `sys.frozen` flag) with:
   `BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))` when frozen.
3. **The built exe couldn't find its own frontend.** Even with fix #2
   applied, launching the first successful build failed with `Frontend build
   not found at ...\dist\ReflowStudio\frontend\dist\index.html` — a real
   crash caught by actually running the exe and watching it fail, not by
   review. Root cause: `frontend/dist` is bundled as a PyInstaller `datas`
   entry (unlike the runtime asset folders, which are copied in separately
   by `build_dist.py`), and PyInstaller's onedir layout places `datas` under
   the bundle's `_internal/` subfolder — reachable at runtime via
   `sys._MEIPASS`, not next to the exe like `sys.executable`'s directory.
   Fixed by giving `main.py` a separate `RESOURCE_DIR` sourced from
   `sys._MEIPASS` specifically for `DIST_INDEX`, while `BASE_DIR` (from fix
   #2) stays correct for the exe-adjacent runtime asset folders. Re-verified
   by rebuilding and relaunching: the window opened correctly this time,
   confirmed via a live Win32 `EnumWindows` check finding a visible "Reflow
   Studio" window.

**Verified end to end on Windows** (the only OS available in this
environment — Linux/macOS builds rely on the CI matrix, since PyInstaller
can't cross-compile): a full build produced a working `ReflowStudio.exe`;
launched it directly (not through the source-launch scripts) and confirmed
via the Win32 check above that the real app window renders correctly.

---

## 42. Security & Robustness Hardening Pass

**What it is.** A dedicated audit pass across the codebase for common
vulnerability classes, prompted by a direct question rather than a specific
bug report.

**Why.** User question: *"Is this system fail proof, crash proof, hack
proof, safe and secure... or will you make it?? If u r going to make it then
add to the todo list."* Answered honestly first — no software is ever fully
"proof" against everything — then treated as a real, scoped hardening task:
systematically checking the classic vulnerability classes relevant to a
desktop app that downloads and runs third-party ML model files (unsafe
deserialization, path traversal, zip-slip, credential leakage, shell
injection), fixing what was actually found, and explicitly confirming
(rather than assuming) when something was already safe.

**Real vulnerabilities found and fixed:**
1. **Arbitrary code execution via a malicious lip-sync model checkpoint.**
   `torch.load()` uses `pickle` by default, which can execute arbitrary code
   during deserialization via a crafted `__reduce__` on any object in the
   pickle stream — a well-known vulnerability class for any app that loads
   downloaded ML model files. `core/Wav2Lip/inference.py`'s `load_model()`
   (the checkpoint used by the actual lip-sync stage) called `torch.load()`
   with no `weights_only` flag — PyTorch only made `weights_only=True` the
   default starting in version 2.6, and this project's pinned requirements
   predate that. **Fixed** by adding `weights_only=True`, which restricts
   unpickling to a safe allowlist (tensors + basic Python builtins).
   **Verified against the actual checkpoint file on disk**, not assumed
   compatible: loaded `core/Wav2Lip/checkpoints/Wav2Lip_GAN.pth` directly
   with `weights_only=True` and confirmed identical structure to the unsafe
   load, then ran the real `load_model()` construction path end to end and
   confirmed it succeeds unchanged.
2. **Path traversal in the Marketplace's local-download filename
   extraction.** `bridge/api.py`'s `_run_local_download()` derived the
   destination filename with `source_url.split("/")[-1]` — a crafted URL
   with backslash-based `..\` segments (e.g. ending in
   `..\..\..\Users\Public\Desktop\evil.bat`) passed through completely
   unsanitized on Windows, since `str.split("/")` never touches backslashes,
   letting a malicious "Local Download" URL write a file outside the
   intended `_downloads/<model_id>/` folder. **Reproduced the exploit
   first**, then fixed with a new `_safe_download_filename()` helper that
   splits on both separators regardless of the current OS (relevant since
   this app also targets Linux/macOS, where a lone `os.path.basename()`
   call wouldn't catch a backslash sequence either — backslash is a valid
   filename character there) and rejects anything that normalizes to empty
   or pure dots. **Re-verified** the fix blocks the exploit while legitimate
   Hugging Face URLs (including one with a `?download=true` query string)
   still extract correctly.

**Areas audited and confirmed already safe, not just assumed:**
- **Zip-slip in `core/downloader.py`'s `extract_archive()`.** Reproduced
  three exploit variants against Python 3.10's `zipfile.extractall()`
  directly (relative `../` traversal, backslash-based traversal, and an
  absolute/drive-letter path entry) and confirmed all three are already
  safely contained by the standard library's own built-in protection — no
  fix needed.
- **`core/marketplace.py`'s `install_downloaded_voice_model()`.** Its
  destination filenames come from `os.walk()`, which only ever yields bare
  filenames with no path-traversal possibility — inherently safe by
  construction.
- **`bridge/api.py`'s `_run_local_download()` destination directory.** The
  `model_id` component of the path (`os.path.join(config.MODELS_DIR,
  "_downloads", model_id)`) is a server-generated `uuid.uuid4()` from
  `core/model_registry.py`'s `add()`, never attacker-controlled — so even
  before the filename fix above, the *directory* half of that path was
  never at risk.
- **`core/credential_store.py`.** Re-read in full to confirm no plaintext
  fallback exists: `set_credential()` raises `CredentialError` if no OS
  keyring backend is available, rather than silently degrading to plaintext
  storage — matching what the credential store was originally designed to
  guarantee (§9.1).

**Not yet independently re-verified in this pass** (carried over from
earlier in the session, unchanged): shell-injection sweep across
`subprocess` call sites, and the `eval`/`exec`/`yaml.load`(unsafe)
surface — both were checked earlier in the broader session's development
and no issues were found, but weren't re-run as part of this specific
targeted pass.

---

## 43. Complete Bug/Issue Log

A flat chronological reference of every distinct bug hit during this work, for
quick lookup. (Each is also covered in context in its relevant section above.)

| # | Issue | Root Cause | Fix | How Verified |
|---|-------|-----------|-----|---------------|
| 1 | shadcn CLI wrote files into a literal `@` folder | Tool misread the `@/` path alias | Moved files to correct locations by hand | Manual inspection |
| 2 | TypeScript flagged `tsconfig.json`'s `baseUrl` as deprecated | Redundant once `paths` was also set | Removed `baseUrl`, kept `paths` | Clean `tsc` build |
| 3 | Third-party components assumed Next.js | `next/link`, `next/image`, `NodeJS.Timeout` used in a plain Vite app | Patched to `<a>`/`<img>`/`ReturnType<typeof setTimeout>` | Clean build |
| 4 | pywebview opened a loopback HTTP server | Bare filesystem path passed to `create_window()`, not a `file://` URI | `Path(...).as_uri()` | `Get-NetTCPConnection` showed zero ports |
| 5 | Maximize covered the taskbar | WinForms borderless-form `Maximized` covers the whole monitor, not just the work area | Raw Win32 `SetWindowPos` to the actual work area instead of `window.maximize()` | Direct window-bounds measurement |
| 6 | First maximize fix produced an oversized window | pywebview's logical→physical DPI scaling applied twice on already-physical values | Switched to `GetWindowRect`/`SystemParametersInfoW`, same raw pixel space throughout | Direct window-bounds measurement |
| 7 | Window launched at 1750×952 instead of 1600×900 | WinForms `AutoScaleMode.Dpi` didn't reliably honor the requested size | `_force_exact_window_size()` forces exact size via `SetWindowPos` once the window exists | Direct window-bounds measurement |
| 8 | Confusing "why is it maximized/4:3" alarm | A diagnostic test script, not the real app, was being watched | Clarified and killed the test script | N/A (miscommunication, not a code bug) |
| 9 | STANDARD/ADVANCED toggle duplicated the Nodes nav tab | Both existed to reveal the same advanced view | Decoupled into a content-density preference independent of navigation | User confirmation |
| 10 | Black borders around the whole app | Splash CSS styled `#root` directly; persisted after React replaced its children | Scoped splash styling to `.boot-splash` instead of `#root` | `getBoundingClientRect()` on TitleBar showed `x=0` after fix |
| 11 | Sidebar content silently overflowed instead of scrolling | `LogConsole`'s internal `flex-1`/`min-h-[160px]` fought the parent's `flex-1 min-h-0` | Removed internal sizing; each call site supplies its own | `clientHeight`/`scrollHeight` matched after fix |
| 12 | Download progress showed 265% | CDN gzip-compressed the response; `Content-Length` reflected the compressed size while `requests` wrote the decompressed size | `Accept-Encoding: identity` header | Real download measured exactly 100% |
| 13 | Dashboard/Settings wasted horizontal space | Narrow `mx-auto max-w-3xl` layout even in wide modes | Responsive CSS Grid rows | Screenshot at 1600×900, zero scroll needed |
| 14 | `WhisperLocalProvider` would have lost subprocess crash isolation | First draft transcribed in-process instead of shelling out to `run_stt.py` | Rewrote to shell out exactly as the original pipeline did | Caught in code review before shipping |
| 15 | Cloud REST providers crashed on "Local Service" (no-key) models | `resolve_credential()` was called unconditionally in 5 of 6 stage adapters | Made credential resolution optional everywhere, matching Translation's existing correct pattern | Real HTTP round-trip with `credential_ref=None`, confirmed no auth header sent |
| 16 | `_dub_segment()` extraction would have overlaid unmatched-length audio | First draft returned the clip regardless of the `len(clip) > 0 and target_dur > 500` check | Return `None` in that case too, matching the original's skip behavior exactly | Caught by close comparison against the original code before shipping |
| 17 | Nodes couldn't be dragged | `Nodes.tsx` never wired `onNodesChange` to `<ReactFlow>` | Rewrote around `useNodesState`/`useEdgesState` | Real OS-level mouse drag (synthetic JS events don't register - `isTrusted` can't be spoofed); before/after screenshot confirmed the node and its edge moved |
| 18 | CLONED_USER voice model couldn't be deleted | UI explicitly hid the remove button for `meta.builtin` entries | Removed the special case | Screenshot confirmed trash icon present |
| 19 | `\brvc\b` didn't match realistic filenames | Regex `\b` treats `_` as a word character, so `_RVC_` has no boundary | Custom boundary treating any non-letter as a separator | Retested against `my_custom_RVC_model.zip` |
| 20 | Cloud/local-API model adds didn't refresh other mounted tabs | `add_cloud_model`/`add_local_api_model` returned synchronously with no push event | Emit `model_installed` on success, same as the download path | Live click-through confirmed the newly added model appears |
| 21 | "Marketplace's stage tabs are broken" (false positive, §20) | Own audit test script's coordinate math, not the app: missing `devicePixelRatio` scaling on logical→physical pixel conversion, plus not accounting for Radix `Tabs` requiring `mousedown` not `click` | Fixed the test script; retracted the claim explicitly to the user | Re-tested with corrected script, tabs worked correctly |
| 22 | "Dashboard switches aren't toggling" (false positive, §20) | Reading `aria-checked` in the same `evaluate_js` call as the triggering `.click()` reads pre-render state | Re-checked in a separate call after a short delay | Confirmed both toggles had in fact worked |
| 23 | "remove all" models kept silently coming back after restart | `seed_voice_models()` auto-re-added a `CLONED_USER` entry any time the voice registry was empty | Deleted `seed_voice_models()` and its call site outright | Confirmed `models.json` stayed empty across a real restart |
| 24 | Dashboard/Nodes stage toggles could disagree with each other | Each page held its own disconnected copy of the render configuration | Shared, persisted `use-render-config.ts` store read/written by both | Toggled a switch on each page, confirmed the other page reflected it |
| 25 | Nodes page had no way to start a render at all | Initialize Pipeline control only existed on Dashboard | Added the same render status bar + Initialize Pipeline/Stop button to `Nodes.tsx`, reusing `useRenderJob()` | Selecting a video via Dashboard, then switching to Nodes, showed its button go from disabled to enabled |
| 26 | AirLLM was completely unreachable despite being fully built | Registry only understood `local_file`/`local_api`/`cloud_api` kinds; `resolve_translation()` had no `airllm` branch | Added `request_preset="airllm"` as the marker + a matching branch in `resolve_translation()` | Direct script confirmed `resolve_translation()` returns `AirLLMTranslationProvider` once one is added and activated |
| 27 | Selecting the dedicated NVIDIA GPU showed "No VRAM" | GPU only detected via Windows WMI (no CUDA torch build present), which never queried VRAM size | Added `_nvidia_smi_snapshot()` using `nvidia-smi --query-gpu=...` for real total/used VRAM | Live: Projected Load gauge showed a genuine 44% (3640/8188 MB) instead of blank |
| 28 | User asked to extend AirLLM to every stage (not a bug — a scope decision, §24) | AirLLM only supports causal-LM architectures; Whisper/XTTS/RVC are structurally incompatible | Declined, explained the technical reason directly rather than shipping a non-functional wrapper | N/A (design decision, not a code fix) |
| 29 | User asked to extend custom-instructions to every stage (not a bug — the same scope decision recurring, §30) | STT/Voice/Enhancer/Visual Filter/Lipsync are fixed-function models with no instruction mechanism | Scoped to Translation + Profanity Filter only, the two stages actually backed by an instructable LLM | N/A (design decision, not a code fix) |
| 30 | Minimize-to-tray crashed on boot with a stack overflow | `bridge.tray` was exposed as a plain object; pywebview recursively walks every non-callable attribute reachable from the bridge, and recursing into the live `Window`'s native WinForms/COM proxy never terminates | Only ever expose bound methods (`tray.minimize_to_tray`, `tray.stop`) via a `set_tray_handlers()` setter, never the `TrayController`/`Window` object itself | Real `.venv`-backed launch reproduced the crash pre-fix, confirmed zero recursion errors and a stable window post-fix |
| 31 | A crash mid-render left no trace of the interrupted job | No persisted marker of an in-progress render | `core/render_state.py` persists a marker on render start, cleared on every clean exit path; still-present marker on boot offers to resume | Wrote a real crashed-job marker, launched the app, confirmed it was read and cleared exactly once |
| 32 | A full ML training/eval repo shipped inside the app for no reason | Wav2Lip's upstream training/preprocessing/evaluation tooling was never deleted after vendoring it | Traced the real import graph from `inference.py`, deleted everything not reachable from it (training scripts, `evaluation/`, the `face_detection/` package) | Constructed `LipSyncHandler`/`Wav2LipLocalProvider` against the real checkpoint post-cleanup, confirmed unchanged behavior |
| 33 | `core/Wav2Lip/models/` (real source code) was silently excluded from git | `.gitignore`'s unanchored `models/` pattern matched *any* directory named `models`, not just the intended top-level download cache | Anchored `models/`, `ffmpeg/`, `temp/`, `outputs`/`output/` to the repo root with a leading `/` | Confirmed the previously-hidden source files became tracked and a fresh clone would no longer be missing them |
| 34 | A malicious lip-sync checkpoint could execute arbitrary code on load | `torch.load()` defaults to `pickle`-based deserialization, which can run arbitrary code via a crafted `__reduce__`; this project's pinned torch predates the 2.6 default flip to `weights_only=True` | Added `weights_only=True` to `core/Wav2Lip/inference.py`'s `load_model()` | Loaded the real `Wav2Lip_GAN.pth` checkpoint directly with the flag, confirmed identical structure and an unchanged working `load_model()` path |
| 35 | A crafted Marketplace download URL could write outside its intended folder | `_run_local_download()` only split the filename on `/`, never sanitizing backslash-based `..\` traversal sequences | New `_safe_download_filename()` splits on both separators and rejects empty/dot-only names | Reproduced the exploit pre-fix (would have escaped `_downloads/<model_id>/`), confirmed it's blocked post-fix while real HF URLs still extract correctly |
| 36 | PyInstaller spec file crashed immediately with `NameError: name '__file__' is not defined` | `.spec` files are `exec()`'d in a namespace with no `__file__` | Used PyInstaller's own injected `SPECPATH` variable instead | Build proceeded past Analysis once fixed |
| 37 | The built `.exe` couldn't find its own frontend bundle | `frontend/dist` is a PyInstaller `datas` entry, which lands under the onedir build's `_internal/` (`sys._MEIPASS`) — not next to the exe like the separately-copied runtime asset folders (`sys.executable`'s directory) | Gave `main.py` a separate `RESOURCE_DIR` sourced from `sys._MEIPASS` specifically for locating `frontend/dist/index.html` | Built exe failed to find `index.html` pre-fix (caught by actually launching it); a real visible "Reflow Studio" window confirmed via Win32 `EnumWindows` post-fix |

---

## 44. Disk Space Breakdown

Measured directly on this machine (`Get-ChildItem -Recurse | Measure-Object -Sum Length`),
not estimated — prompted by the user asking why the project folder had grown
to several gigabytes.

| Folder | Size | What it is | Tracked in git? |
|---|---|---|---|
| `dist/` | 3.96 GB | §41's PyInstaller onedir build output (`ReflowStudio.exe` + `_internal/` runtime + copied assets) | No — regenerated on demand, gitignored |
| `build/` | 3.90 GB | Legacy `build/windows-portable/` vendored Python runtime, kept per an earlier explicit user decision (a `.venv` was added alongside it instead of deleting it) | No — gitignored |
| `models/` | 1.93 GB | Downloaded ML weights (`xtts/` 1.79 GB, `rvc/` 181 MB, `translation/` 5.8 MB; `demucs/`, `musetalk/`, `uvr/`, `wav2lip/` currently empty — not yet downloaded on this machine) | No — gitignored, managed by `core/integrity.py` |
| `.venv/` | 1.65 GB | §35.1's project-local Python environment (torch, transformers, pywebview, etc.) | No — gitignored |
| `.git/` | 1.01 GB | Full commit history | N/A (this *is* the repository) |
| `gfpgan/` | 0.51 GB | Face-enhancement model weights | No — gitignored |
| `core/Wav2Lip/checkpoints/` | 0.41 GB | The real Wav2Lip/SFD checkpoints (survivors of §37's dead-file cleanup) | No — gitignored |
| `ffmpeg/` | 0.19 GB | Bundled ffmpeg binary | No — gitignored |
| `frontend/node_modules/` | 0.15 GB | Frontend build dependencies | No — gitignored |
| **Total project folder** | **13.72 GB** | | |

**What this means practically:**
- Everything gitignored above (`dist/`, `build/`, `models/`, `.venv/`, `gfpgan/`,
  `core/Wav2Lip/checkpoints/`, `ffmpeg/`, `frontend/node_modules/` — 11.75 GB,
  ~86% of the total) is either regenerated on demand or downloaded by
  `core/integrity.py`/`npm install` on first run. **A fresh `git clone` of this
  repository is nowhere near 13.72 GB** — it's just source code plus `.git`
  history.
- `build/windows-portable/` (3.90 GB) is the single largest reclaimable chunk
  if disk space becomes a concern later — it predates the `.venv` this session
  set up and is no longer the primary way to run the app from source
  (`Launch_Reflow.bat` already prefers a real venv/system Python, and now
  prefers §41's packaged `dist/ReflowStudio/` build over either). It was
  deliberately **not** deleted in this session per the user's explicit
  redirect at the time ("What I want for the tool is that it should have its
  own personal python environment"), which asked for a proper dev
  environment rather than removal of the existing portable build.
- `dist/` (3.96 GB) will regrow every time `packaging/build_dist.py` is
  re-run — this is expected and by design (§41), not a leak.

---

## 45. Packaged exe Icon & a Real Windows Installer

**45.1 App icon.** The packaged `ReflowStudio.exe` used PyInstaller's default
icon until this point. Fixed by converting `assets/icon.png` (the app's real
brand mark) into a proper multi-resolution `assets/icon.ico` via Pillow —
Windows exe icon resources need real `.ico` format, a plain PNG isn't
accepted — and wiring it into `packaging/reflow.spec`'s `EXE(icon=...)`,
Windows-only (a no-op on Linux/macOS, which don't use exe icon resources the
same way). **Verified** the icon is genuinely embedded, not just
configured: `ExtractIconExW` against the rebuilt exe returned real non-null
icon handles, and the app still launched correctly afterward.

**45.2 Windows installer.** User request: *"Could you now build an installer
for the dist/ReflowStudio?? Using the installer InstallBuilder??"* — followed
up after their own attempt at using the InstallBuilder Enterprise GUI got
stuck at a black screen. Built via `builder-cli.exe` (the command-line
builder) instead of the GUI — sidesteps whatever caused the GUI to hang,
since the CLI needs no display session and builds straight from an XML
project file non-interactively.

New `packaging/installbuilder/reflow-installer.xml` packages the entire
`dist/ReflowStudio/` build (see §41) into a normal Windows installer:
Program Files copy, Start Menu + Desktop shortcuts pointing at
`ReflowStudio.exe` (using the app's own icon from §45.1), an "Uninstall"
shortcut, and an auto-generated uninstaller — everything a user expects
from double-clicking a `setup.exe`, none of which `dist/ReflowStudio/`
alone (just a folder to run in place) provided.

**Issues faced — iterated against `builder-cli`'s own real schema-validation
errors, not guessed:**
- `<allowMultipleInstances>` and a `<shortcut>`-level
  `<windowsWorkingDirectory>` tag aren't valid elements in this
  InstallBuilder version — both removed after the builder's own error
  messages named them directly.
- `<installerFilename>` referencing `${platform_log_name}`/`${version}`
  failed with "unknown variable" — neither is a real built-in InstallBuilder
  variable; replaced with a literal filename.

**Verified:** a full build produced a real ~2.9GB
`ReflowStudio-1.0.0-Setup.exe` — confirmed as a genuine Windows PE
executable (`MZ` header) rather than just trusting the builder's own
"success" output. Actually *running* the installed result wasn't verified
in-session, since it requires a real UAC elevation click-through
(`requestedExecutionLevel=requireAdministrator`) a human has to approve, and
running it unattended would make real, hard-to-reverse changes (Program
Files, registry, Desktop) to the user's machine without them watching — left
for the user to confirm directly.

---

## 46. Real Local-File Inference: STT, Translation, TTS, Profanity Filter

**What it is.** The first phase of a much larger fix: making the
Marketplace's `local_file` connections for STT, Translation, TTS, and
Profanity Filter *actually run the model the user connected*, instead of
silently continuing to use the hardcoded default engine no matter what was
marked "active".

**Why.** User request, after the earlier "run these 3 sample videos through
your exact Marketplace picks" ask: *"So do I need to compile this folder...
everything works??"* Investigating that question surfaced two real,
previously-unknown problems, not one:

1. **The download itself was broken for whole-repo links.**
   `core/downloader.py`'s `download_with_progress()` only ever did a raw
   single-file HTTP GET — correct for a direct `/resolve/` link, but a bare
   HF repo-root URL (`https://huggingface.co/<org>/<repo>`, what every
   `recommended_models.py` entry actually uses) just downloaded that page's
   **HTML** (~150-350KB) and silently marked the "model" installed. Found
   by inspecting what a real Marketplace download had actually produced —
   Faster-Whisper, NLLB-200, XTTS v2, Llama Guard 3 Vision, and MuseTalk had
   all "installed" a webpage, not weights.
2. **Even with real weights, most stages had nowhere to load them into.**
   `core/providers/resolve.py` only ever branched on `cloud_api`/`local_api`
   kind (plus one special-cased AirLLM translation entry) — a connected and
   *activated* `local_file` model for STT/Translation/TTS/Profanity Filter
   was completely cosmetic; the pipeline kept silently using the hardcoded
   local engine regardless.

**How it works — the download fix.** `core/downloader.py` gained
`hf_repo_id_for_url()` (detects a bare HF repo-root URL) and
`_download_hf_snapshot()`, which routes those through
`huggingface_hub.snapshot_download()` (real multi-file fetching) instead.
`snapshot_download()` is blocking with no simple progress callback, so it
runs on a background thread while the generator polls the destination
directory's on-disk size to synthesize the same live speed/ETA progress-dict
shape the single-file path already produced — a real rolling-window
calculation, not a cumulative average (an average silently under-reports
speed for the rest of a download after any single slow patch, caught by
watching it happen on a real download before fixing it).
`bridge/api.py`'s `_run_local_download()` was updated to compute
`file_size_bytes` correctly for a directory result too (`os.path.getsize()`
on a directory doesn't raise on Windows, but returns a meaningless number).

**How it works — the inference wiring.**
- **STT:** faster-whisper's `WhisperModel()` already accepts a local
  CTranslate2 model directory in place of a named size string (confirmed
  against the installed package's own docstring, not assumed) — a
  downloaded `Systran/faster-whisper-*` repo just works once
  `resolve_stt()` passes the entry's `local_path` through, no new provider
  code needed.
- **Translation:** new `NLLBLocalProvider`
  (`core/providers/translation/nllb_local.py`) loads a downloaded NLLB-200
  repo via `transformers`' `AutoModelForSeq2SeqLM`, using a new
  `NLLB_LANG_MAP` (`core/languages.py`) of real FLORES-200 codes — NLLB's
  vocabulary is large enough to genuinely cover 3 of the 4 languages the
  M2M100 fallback (§32.4) had to approximate (Nigerian Pidgin, Western
  Punjabi, Telugu all have real dedicated codes). Validated against the
  actually-loaded tokenizer at call time, not just trusted from the
  hardcoded table.
- **TTS:** `TTSHandler` gained a `model_path` override (falls back to the
  bundled default XTTS checkpoint when absent) so `XTTSLocalProvider` can
  point it at a downloaded `coqui/XTTS-v2`-compatible repo instead.
- **Profanity Filter:** new `ClassifierProfanityFilterProvider`
  (`core/providers/profanity_filter/classifier_local.py`) for a downloaded
  sequence-classifier repo. A classifier can only *score* text, not rewrite
  it the way the Ollama LLM default can — "filtering" here means replacing
  a line scored toxic with a fixed placeholder, the closest honest
  equivalent to broadcast media bleeping a whole line it can't cleanly edit.

**A real, separate robustness bug found while verifying all of this — not
fixed once, but everywhere it applied.** `from_pretrained()` attempts a
network freshness/etag check by default *even for an already-downloaded
local directory* — observed hanging for 15+ minutes on a slow connection
during testing, with no reason to touch the network at all for a model
that's already fully on disk. Fixed with `local_files_only=True` across
every affected call site: `NLLBLocalProvider`, `ClassifierProfanityFilterProvider`,
faster-whisper's local-path loading in `core/stt/stt_handler.py`, and later
(§49) MuseTalk's own `WhisperModel.from_pretrained()`/`AutoencoderKL.from_pretrained()`
calls once the same symptom showed up there too.

**Verified end to end, not just per-provider:** each new provider was
individually smoke-tested first (real transcription, real Hindi
translation output, real synthesized audio, real toxic-line censoring on
deliberately-clean and deliberately-toxic test strings), then all three
Sample videos were actually rendered through the full pipeline using these
real engines — genuine Hindi dialogue and genuine profanity-filter hits
(`[line removed by profanity filter]`) appeared in the render logs, not
placeholder output.

---

## 47. CPU-Feasible Visual Filter (Falconsai) & a Marketplace Plumbing Gap

**What it is.** A second, genuinely usable Marketplace option for the
Visual Filter stage, added because the only prior `local_file`
recommendation for it — Llama Guard 3 Vision — turned out to be
unusable on this machine regardless of how correctly it was wired.

**Why.** Direct question: *"If llama guard cannot work on my system can't u
add more recommendations??"* Llama Guard 3 Vision is an 11B-parameter
vision-language model (~42.6GB download) needing a real GPU with 22GB+
VRAM — this machine's captured hardware profile is CPU-only with 15.6GB RAM,
so it can't even hold the weights, let alone run inference.

**How it works.** New `VisionClassifierLocalProvider`
(`core/providers/filter/vision_classifier_local.py`) wraps a lightweight ViT
NSFW image classifier (`Falconsai/nsfw_image_detection`, ~1.5GB, real CPU
inference verified) as a Marketplace option, resolved via a
`request_preset="image_classifier"` marker (same pattern AirLLM uses for
translation — see §24). Unlike NudeNet (a real detector returning bounding
boxes), a plain classifier only scores the *whole frame* safe/unsafe —
flagged frames get a full-frame blur rather than a localized one, the same
whole-thing-censored tradeoff already established for the profanity-filter
classifier (§46).

**A real, separate gap found while wiring this in.** The Marketplace's
per-stage Add Model dialog never threaded `request_preset` through for
`local_file` entries at all — `add_local_model()` only ever accepted
`stage_type`/`source_url`/`display_name`; only the cloud/local-API add flows
carried a preset. A recommendation like this one (which needs
`request_preset="image_classifier"` to route to the right provider) would
have had that marker silently dropped the instant a real user clicked it
through the UI, even though the dialog looked correctly pre-filled. Threaded
through end to end: `bridge/api.py`'s `add_local_model()`, `frontend/src/lib/api.ts`,
`use-marketplace.ts`'s `addLocal()`, and `Marketplace.tsx`'s local-tab
prefill state (a new `localPreset` piece of state, mirroring the pattern
`cloudPreset` already used).

**Verified:** a direct smoke test constructed the provider against a real
downloaded Falconsai checkpoint, confirmed its `id2label` resolution
correctly found index 1 as `"nsfw"`, and ran real inference against a
synthetic test frame. `tsc -b`/`vite build` both passed cleanly after the
frontend plumbing change.

---

## 48. F5-TTS: Real Zero-Shot Voice Cloning

**What it is.** A real, working F5-TTS voice provider — zero-shot
voice-cloning TTS via the `f5-tts` PyPI package's own `F5TTS` API,
distinct from RVC-style audio-to-audio conversion.

**Why.** Part of the same "make everything actually work" push as §46/§47 —
F5-TTS was already a recommended Marketplace entry, but like Llama Guard and
MuseTalk, connecting it did nothing.

**How it works — a real architectural mismatch, not a simple wiring gap.**
F5-TTS needs the *target text* and a *reference audio clip* to clone from;
it's a complete text-to-cloned-speech generator, not a post-processor over
an already-synthesized clip the way `VoiceProvider`'s only prior
implementation (RVC) is. `VoiceProvider.convert()` (`core/providers/base.py`)
gained optional `text`/`reference_audio` parameters that RVC-style providers
simply ignore — additive, not a behavior change for them. `core/pipeline.py`'s
`_dub_segment()` checks the resolved cast member's registry entry directly
(`request_preset == "f5tts"`, the same marker pattern AirLLM/the image
classifier use) and, when it matches, **skips the XTTS synthesis step
entirely**, cloning straight from the same reference audio the
`CLONED_USER` path already uses — there's no separate per-actor audio
sample in this pipeline's cast-list design, so "F5-TTS as a cast member"
means "clone the original speaker via F5-TTS instead of XTTS," not a
different target voice.

**A real, measured cost, not a bug.** Verified with a real generated wav —
but generating two short sentences took **~8 minutes on this CPU**.
F5-TTS's flow-matching architecture (an iterative diffusion-style solver,
`nfe_step=32` denoising steps by default) is fundamentally heavier than
XTTS's single-pass autoregressive approach. Documented directly in the
Marketplace entry's own note rather than left as a surprise, the same way
AirLLM's "slow, layer-streamed from disk" tradeoff is already documented.

**Verified:** a direct smoke test ran real `F5TTSVoiceProvider.convert()`
against a real reference clip, producing a genuine, playable generated wav
file.

---

## 49. MuseTalk: Vendoring a Second Lip-Sync Engine

**What it is.** A second, real, fully-working lip-sync engine — MuseTalk
(TMElyralab), vendored into `core/MuseTalk/` the same way Wav2Lip was
originally vendored, and wrapped in `MuseTalkLocalProvider`
(`core/providers/lipsync/musetalk_local.py`).

**Why.** Same "make everything work" push — MuseTalk was already a
recommended Marketplace entry (§28) but, like Llama Guard and F5-TTS before
this session's fixes, connecting it did nothing at all.

**How it works.** Shells out to a subprocess the same way `LipSyncHandler`
already does for Wav2Lip (`core/lipsync_handler.py`) — isolates MuseTalk's
own process from this app's main one, same crash/timeout isolation
reasoning already established there.

**The real blocker: mmpose/DWPose vs. this project's torch version.**
Upstream MuseTalk depends on `mmpose` for 68-point face-landmark detection,
but `mmcv` (mmpose's own hard dependency) only ships prebuilt wheels up to
torch ~2.1-2.2 — OpenMMLab's releases lag PyTorch by a long margin, and this
project runs torch 2.13. Installing or compiling a compatible `mmcv` would
mean downgrading torch project-wide, risking every other model wired this
session (XTTS, NLLB, faster-whisper, AirLLM, F5-TTS). Swapped for the real
`face-alignment` PyPI package instead (SFD-based, pure PyTorch, no `mmcv`)
— it predicts the same standard 68-point 2D landmark scheme DWPose's
face-region slice approximates, so the downstream crop-refinement math is
unchanged; only the landmark *source* differs (documented directly in
`core/MuseTalk/musetalk/utils/preprocessing.py`'s patch header).

**9 real bugs found and fixed getting from "vendored" to "produces a real,
correct output video" — each found by actually running it and reading the
actual error, never assumed:**
1. `ModuleNotFoundError` running `scripts/inference.py` directly instead of
   as `-m scripts.inference` — the `musetalk` package wasn't on `sys.path`
   otherwise, since the script lives one directory below where the package
   itself sits.
2. `face-alignment` 1.5.0 renamed `LandmarksType._2D` → `TWO_D`.
3. `subprocess.run(text=True)` with no explicit encoding decodes captured
   output using this machine's `cp1252` default, which can't decode real
   bytes MuseTalk's own output produces — fixed here and in
   `core/lipsync_handler.py`'s pre-existing identical pattern before it had
   a chance to hit the same crash for real.
4. `torch.compile` silently succeeds once (falls back to eager mode) but
   fails *uncaught* on a later call mid-run, since this machine has no MSVC
   (`cl.exe`) — disabled compilation outright rather than rely on
   inconsistent fallback behavior.
5. `resnet18-5c106cde.pth` and `79999_iter.pth` (the face-parsing
   backbone/model, well-known pretrained checkpoints re-hosted on HF) are
   legacy pre-2019 `.tar`-format `torch.save` files — PyTorch 2.6+'s
   `weights_only=True` default can't load that format **at all**, not even
   with an allowlist, unlike the modern-format checkpoint
   `core/Wav2Lip/inference.py` already handles (§42). `weights_only=False`
   is the only way to load this specific well-known, trusted file format.
6. `os.system()` ffmpeg calls with unquoted paths — this project's own root
   path (`"Reflow Studio"`) contains a space, silently truncating arguments
   and making ffmpeg fail to find its input entirely.
7. `face_alignment`'s `return_bboxes=True` appends a 5th (confidence-score)
   element upstream's bbox-consuming code never expected.
8. That same bbox needed converting to a plain tuple of real ints, not left
   as a numpy array of floats — broke a later `== coord_placeholder`
   equality check (`ndarray == tuple` returns an elementwise bool array;
   `if` on that raises "truth value... is ambiguous") and `cv2.resize()`'s
   `dsize` argument respectively.
9. **A real index-misalignment bug in MuseTalk's own reference pipeline**,
   not something this session introduced: frames where no face was detected
   get skipped when building encoded latents, but the frame/coordinate
   lists used later for reassembling the output video were never filtered
   the same way — once any frame was skipped, every frame after it got
   paired with the wrong bounding box via modulo-cycled indexing into a
   longer, unfiltered list. Fixed by filtering both lists consistently
   before building the cycled versions used for reassembly.

**Verified end to end with a real generated output video** (correct
duration, both video and audio streams present) — and, once the pipeline
integration surfaced a follow-up question about visual quality, verified
again with real frame-by-frame inspection of a proper talking-head test
clip (genuine mouth-shape variation and body/background motion across
frames, not a stuck/repeated frame).

**Where this fits practically — see §53.** MuseTalk targets 30+ FPS on a
real GPU; on this CPU-only machine it measured roughly **1.75 minutes of
processing per second of video**. It's real and it works, but it is not the
practical default for anyone without a GPU.

---

## 50. Windows Console UTF-8 Crash & an OpenCV 5.0 Regression

**50.1 UTF-8 crash.** Several handlers (TTS, Vision/NudeNet, Wav2Lip's
worker) print emoji status lines. This machine's console codepage is
`cp1252` (confirmed directly, not assumed) — a plain `print()` of any of
them raised `UnicodeEncodeError` and crashed whatever was running. Hit for
real during the first attempt at an actual full render (STT, TTS, and
Vision all crashed on first output). Fixed at the source: `main.py`
reconfigures its own stdio to UTF-8 and sets `PYTHONIOENCODING`/`PYTHONUTF8`
in the environment so every subprocess it spawns (`core/run_stt.py`,
`python -m demucs`, MuseTalk's subprocess, etc. — all inherit `os.environ`)
starts up already in UTF-8 mode. `core/run_stt.py` also reconfigures
directly, in case it's ever invoked standalone.

**50.2 OpenCV 5.0 regression.** A real, separate bug found only once a full
render finally reached the lip-sync stage: `AttributeError: module 'cv2' has
no attribute 'CascadeClassifier'`. OpenCV 5.0 (the current PyPI default as
of this session) **removed `CascadeClassifier` from its Python bindings
entirely** — a real breaking API change, not a packaging mistake — silently
breaking Wav2Lip's face detection on every single render, only surfacing
deep into the lip-sync stage rather than at install time.
`requirements.txt` pins `opencv-python-headless<5` to stay on the last
API-compatible major version — `opencv-python-headless` specifically, not
`opencv-python`, since this is a backend pipeline with no GUI `cv2` calls
anywhere in it, and having both packages installed side by side corrupts
the shared `cv2` install (they ship overlapping files under the same import
name) — found by hitting exactly that corruption for real before narrowing
to the headless-only fix.

**Also found in the same pass: `requirements.txt` was missing STT/TTS/
separation/filter dependencies entirely.** `faster-whisper`, the actual
`TTS` import (`coqui-tts`, since the original archived `TTS` package needs a
C++ compiler this machine doesn't have — see §35.1's `.venv` setup),
`demucs`, and `nudenet` were all hard imports with nothing declaring them —
a plain `pip install -r requirements.txt` never actually produced a working
STT/TTS/separation/filter stage. Each was found by installing into a clean
environment and hitting the real `ModuleNotFoundError` in turn, then
chasing each dependency's own real version-compatibility errors
(`coqui-tts` needs `transformers<5` and `torchcodec`, both discovered the
same way).

---

## 51. Settings Page Black Screen (a Real Rules-of-Hooks Bug)

**What it is.** A real React "Rules of Hooks" violation that crashed the
Settings page to a blank/black screen every time it was opened.

**Why it happened.** User report: *"There is a bug on opening the settings
page.. the window goes black."* `SettingsPage` called
`useHelpTooltipsEnabled()`/`useAccentColor()` **after** a conditional
`if (!values) return <Loading/>` early return. `values` starts `null` and
only populates once an async `bridge.getSettings()` call resolves — so the
very first render skipped both hooks entirely, while every later render
included them. That's a hook-count mismatch across renders, which React
detects and throws a hard error for, crashing the page's whole render tree
with nothing left on screen but the app's dark background.

**Fix.** Moved both hooks above the early return, so they run
unconditionally on every render as React's Rules of Hooks require.

**Verified beyond the one fix.** A background audit swept every other
page/component under `frontend/src` for the same pattern — a conditional
early return before a hook call, or a hook called inside a conditional
block — and confirmed this was the only real instance; every other
early-return in the codebase already occurs *after* that component's own
hooks have run, or occurs in a genuinely separate component with its own
independent hooks (the chart-library components' outer/inner-component
split, for example). `tsc -b`/`vite build` both passed cleanly after the
fix.

---

## 52. Dub Audio Overlap & Background Bleed-Through

**What it is.** Two real, independent audio bugs, both reported directly
after watching a real rendered output: *"the bbc video had both the
original narration and the hindi dub narration all out of order... and the
lipsync was bad."*

**Bug 1 — segments overlapping each other.** `core/pipeline.py`'s
`_dub_segment()` capped the speed-up applied to an over-long translated
line at 1.5x, to avoid unnaturally fast/chipmunked speech — but a line
still longer than its target duration even after that cap (routine: Hindi
commonly runs longer than the English/source phrase it translates)
previously overlaid straight into the **next** segment's start time, since
`AudioSegment.overlay()` only adds audio, it never shifts anything out of
the way. Two lines audibly playing at once is exactly "out of order."
Fixed in two passes:
- First pass: hard-trim to the segment's own nominal `target_dur`.
- **Caught as a real regression by the user's own follow-up feedback**
  before it shipped as final: an instant hard cut chops a sentence off
  mid-word, which sounds just as bad as the overlap it replaced. Second
  pass: `_dub_segment()` now takes `next_start` (the *following* segment's
  real start time, threaded through `_dub_all_segments()` in both the
  sequential and parallel code paths) and only trims down to whichever is
  more generous — the segment's own `target_dur`, or the actual gap before
  the next segment begins, since there's very often real silence between
  sentences a translated line can use first. The trim itself now fades out
  over 80ms instead of cutting instantly.

**Bug 2 — original narration bleeding through under the new dub.**
`core/audio_utils.py`'s `dynamic_mix()` applied a single flat gain
reduction across the **entire** background track — exactly what its own
code comment already flagged as a placeholder ("a simpler Global Duck
approach... for stability", not true side-chaining). "Keep background"
isn't pure music/ambience; it's whatever Demucs' vocal-separation model
didn't classify as vocals, which for narration-style content (a documentary
presenter over street noise, not a singer over a mix) routinely still
contains an audible, imperfectly-removed trace of the *original*
narration. A flat reduction wasn't enough to mask that residue specifically
during the moments the new dub is also speaking. Implemented real per-range
ducking: `detect_nonsilent()` finds the new voice track's actual speech
ranges, and the background gets pushed dramatically further down
(`active_ducking_db`, -24dB default) only during those ranges, staying
closer to its natural level everywhere else.

**Verified:** a full real render of the flagged video (`Sample/2.mp4`, a
BBC documentary clip) completed end to end with both fixes applied and
Wav2Lip active (see §53) — correct duration, all three streams present.
Audio quality itself can't be verified by this session directly (no audio
playback capability) — the fixes address the two specific, concrete
mechanisms the user described, verified by reading the actual code paths
that produced them, not by guessing.

---

## 53. Practical Hardware-Aware Defaults, Not Just "It Technically Works"

**What it is.** A direct course-correction after the user pointed out that
a "technically working" 3-hour render isn't actually usable: *"why does it
take 3 hrs?? What's the help of this tool then if a user waits this
long?? ... give me a proper any-system-workable system.. and works on low
end devices efficiently."*

**The honest answer.** MuseTalk (§49) is real and produces correct output —
but it's built for 30+ FPS on a real GPU. Run on this CPU-only machine
without any GPU acceleration, it measured roughly 1.75 minutes of
processing per second of video — a ~100 second video would take
**roughly 3 hours**. That's a property of running a GPU-oriented
latent-diffusion model on CPU-only hardware, not a flaw specific to this
app's implementation of it — but shipping it as the *active default*
regardless of hardware was the real mistake, not the engine's existence.

**Fix.** The Marketplace's active lipsync selection was cleared back to
unset (`models.json`'s `"lipsync"` active slot set to `null`), which falls
through `resolve_lipsync()`'s existing default path to **Wav2Lip** — this
app's original lip-sync engine, architecturally much lighter (a GAN, not a
latent-diffusion UNet+VAE pipeline) and the thing that actually powered
every fast, successful render earlier in this session. MuseTalk stays fully
wired and connectable (§49's work isn't wasted — it's real, tested, and
available), just no longer auto-selected without a GPU to justify it.

**Verified with a real, complete render:** `Sample/2.mp4` (the video the
user specifically flagged), re-rendered with Wav2Lip active and both audio
fixes from §52 applied, completed in **39 minutes** (down from an estimated
~3.6 hours with MuseTalk) — a real, valid output video with correct
duration and all three streams present.

---

## 54. Recommended Models List Expanded ~2.5x

**What it is.** `core/recommended_models.py`'s curated per-stage
recommendation list grown from 34 entries to 84 — roughly 2.5x, short of the
user's requested 3-4x only where genuinely real, verifiable options ran out
(voice conversion and lip-sync specifically have far fewer well-known named
models/services than, say, TTS or translation).

**Why.** Directly requested alongside the visual-filter question in §47:
*"can u add more recommendations?? Such that it makes it easier for the
user to just select download and run it?"*

**How it was implemented — held to the exact same verification standard
the original list was built under.** Every candidate `local_file` repo ID
was checked against the real, live Hugging Face API (`HfApi().model_info()`)
before being added — several plausible-sounding candidates (`coqui/YourTTS`,
`sczhou/CodeFormer`, `TencentARC/GFPGAN`, `OpenTalker/SadTalker`, and
others) turned out not to exist under that exact path and were dropped
rather than guessed at or swapped for a lower-quality community fork.
Real additions include: Piper, MeloTTS, SpeechT5, Parler-TTS, and Fish
Speech for TTS; Whisper large-v3-turbo, Distil-Whisper, Canary, and MMS for
STT; MADLAD-400, mBART-50, and TowerInstruct for Translation; the original
RVC WebUI's own repo and SpeechT5's voice-conversion checkpoint for Voice;
Swin2SR for the Enhancer; two more NSFW classifiers plus Azure/Sightengine
cloud options for the Visual Filter; SadTalker and ByteDance's LatentSync
for Lipsync; and three more toxicity classifiers plus Azure/Amazon cloud
options for the Profanity Filter.

**Issue faced — a real bug caught by writing a verification script rather
than trusting the data by eye.** The Marketplace's "Best" badge convention
requires exactly one `"best": True` entry per stage; the expansion pass
introduced 3 separate stages with two "best" entries each (one was actually
a **pre-existing** bug from when Falconsai was added in §47 without
removing the Visual Filter stage's previous "best" flag). Caught by a
direct assertion script (`len(bests) == 1` per stage) run against the real
module before committing, not by re-reading 84 entries by eye.

**Verified:** a direct script imported the real module and checked every
entry for required fields matching its declared `kind`, no duplicate names
within a stage, and exactly one `"best"` per stage — all passed cleanly
after the two bugs above were fixed.

---

## 55. TTS Silently Producing Zero Audio — the Torchcodec/FFmpeg DLL Bug

**What it is.** After §52's audio-overlap/bleed-through fixes, a fresh
verification render of `Sample/2.mp4` was kicked off to give real evidence
(not just an assertion) that the dub had actually improved. The render
completed end-to-end and reported `100% COMPLETE` in ~20 minutes — but
inspecting the actual log line-by-line found `[TTS] ❌ Generation Failed:
Could not load libtorchcodec` on **all 39/39 dubbed segments**. The pipeline
never surfaced this: `core/tts/tts_handler.py`'s `generate_audio()` catches
generation exceptions, prints them, and returns — it doesn't raise, so
nothing downstream ever learns a segment has no audio. The render that
"passed" almost certainly had little to no real Hindi dub in it at all,
which is a materially different (and worse) problem than the overlap/
bleed-through bugs fixed in §52.

**Why it happened.** `requirements.txt` already had a partial writeup of
this exact failure mode from earlier in the session (added when `torchcodec`
was first pinned in as a dependency): coqui-tts, under `torch>=2.9`, uses
torchcodec for audio IO, and torchcodec needs real FFmpeg *shared* libraries
(`avcodec-*.dll` etc.) loadable at runtime. This project's bundled
`ffmpeg/bin/ffmpeg.exe` (from gyan.dev's `essentials_build`) is a
`--enable-static` build with no such DLLs. The comment even said so —
but ended with "Not yet fixed in packaging/build_dist.py," i.e. the gap
had been identified and then never actually closed. It stayed invisible
because nothing during the F5-TTS/MuseTalk/recommended-models work in
§48–§54 happened to trigger real TTS generation on this exact code path
after the note was written.

**How it was actually root-caused.** Reproduced directly:
`python -c "import torchcodec"` raised the same `RuntimeError`, with a
diagnostic message listing attempted DLL loads for FFmpeg versions 4–8, all
failing with `FileNotFoundError` on `libtorchcodec_core{N}.dll`. Downloaded
a real `ffmpeg-release-full-shared` build (gyan.dev) and tried three
increasingly specific fixes, each disproven or proven with an actual load
attempt rather than assumed:
1. Appending the shared-libs folder to `os.environ["PATH"]"` — reproduced
   the exact same failure. Windows' post-Python-3.8 "safe DLL search mode"
   does not consult `PATH` when a dependent DLL is loaded via
   `ctypes.CDLL(full_path)` (which is how `torch.ops.load_library`
   resolves torchcodec's own `.dll`), unlike the classic search order.
2. `os.add_dll_directory()` on the shared-libs folder alone — still failed.
   Loading `libtorchcodec_core8.dll` directly with `ctypes.CDLL` after only
   `os.add_dll_directory()` (no `import torch` first) reproduced the same
   `FileNotFoundError`.
3. `os.add_dll_directory()` **after** `import torch` — worked. Torch's own
   `__init__.py` registers its own DLL directories (its `lib/` folder) via
   the same mechanism, and torchcodec's DLL transitively depends on those
   being registered first, not just the FFmpeg ones.

**The fix.** Vendored the full-shared FFmpeg build's DLLs into
`ffmpeg/shared_libs/` (gitignored, same as the rest of `ffmpeg/` — already
covered by `packaging/build_dist.py`'s existing whole-folder
`ASSET_FOLDERS` copy, so no packaging changes were needed). Registered that
folder in `config.py` — imported by nearly every module in the codebase,
and already importing `torch` at the top, which naturally satisfies the
"torch must be imported first" ordering found in step 3 above. `main.py`
needed no changes: `config.py` gets imported transitively long before any
TTS call, regardless of entry point.

**Verified — twice, for real:**
1. A standalone script directly called `TTSHandler.generate_audio()` with
   real Hindi text after the fix and got back a 211KB real `.wav` file
   (before the fix, the identical call logged
   `Generation Failed: Could not load libtorchcodec` and produced nothing).
2. A full re-render of `Sample/2.mp4` (~33 minutes) completed with
   **zero** `Generation Failed` lines across all 39 segments — every line
   of dialogue actually got dubbed this time. `ffprobe` confirmed the
   output has valid video/audio/subtitle streams at the correct duration
   (122.4s), and `ffmpeg -af volumedetect` confirmed the audio track is
   real signal, not silence (mean −16 dB, max 0 dB, not the flatline a
   silent/empty track would show).

**The honest takeaway.** This is the kind of bug that "the render completed
successfully" cannot catch, because the pipeline's own success/failure
signal (exit code, `100% COMPLETE`) was disconnected from whether the one
thing the user actually cares about — real dubbed speech — was present.
Every prior claim in this document that a render "passed" or "completed"
only verified structural correctness (valid output file, correct streams,
no crash), never verified that the dubbed audio was real, non-silent
speech, until this section's `volumedetect` check. Earlier renders in
§52/§53 may or may not have been affected by this exact failure mode —
they were not re-checked with `volumedetect` after the fact, since the
purpose here was fixing the current, real regression, not auditing every
past render retroactively.
