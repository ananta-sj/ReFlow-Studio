# Windows branding fix and source upload handover

The EXE already contained the logo, but its Python-hosted application window
used the interpreter's default icon. Production startup now sets the explicit
`ReflowStudio.Desktop` Windows application identity before creating the window
and supplies `assets/icon.ico` to the window backend. The tray uses the existing
PNG logo instead of the generic green dot. Non-Windows windows use the PNG icon.

The real production startup was exercised in a hidden Windows window. Its
native Form icon pixels matched the supplied ICO, its taskbar-entry property
was enabled, and the current process reported the Reflow application identity.
The source assets were reused; no new software or models were installed.

The existing approved PyInstaller installation rebuilt the launcher. Its output
was compared with all installed launcher companion files. Five branding tests,
eighteen packaging contracts and the updated executable's offline check passed.

## Updated files to use

- Windows download: `dist/ReflowStudio-Windows-Executable-RC2-2026-10-31.zip`.
  SHA-256: `5e66e682641e689a810c82f356c5be713f5fc50f534f4d647b59287c0d29cb81`.
  All 192,871 ZIP members were decoded and checked against the updated manifests.
- Split download: `dist/github-windows-download-RC2/`. Its two verified parts
  reproduce the complete corrected Windows ZIP.
- Updated source ZIP: `release-assets/ReflowStudio-source-RC2.zip`.
- Extracted source-only upload folder:
  `release-assets/github-source-upload/ReflowStudio-source/`.
  Its 838 files include the new README and `.github/workflows/build.yml`, but no
  EXEs, release ZIPs, installed runtimes, model weights, media, settings or logs.
- Owner upload instructions: `release-assets/UPLOAD-THIS-SOURCE.md`.
  Public/general instructions: `docs/GITHUB_UPLOAD_GUIDE.md`.

Only the closed test app's launcher log was removed. Saved settings, graph and
UI preferences were checked before/after cleanup and preserved. Models and
outputs were not removed. Personal runtime state is excluded from distribution.

The earlier RC1 archives remain as rollback evidence; use RC2 for the corrected
download. No source was committed/pushed, workflow dispatched, or release
published. Fresh-PC, full-workflow and licensing release gates remain open.

See `docs/validation/2026-10-31-iconfix-summary.json`,
`2026-10-31-taskbar-branding.json`, `2026-10-31-iconfix-archive.json` and
`2026-10-31-user-test-log-cleanup.json` in the same validation folder for receipts.
