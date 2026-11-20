# Historical IndicF5 source evaluation

The unused vendored evaluation source was removed during the November 20, 2026 security review. Its training web interface contained shell-command construction, unsafe checkpoint loading and file-path operations flagged by CodeQL. No live application or preparation script imports this source directory.

Historical upstream: https://github.com/ai4bharat/IndicF5
Reviewed revision: `13f7c4d627cc10111aea8fe9c0039462cacacdc7`.

ReFlow's existing IndicF5 integration uses `f5-tts` 0.1.0 in a separately installed environment, with its own checks and acceptance limits. Removing this unused copy does not upgrade that environment or establish its dependency security. The application worker and provider remain in `core/indicf5_worker.py` and `core/providers/tts/indicf5_local.py`.

A future source evaluation must use an explicitly reviewed, pinned upstream revision. Do not restore the old training interface merely to run inference. Earlier evaluation reports are historical records, not current installation instructions.
