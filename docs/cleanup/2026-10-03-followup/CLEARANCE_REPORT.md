# Final clearance pass - 3 October 2026

This pass completed the requested housekeeping before the development and
business discussion. It did not redesign features or change dependency versions.

- Removed 18 remaining `.lib` compiler/link archives from the embedded
  Python runtime's Torch `lib` directory: **151,035,100 bytes**.
  Windows inference loads the retained DLLs/PYDs. The development `.venv`
  was preserved; compiling extensions against the trimmed portable runtime
  still requires reinstalling its matching Torch wheel, as noted in the
  initial report.
- Removed the 2,013-byte `ReflowStudio.lnk`, whose target
  `dist/ReflowStudio/ReflowStudio.exe` was verified absent.
- Removed empty `installer/`, `ui/`, `gfpgan/`, `models/demucs/`,
  `models/musetalk/`, `models/uvr/`, and `models/wav2lip/` folders.
  Folder contents and reparse points were checked before removal.
  Feature recovery creates the model folders it needs.
- The routine cache scan found no populated disposable caches. Its only
  remaining target was the empty `temp` directory, which was recreated for
  processing.
- Updated `dev/cleanup_workspace.ps1` to recognize the remaining portable
  Torch `.lib` compiler inputs on subsequent runs. Runtime DLLs remain
  excluded from this cleanup rule.

The exact filenames, original lengths and reasons are recorded in
`removed-targets.csv` and `removed-folders-shortcut.csv` beside this report.
The preceding 31.08 GB -> 6.46 GB cleanup audit remains unchanged as a
historical snapshot; `size-summary.json` records the latest workspace size.

Samples, rendered outputs, frontend files, user settings, custom source
changes, Git history, and both Python environments were preserved. Legacy
packaging source/workflows remain available until a development decision
explicitly retires that route. The two environments have different dependency
sets and were not treated as interchangeable duplicates.

Validation for this pass is in `torch-check-after.txt`: Torch import, a real
CPU matrix multiplication with an exact expected result, and torchaudio import.
No new full AI render was run. Previous backend/recovery and FFmpeg test
results remain in the initial cleanup report.
