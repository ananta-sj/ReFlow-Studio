# Native builds, installers and source downloads

The workflow `.github/workflows/build.yml` builds from `main` pushes, supported
version tags and manual runs. Successful eligible main builds publish a new
numbered **Desktop Preview** release (for example `v0.7.3-desktop-preview`).
Previous releases remain available. Only the publishing job can write releases.

## Download choices

- **Windows x64 installer:** the `windows-x64-setup` EXE installs for the current
  user, normally in `%LOCALAPPDATA%\Programs\ReflowStudio`, with a Start Menu
  shortcut and optional desktop shortcut. No administrator access is requested.
- **Windows x64 portable:** extract the entire ZIP into a writable folder and
  open `ReflowStudio.exe`. Keep all companion files together.
- **Linux x64 installer:** run `sh ./<downloaded-setup-filename>.run` as your
  normal user, without sudo. It installs to `~/.local/share/ReflowStudio` and
  adds an application-menu entry. Use the same file with `--uninstall` for removal.
  The tar.gz remains available for portable use.
- **macOS Apple Silicon / Intel:** mount the matching setup DMG and run
  **Install Reflow Studio.command**. Open the installed app in `~/Applications`,
  rather than launching from the image or dragging into `/Applications`. Use
  **Uninstall Reflow Studio.command** from the image for removal. The tar.gz
  remains a portable development option. Images are not notarized.
- **Source:** `ReflowStudio-source.zip` contains application source, build inputs,
  tests and reviewed recipes, excluding personal media, models, environments,
  credentials, settings and logs.

Python and desktop dependencies are bundled. **Local AI engines, model weights,
voice references, credentials and FFmpeg/FFprobe are not bundled.** Windows also
requires WebView2 and Visual C++ runtimes. The installer does not download or
install those prerequisites. Windows packages are unsigned and may encounter
Windows reputation checks; do not disable security protection to run them.
Linux native Qt prerequisites and macOS installation/signing behaviour still
need platform-specific volunteer testing. The installed Mac app keeps its writable
Python/application runtime and generated data outside the `.app`, in
`~/Library/Application Support/ReflowStudio/runtime`. This duplicates its bundled
runtime on disk; it avoids writing into the installed application bundle. Existing
portable settings/models are not automatically migrated.

## Windows updates and removal

Close ReFlow, including its tray icon, before updating or uninstalling. Setup
checks the application's byte-range lock and refuses an active instance.
Install over the same location to update program files. Generated settings,
models and outputs are not installation payloads and are retained on uninstall;
there is no broad recursive user-data cleanup. Portable copies are independent
and are neither migrated nor deleted automatically. Keep a separate backup of
important settings, accepted takes and media before testing preview updates.

Installer metadata identifies the 0.7 preview series; the GitHub release tag and
commit-bearing download filename identify each exact build. This is not a
silent updater or a system-wide installation.

## Linux/macOS updates and removal

Run the same architecture's installer over its existing per-user installation.
Only manifest-owned program files are replaced. Modified or unowned program files
block an update rather than being overwritten. Close ReFlow before updating or
removing it; installers use the same application lock as the running desktop.
Removal deletes only unchanged recorded program files and empty program folders.
Settings, downloaded models, outputs and modified files remain. Portable copies
and system-wide installations are not migrated or deleted.

Installation is not transactional across power loss or disk-full failures. If an
interrupted installation cannot be retried because files appear unowned/modified,
preserve the affected folder and seek recovery help rather than deleting user
data. Fresh-machine, interruption recovery and interactive installation testing
remain open acceptance work.

## Automated gates

The workflow builds the locked interface and native PyInstaller launcher on
Windows x64, Linux x64, Apple Silicon macOS and Intel macOS. It verifies pinned
Python downloads, installs desktop dependencies, runs packaging contracts and
an offline executable/package check, and verifies archive readback/checksums.

On Windows, an existing Inno Setup compiler on the hosted runner creates setup
from the exact candidate manifest. Missing compilers fail the build; no fallback
compiler download is performed. Extra files, links and modified payloads are
rejected. A disposable installation then checks overlay-upgrade preservation,
installed package and hidden desktop/bridge startup, active-app upgrade blocking,
and uninstall preservation of synthetic user files. Publication waits for all
platform builds and all installer gates. Check reports are retained as
Actions artifacts, including `ci-windows-installer-smoke.json`.

These checks do not establish fresh-machine compatibility, visual/interactive
acceptance, real inference or complete episode quality. Reliable unattended
multi-character episode/movie dubbing remains unvalidated. Original ReFlow code
is AGPL-3.0-only; see `LICENSING.md` for third-party terms and distribution limits.

Linux uses standard shell/tar/checksum tools and the bundled Python; macOS uses
`hdiutil` and bundled Python. No installer downloads additional tools or models.
Hosted acceptance executes the actual `.run` or mounts the actual DMG, installs
under an isolated home folder with spaces, checks upgrades and active-app locks,
runs installed package/hidden desktop checks, and checks data-preserving removal.
On Linux, the hidden desktop check uses the runner's existing `xvfb-run`; absence
of prerequisites fails the gate instead of downloading them silently. On macOS,
code-signature checks before and after startup verify that the installed `.app`
was not modified. Developer ID signing/notarization remain separate work.

**Testing status:** installer source and contract tests are locally checked on
Windows. Actual native installer builds and acceptance require Actions on the
matching OS; these source checks do not establish that those future gates passed.

## Runner startup prerequisites and shutdown checks

The Ubuntu build runner explicitly installs the Qt/OpenGL/XCB and WebEngine
system libraries required by the existing desktop backend, plus Xvfb/Xauth for
hidden startup testing. This approved setup affects disposable runners only;
Linux users still need equivalent distribution-native libraries. The runner's
system package inventory is retained with its check artifacts. FFmpeg remains a
separate media-processing prerequisite; its absence is not the GUI failure.

Windows acceptance waits, with a fixed timeout, for Inno's final uninstaller
process to release its log before checking removal and cleaning its temporary
installation. A stuck uninstaller still fails the gate.

macOS uses an explicitly stopped loopback interface server with bounded idle
connections so browser preconnect sockets cannot hold the process open after
window close. The normal app and hidden test share that lifecycle. Hidden Mac
startup also reports remaining threads; a lingering process emits diagnostic
stacks and fails after a short shutdown deadline. Interface acceptance alone
never overrides a failed process-exit check. These fixes require a fresh native
Actions run; earlier logs established UI startup, not successful shutdown.

The subsequent Mac shutdown traces identified bridge callback threads waiting
inside Cocoa JavaScript evaluation after window closure. The pinned pywebview
6.2.1 Cocoa adapter now cancels those waits when its native window is closed and
bounds waits for an unresponsive live window. This is shared by normal launch
and hidden acceptance; it does not force a successful process exit. Native
confirmation still requires the next build. Linux additionally checks Qt plugin
dependencies with `ldd` before packaging, includes XInput/XCB runtime libraries,
and emits plugin-loader diagnostics on the hidden desktop test.
