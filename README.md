# ReFlow Studio

**Translate, dub, and review video, audio, and subtitles in one desktop workspace.**

ReFlow Studio brings transcription, translation, voice generation, timing and
media export into a desktop interface. Choose compatible local models or
configure supported API connections, review dialogue that needs attention, and
export your results from the same project.

[Downloads](https://github.com/ananta-sj/ReFlow-Studio/releases) ·
[Builds](https://github.com/ananta-sj/ReFlow-Studio/actions) ·
[Report an issue](https://github.com/ananta-sj/ReFlow-Studio/issues)

> **Release status:** the updated Windows executable is a test candidate.
> Linux and macOS remain experimental. The new build workflow prepares review
> artifacts; it does not automatically publish a release. Check a download's
> notes for its included engines and setup requirements.

## What you can do

| Feature | What it provides |
| --- | --- |
| Video dubbing | Transcription, translation, generated speech, timing, mixing and video export. |
| Audio dubbing | The dubbing workflow for audio-only input. |
| Subtitle translation | Translate subtitle files without generating speech. |
| Dialogue review | Edit wording, audition generated takes, check timing and accept takes before export. |
| Model Marketplace | Connect compatible local models and API endpoints, choose active engines and inspect readiness. |
| Voice options | Reference-based speech generation and optional voice conversion, depending on the selected engine. |
| Background audio | Optional vocal separation and mixing to preserve background sound. |
| Visual processing | Optional lip-sync, face enhancement and content filtering with their required engines and assets. |
| Queues and recovery | Batch jobs, progress tracking, cancellation and saved recovery state. |

Language coverage comes from the selected transcription, translation and speech
models. A language appearing in the interface does not mean every engine can
translate or speak it. GPU support also depends on the engine, runtime and
operating system; CPU processing can take substantially longer.

## Start with the Windows download

Use the **application download** from [Releases](https://github.com/ananta-sj/ReFlow-Studio/releases)
when the updated release is published. GitHub's automatic **Source code** archive
is for development, rather than a ready-to-run application.

1. Download and extract the entire Windows package to a writable folder, such
   as `C:\ReflowStudio`. Do not run it from inside the ZIP.
2. Double-click **`ReflowStudio.exe`**. Keep its companion folders beside it.
3. Read `START_EXECUTABLE.txt` and `START_HERE.txt` in the package.
4. Check the selected engine in **Marketplace** and complete its model and
   reference setup before rendering.

The prepared Windows engine bundle includes Python and FFmpeg. Windows still
needs a working WebView2 runtime and the appropriate Visual C++ runtime. A
prerequisite installer is included where noted in the package instructions.
`Launch_Reflow.bat` remains an alternative launcher in that Windows bundle.

For a download distributed in parts, put **all parts** and
`Assemble-ReflowStudio.cmd` in one folder, then run the script. It verifies the
parts, creates the complete ZIP and verifies that ZIP. Extract it afterward.
The script uses built-in Windows tools and refuses to replace an existing ZIP.

### Models and first-use setup

Downloaded model weights, personal voice references, API credentials and saved
project settings are excluded from a clean distribution. Engine packages can
still contain small assets supplied by their publishers.

Some models download on first use; others require manual setup, a compatible
runtime, publisher access approval or authentication. Opening the interface does
not install every engine or fetch every model. Follow the selected engine's
readiness guidance rather than assuming a fresh copy contains your voices.

Local inference can work offline after its required runtimes and models are
available. Downloads, cloud providers and remote services need a connection.
Optional dialogue assistance uses explicitly configured services and models;
ReFlow does not automatically install a manager model or select one for you.

## A typical workflow

1. Choose a video, audio or subtitle workflow and add your input.
2. Set the source and target languages, then select compatible engines and a
   voice/reference where needed.
3. Enable optional background preservation, subtitles or visual stages.
4. Render and review the output. If dialogue does not fit its time slot, adjust
   the wording and audition another take in dialogue review.
5. Accept suitable takes and export the result. Keep your original media.

The Nodes page configures a fixed processing pipeline. It is not an arbitrary
graph execution engine. Multiple voice nodes alternate cues; automatic speaker
identification is not implemented. Worker counts control bounded preparation
work and do not guarantee parallel model inference or faster renders.

## Engines and optional features

Adapters include Whisper-based transcription; NLLB, M2M100 and IndicTrans2
translation; XTTS, F5-TTS and IndicF5 speech; and configured API providers.
Optional processing includes RVC voice conversion, Demucs separation,
Wav2Lip/MuseTalk lip-sync, GFPGAN enhancement and content-filtering models.

These adapters have different installation, language, reference and hardware
requirements. RVC needs a compatible voice model; it is a voice conversion
stage. Some routes are experimental or require a separately prepared runtime.
The available adapters are not a promise that every model is bundled or every
route has passed release testing on every platform.

## Platform builds

| Platform | Current packaging status |
| --- | --- |
| Windows x64 | Portable executable candidate with local startup and interface checks; clean-PC release testing remains. |
| Linux x64 | Native desktop preview workflow; engine and distribution-specific testing remains. |
| macOS Apple Silicon | `.app` desktop preview workflow; native engine, writable-data and signing work remains. |
| macOS Intel | Separate `.app` preview target with the same pending validation. |

The GitHub Actions workflow builds each target on its own operating system and
also exports a clean source ZIP. Its **desktop previews include desktop
dependencies, not the full Windows engine bundle**. They currently need FFmpeg
and FFprobe separately on PATH, plus any required local AI runtimes and models.
Mac previews are not Developer ID signed or notarized.

After uploading the updated source, open **Actions → Build native desktop
candidates → Run workflow**. Successful jobs provide candidate archives,
checksums and check reports as Actions artifacts. A build passing does not
establish complete media-workflow or clean-machine acceptance.

See [the native build guide](docs/GITHUB_NATIVE_BUILDS.md) for scope, checks and
release requirements, and [packaging instructions](packaging/README.md) for the
local Windows assembly process.

For uploading the updated project, use the prepared source-only export and the
[GitHub upload guide](docs/GITHUB_UPLOAD_GUIDE.md). Keep application downloads
in Releases rather than in the source tree.

## Work on the source

The interface uses React, TypeScript and Vite; the backend uses Python and
pywebview. The **desktop development setup** uses Python 3.13 and Node.js 22.
Local AI engines may use separate Python versions and dependency environments.

From a fresh clone:

```sh
git clone https://github.com/ananta-sj/ReFlow-Studio.git
cd ReFlow-Studio
```

Create a desktop environment and install its dependencies.

**Windows:**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r packaging/requirements-desktop.txt
```

**Linux/macOS:**

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r packaging/requirements-desktop.txt
```

Build the interface:

```sh
cd frontend
npm ci
npm run build
cd ..
```

Start the desktop with `.\.venv\Scripts\python.exe main.py` on Windows or
`.venv/bin/python main.py` on Linux/macOS. Native GUI prerequisites still apply.
This setup opens the desktop; it does **not** install the AI engine environments
or models. The root `requirements.txt` describes the legacy engine stack, not a
single validated dependency lock for every platform.

Packaging contracts can be checked with the desktop environment's Python:

```sh
python -m unittest discover -s packaging/tests -v
```

Use the appropriate `.venv` Python path above if that environment is not
activated. Additional tests and development helpers are in `dev/`.

## Troubleshooting

- **Missing runtime or model:** inspect the selected engine's Marketplace
  readiness and complete its particular setup.
- **Missing interface files:** extract a complete application package. For source
  development, build `frontend/dist` before starting Python.
- **Permission errors:** use a writable folder and keep all companion files.
- **An interrupted job:** review the recovery prompt. Restored batches remain
  paused until you deliberately resume them.
- **Already running:** close the existing instance, including a minimized tray
  window, before opening the same portable folder again.

For executable startup failures, check `logs/launcher.log` when present. When
[reporting an issue](https://github.com/ananta-sj/ReFlow-Studio/issues), include
the build, operating system, engine and relevant error. Remove credentials and
private media from any shared diagnostic files.

## Licensing and acknowledgements

The updated application's license choice and distribution review are pending.
The current root `LICENSE.txt` contains Python's license/history; it does not
state a selected ReFlow Studio application license. Third-party engines,
runtimes and models retain their respective licenses and access conditions.

ReFlow Studio builds on work from the communities behind pywebview, React,
FFmpeg, Whisper, Coqui/XTTS, F5-TTS, IndicF5, IndicTrans2, NLLB, M2M100, RVC,
Demucs, Wav2Lip, MuseTalk, GFPGAN and other included dependencies.
