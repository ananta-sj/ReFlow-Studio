# Automatic disposable cleanup

**Settings → Automatically clear disposable caches** is enabled by default. It runs at app startup and after owned work has stopped on exit.

- Source `.pyc`/`.pyo` files and empty `__pycache__` directories are removed. Unknown files placed in a cache directory are kept.
- Old temporary job directories are removed only when they contain a valid ReFlow ownership marker, the recorded process is no longer running, and no files have changed within 24 hours. Process creation time protects against Windows reusing a process ID.
- Installed runtimes, environments, model weights, outputs, saved reviews, recovery checkpoints, Git data, links and junctions are excluded. Unknown old job folders without ownership metadata are retained.
- The main app disables bytecode writing, and Python commands launched through the owned worker helper get `-B`, including embedded Python runtimes that ignore environment variables.

This setting is separate from clearing current render temporary files or clearing temporary files on exit. Changing it does not invalidate saved review takes. It does not empty the Windows Recycle Bin or clear unrelated system/application caches.

The first local cleanup removed 114 bytecode files (904,918 bytes) and 11 empty cache directories. No job workspaces were removed. Larger storage use is primarily models and installed runtimes; those are deliberately retained.
