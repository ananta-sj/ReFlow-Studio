# Real-video dubbing iteration — 4 October 2026

## User request and chosen scope

User could not locate their intended video and authorized using existing media.
Use `Sample/2.mp4` first44 seconds, original854×480 moving frames/25fps, rather
than the old8-second synthetic static portrait. Reencode the bounded diagnostic
input with existing FFmpeg, retaining original source untouched. Use the supplied
Abhishek recording as the single Hindi voice reference.

Current production `video_dub` route: background separation, source recognition,
Hindi translation, speech/timing, background mix, subtitles, final video mux and
stem export. CPU/offline, one segment worker; existing installed Whisper tiny,
NLLB and XTTS via isolated fixture connections. No production settings/model
registry changes or new downloads. Keep background enabled, subtitles enabled
as a soft track, four stems requested. Lip-sync, enhancement and visual content
filter disabled explicitly for this basic audio/timeline/subtitle test; this run
does not certify those optional stages or lip-motion synchronization.

Unlike earlier controlled voice listening, generation uses existing production
temperature/seed defaults and its reference cleaning/mastering stages. Accepted
diagnostic temperature0.90/reference bytes are not silently injected into the
production engine. The accepted new Rubber Band tempo helper is in production.

## Harness and evidence

`dev/verify_real_video_dub.py` binds an owned cancellable job and runs the current
pipeline with local fixture connections. Captures grouped source cues, translated
speech cues, progress, generated cue WAVs, cue durations and stage timings. On
failure retains source clip, reference copy, cues, available subtitle/reference/
mix artifacts and exact error, then removes owned temporary workspace. A failure
receipt is not a successful final render. Existing source/user media preserved.

Technical output gates: final published video file; video/audio/subtitle streams;
duration44s within150ms; complete audio/video decode to null. Existing pipeline
guards reject invalid recognition bounds, missing audio and spoken-word truncation.
Generated timings must fit; this test cannot disable those guards to produce a
nominal pass. No manually rewritten transcript/translation or replacement
render route is inserted into this baseline.

Receipt/log: `validation/2026-10-04-real-video-dub.json` and `.log`.
Human listening/semantic acceptance remains separate from technical decoding.
The video must be reviewed for correct meaning, clear natural voices, timing,
original-English leakage, subtitle alignment and moving-frame quality.

## Results

Recorded when execution completes. No new full-workflow acceptance claimed while
the run is in progress. Prior487 backend checks and portable control acceptance
remain valid for their contracts; they cannot certify this real media's quality.

### Completed baseline: automatic run failed safely

Elapsed **572.734 seconds** (9min33s). Owned workspace removed. Durable evidence:
`validation/2026-10-04-real-video-5b4d14f8/`. No final dubbed video was published;
no full automatic or human-quality acceptance. The input clip, supplied reference
copy, clean reference, separated vocals/background, Demucs worker log, translated
SRT, cue report and first completed Hindi cue are retained.

Separation inference progress took about3min38s; this is the worker's progress
timer, not a complete independent stage wall-clock measurement. Recognition
passed bounds and produced9 grouped cues; source language detected English.
Translation completed. Cue1 produced5.381s within6.640s (99.985s including engine
setup/synthesis/mastering). Cue2 failed after40.953s: needs3.011s at the approved
tempo, available2.600s. The guard refused spoken-word truncation. No extra pace
increase or manual replacement text was used to force a pass.

An auxiliary late raw-capture attempt retained0 files because the owned job was
already complete. Its log is preserved; **failed-cue raw audio was not retained**.
Do not claim that capture or an absent file establishes synthesis quality.

### Content findings requiring correction

| Cues | Observed source/output | Implication |
| --- | --- | --- |
| 2,6.64–9.24s | Recognized “Me has this report.” → “मेरे पास यह रिपोर्ट है।” | Source wording is suspect; meaning must be checked before shortening translation. The current speech also overflows by0.411s. |
| 3,9.24–14.48s | “lackluster establishing shot” becomes “अस्पष्ट स्थापित शॉट” | Awkward/literal Hindi; editorial review needed, not automatic semantic acceptance. |
| 4,14.48–19.68s | “Next day, walkie-talkie preamble from the altar...” → fragment ending “अंकुश” | Suspect recognition and incomplete source thought; translation is not a natural complete Hindi utterance. |
| 4–5 | One thought crosses the bounded cue grouping limit | Separate translation of fragments loses contextual meaning; arbitrarily extending synthesis windows is not a valid repair. |
| 5 | Source “pricks” mapped to gendered Hindi “कुतियाओं”; “fucking matrix” to “गंदगी मैट्रिक्स” | Tone/meaning choices need review; literal machine output is unsuitable as an accepted final script. |
| 7–8 | “a fellow shot” is suspect; Hindi retains “babbles” and “monochrome” and fragmented syntax | Mixed-language/fragment output and probable recognition error. Keeping an English technical term may be acceptable, but unreviewed text is not evidence of meaning preservation. |
| 9,43.44–44.04s | “This is followed.” / “इसका अनुसरण किया गया है।” in0.600s | Arbitrary44s extraction starts the next sentence. Recut at a reviewed complete-sentence boundary rather than forcing this partial cue to fit. |

These are audit flags, not a certified corrected transcript. No invented reporter
name or silently repaired source wording. `source-cue-02.wav` isolates the actual
original audio for the immediate source ambiguity.

### Next repair sequence and practical limits

1. Verify suspect English wording against source audio; prepare proposed natural
   Hindi with explicit corrections and retained machine baseline.
2. Use a complete-sentence excerpt boundary. Retain/correct cue timing and context
   rather than disabling word/timing validation.
3. Regenerate only affected cues and review fitting takes. The current video
   pipeline does not yet reuse audio-review accepted takes; repeated full runs
   would unnecessarily repeat expensive separation/recognition/translation.
4. Add reviewed-track video/subtitle assembly before presenting an accepted full
   output. Then test actual audio leakage, A/V placement, decoded video and stems.

No mixing/mux/subtitle-stream or final frame-decode acceptance was reached in this
baseline. Background leakage, final synchronization and moving-frame quality
remain unverified. Optional lip-sync/enhancement/filter stages were not enabled.
No production code/engine/default changed during this test. Added diagnostic
driver/report only; existing487 backend checks and83 frontend checks are retained,
not rerun or equated with real media quality. No new tools/downloads, commit,
push or release. Current release remains not ready.

### Follow-up: contextual recheck and bounded cue retry

The retained 15-second recognition also reports “Me, has this report.” This does
not resolve the ambiguous wording, and the user's “ok” was not treated as source
confirmation. Two isolated fresh cue-2 takes reused the saved clean reference
and unchanged production generation/mastering/tempo, without repeating separation
or translation. They lasted 6.134s and 5.832s for the same 2.600s slot; neither
fits. Raw and processed takes are retained and all four WAVs decode. Total93.953s,
owned workspace removed. The retry's first invocation had a diagnostic JSON
encoding error before inference; explicitly fixed UTF-8, original log retained.
See `REAL_VIDEO_SCRIPT_REVIEW_2026-10-04.md` for proposals, uncertainties and
limitations. No cue acceptance or final video, no production defaults changed.
