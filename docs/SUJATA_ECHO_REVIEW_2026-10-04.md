# Sujata perceived echo: stage-isolation review

## Feedback and scope

After the native XTTS playback-rate repair, the user said: “beautiful.. but
i think the sujata voice has a bit echo”. Positive feedback with a specific
unresolved Sujata issue; not blanket quality or release acceptance. Abhishek,
the presented clips and original references remain unchanged.

The presented Sujata file is mono. Its diagnostic chain is the retained XTTS
waveform, corrected24000-Hz labeling, loudness normalization, RubberBand1.342/
pitch1 and gain-only peak protection. No explicit echo/reverb filter, second
voice overlay or stereo channel delay. This does not exclude room coloration
in reference/synthesis or processing artifacts. Echo's origin is unestablished.

This retained take used seed1234, temperature0.90 and the full unprocessed Hindi
reference. Production uses temperature0.75 and reference cleaning. This review
targets the actual clip heard, not an invented equivalent production take.

## Negative tempo-option test

Existing FFmpeg advertises `window=short`. Same normalized native input with
`rubberband=tempo=1.342:pitch=1:window=short`, unchanged format and gain-only peak
correction, produced6.431s/−16.57LUFS/−1.55dBTP. Its full WAV SHA-256 matches the
current clip exactly:
`cd60690ff40d3c470014b2cefdec9d1a708c642cd97e263290885f26dc862fd5`.
No improvement or change on this stack/input; not presented as an echo fix.
This does not establish why the option has no effect or that other modes cannot
help. No alternative mode was promoted to production.

## Listening controls

`dev/review_sujata_echo.py` reuses retained assets, no inference. Native decoder
PCM relabeled without resampling. A/B bypass tempo and use gain-only matching
near−18LUFS. No added EQ, denoising, dereverb, gates, fades or word cuts.

| Control | Contents | Duration | LUFS | True peak dB |
| --- | --- | --- | --- | --- |
| A: raw native | Generated waveform at correct native rate, gain only | 8.630s | −17.99 | −1.73 |
| B: normalized, no tempo | Same waveform after existing loudness normalization, comparison gain only | 8.630s | −18.00 | −5.09 |
| Retained current | Native normalized waveform with existing tempo | 6.431s | −16.57 | −1.55 |

A/B differ0.01LU in integrated level; peaks/dynamics differ because normalization
is the stage under test. Both are deliberately slower than the current clip;
this is not a new pace proposal. Echo in A points toward synthesis/reference;
A clean and B affected points toward normalization; both clean and current
affected points toward tempo. These are conditional next investigations, not
proven diagnoses. Listening is required before selecting a corrective change.

## Evidence and preservation

Receipt `validation/2026-10-04-sujata-echo.json`; final folder
`validation/2026-10-04-sujata-echo-9a09f414/`. Earlier window-only run remains in
`validation/2026-10-04-sujata-echo-e6a9d660/`, intermediate unmatched controls in
`validation/2026-10-04-sujata-echo-61249785/`; separate logs retained. Final A/B
improve level matching, intermediate files are not promoted or deleted.

Each run validates decoding, duration within100ms of expected tempo relationship,
mono24000-Hz input, finite measurements and true-peak tolerance. Raw source hash
matches the original native-Hindi receipt. Owned workspaces removed.
Only diagnostic code/media/docs added; production/settings/defaults unchanged.
No new package/model/download. Prior490 backend checks retained, not rerun for
this media-only experiment. Full timing/transcript/translation/video acceptance
remains open. No commit, push or release.

## Subsequent listening result

The user reports both controls mostly the same and good, with little distortion
in the first few words of both. The artifact is audible to the user in the raw
native-rate control, before normalization or tempo. Normalization is therefore
not required for its presence; the precise origin remains unestablished. Next:
existing reference-cleaning control at fixed sampling settings, documented in
`SUJATA_REFERENCE_CONTROL_2026-10-04.md`. Do not promote a speculative fade,
threshold trim or echo filter as a fix.
