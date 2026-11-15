# Bounded source-sentence grouping iteration

This iteration continues the existing-stack translation/voice work. No engine,
framework, model, dependency, account action or release was added. The approved
Hindi 1.342× pitch-preserving tempo and loudness settings are unchanged.

## Problem and implementation

Previously, adjacent source cues could join only when the preceding cue was
shorter than 2.5 seconds. The reviewed source had an unfinished first cue ending
at 4.92 seconds, followed by “recognisable to anyone.” ending at 6.3 seconds.
Translating only the first fragment lost sentence context and gave speech an
unnecessarily small window.

`core/pipeline.py` now optionally joins an unfinished preceding cue to a lowercase
continuation. Closing quotes/brackets are ignored when checking terminal
punctuation; period, question mark, exclamation mark and Devanagari sentence
terminators stop this additional join. Opening quotes/brackets do not hide a
lowercase continuation. This is deliberately conservative: it does not infer
sentence boundaries for scripts without letter case, infer speakers, repair
recognition words or shorten a translation.

Both audio and video source paths enable the additional rule for a single voice.
Multi-voice jobs retain the existing short-cue policy because actor assignment
currently alternates by cue index. The extra joining would otherwise remap later
voices. All joins now reject overlapping windows and differing `speaker` or
`speaker_id` metadata, including one-sided metadata. The gap must be between zero
and 0.6 seconds and the combined source window at most nine seconds. Source
segment dictionaries are copied; detected-language metadata remains intact.
Existing short-cue joining otherwise remains available, including across short
complete sentences; this change is not a general linguistic segmentation engine.

## Verification and evidence

Five new regression tests cover the recorded long-cue shape, punctuation and
quote boundaries, capitalized new thoughts, pause/length/overlap limits, speaker
identity, single-versus-multiple voices, input immutability and language metadata.
The first test run exposed a test setup omission: source-preserving speech needs
an explicit or reliably detected language. The test now supplies English; the
production language guard was not relaxed.

The complete backend suite passes **469 tests in 98.596 seconds**. Receipt:
`validation/2026-10-04-sentence-grouping-backend.log`. The existing 83 frontend
checks/build are retained evidence; frontend code did not change in this iteration.
The owned Windows QA distribution was refreshed: 167 application files checked,
no size mismatches, no stale frontend assets removed. Original runtimes and user
media were preserved. Receipt: `validation/2026-10-04-portable-app-refresh.json`.

The acceptance runner now supports separate labelled receipts/output folders,
records grouped source and translated speech cues, and retains progress on
failure. An explicitly changed audio excerpt length requires a separate label.
The original default remains eight seconds; video settings are unchanged.

The unchanged eight-second automatic dub **failed before grouping/translation**:
the recognition worker returned a third segment beyond the decoded eight-second
duration. The existing media-boundary guard rejected it and removed the owned
workspace. No output was published. Receipt:
`validation/2026-10-04-audio_dub-sentence-grouping-workflow.json` (158.453 seconds).
The previous timing-failure receipt is preserved separately. This result cannot
prove or disprove the real-media quality of the grouping change.

A separately labelled fifteen-second automatic run tests more source context
without manual transcript/translation substitution. Its background separation,
engines, CPU route and worker settings remain those of the original fixture.
This different profile must not be reported as a pass of the eight-second case.

The fifteen-second run **failed overall**, after 178.750 seconds. Receipt:
`validation/2026-10-04-audio_dub-sentence-context-15s-workflow.json`.
Its actual separated-source recognition grouped the first sentence into
0.000–6.520 seconds. NLLB automatically generated
“जल्द ही, एक मानक समाचार रिपोर्ट दृश्य भाषा स्थापित हो गई, जो किसी को भी तुरंत
पहचानने योग्य है।” and the first cue completed the production speech/timing
stage. This establishes a successful first-cue fit, not semantic/listening
acceptance. No manual replacement was supplied.

The second recognized cue was “Me, has this report.” at 6.520–9.240 seconds;
translation yielded “मेरे पास यह रिपोर्ट है।” Recognition accuracy remains
suspect and has not been established by human review. Its generated speech needed
3.143 seconds after the approved timing adjustment, exceeding the available
2.720 seconds. Production refused to cut words or exceed the approved Hindi
pace. The third cue was recorded in the receipt but did not complete a successful
full render. No final output was published and the owned workspace was removed.

This narrows the observed problem: the original opening fragment now receives
its whole sentence window, but automatic recognition accuracy and variable
speech lengths still block unattended completion. A correction/audition/
regeneration workspace is needed; heuristic sentence grouping cannot replace
it. Accepted previous manually reviewed audio remains unchanged.

## Remaining release gates

Automatic recognition, translation and timing still require real-media
acceptance. Grouping cannot establish semantic correctness or fix an unnatural
sample by itself. Per-cue correction/audition/regeneration, consistent voice
delivery, clean-machine distribution and the other gates in
`RELEASE_READINESS_2026-10-04.md` remain open. No public release is authorized or
claimed by this iteration.
