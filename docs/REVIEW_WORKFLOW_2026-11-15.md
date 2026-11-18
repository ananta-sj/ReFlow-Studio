# Saved dub review workflow

Open the Dashboard's **Prepare and review your dub** panel. For multiple original voices, choose **Prepare for character matching**, confirm clear examples of the characters, then match characters. The unresolved-character filter brings uncertain assignments forward. This review matcher remains experimental; do not assume every automatic assignment is correct.

Choose **Run first pass on remaining lines** after references are ready. Existing accepted takes are skipped. Each line gets at most two speech attempts, with timing, delivery measurements where available, and local Whisper word checks. Each checked line is now committed before work starts on the next line; cancellation or an engine failure cannot discard an earlier completed line in the same former twelve-line batch. Models stay loaded between lines.
An isolated speech-engine failure is saved for review and the next line continues. Three consecutive engine failures stop the pass with progress saved. A generation that exceeds its speech budget is an overlong-line review decision, not evidence that the engine is globally broken.

Reopen the saved review after restart to retain completed takes. Inspect flagged lines against original audio, edit wording or character assignment, generate another take, and explicitly accept a fitting result. Editing a line's wording invalidates its takes. Rendering requires all lines to have fitting accepted takes and character matching to be current.

When an episode stops for dialogue review, choose **Recover into editable review** in its failure report. This verifies the run's saved dialogue and original media, then builds a saved editable draft without repeating recognition or translating saved wording. Audio preparation runs again; old speech takes are not imported or accepted. If translation never finished, recovered source-only lines are explicitly marked pending and cannot be spoken until translated or given corrected target wording. Explicitly preserved songs and sounds remain original in reviewed exports and cannot overlap recovered dialogue.

An automatic timing/word pass does not verify translation meaning, emotion, or natural acting. The interface now states this explicitly. This change does not enable the rejected experimental translation model and does not establish successful two-minute or full-episode dubbing.

Review preparation also no longer prints an emoji to the Windows console during reference cleaning. That print could raise UnicodeEncodeError under a legacy console encoding and abort preparation; it now uses standard application logging.

## Finding and auditioning dialogue

The dialogue table shows original wording, target wording, character and review status. Search by either text or character name. **Next unresolved line** follows the active filters and wraps to the first matching unresolved line. The selected line stays in the inspector when filters change. Save or discard unsaved edits before changing lines; navigation is also blocked during active work.

Original, candidate and accepted auditions have explicit labels. Switching between them resets the audio player, including when recordings have the same byte length. A saved accepted take remains distinct from a replacement candidate. Changing a filter does not select another character or line. Explicit cue navigation brings the selected row into view; opening a review does not automatically scroll the page.

Timing advice may be calibrated from compatible accepted takes; see [Speech timing advice](TIMING_ADVICE.md). Predictions and automatic checks do not replace listening for pronunciation, identity, meaning or delivery. Native window, playback and scrolling acceptance checks remain pending; component regressions verify state and bridge routing.
