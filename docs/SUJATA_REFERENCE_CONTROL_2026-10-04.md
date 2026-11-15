# Sujata opening distortion: reference-preparation control

## Trigger and diagnostic interpretation

On the native-rate raw and normalized/no-tempo controls, the user reported:
“both are mostly same... that is good... but both have little distortion a the
starting few words”. Both perceived artifacts occur before tempo processing;
normalization is not required for the reported artifact to be present. This
supports investigating the generated waveform/reference rather than trying to
mask opening words with fades. It does not certify a cause, an objective echo
delay, clipping, a defective reference, or identical audible quality everywhere.

## One bounded experiment

`dev/review_sujata_reference.py` reuses the exact retained full Sujata reference
and same longer Hindi quality-check text. It applies the project's existing
`AudioEngineer.clean_reference_audio` to an owned reference copy: mono,80Hz
high-pass, adaptive first/last nonsilent-range trimming using500ms minimum
silence and threshold dBFS−16, then peak normalization. This does not remove
internal pauses or perform dereverberation. The existing cleaner's docstring
mentions compression, but its implementation here performs peak normalization,
not a separate compressor. No new filter/tool/framework/model is installed.

CPU XTTS uses the existing checkpoint, seed1234, temperature0.90, generation
speed1.0, split_sentences=True, and correct native writer rate. These match the
earlier diagnostic sampling settings; production temperature remains0.75 and
ordinary generation remains unseeded. The reference-preparation bundle is the
intended changed conditioning input. A change in outcome cannot isolate which
part of that bundle helped or prove general quality superiority.

Raw synthesis is preserved before loudness/tempo. Listening output uses the
earlier accepted loudness-only stage, then existing RubberBand1.342/pitch1,
then measured gain-only matching to the earlier native clip where true-peak
headroom permits. No additional EQ/compression, gate, fade, word truncation,
sentence rewrite, tempo increase or reference substitution. This is a full
new utterance, not edited fragments of different takes. Abhishek unchanged.

The original17.528s reference's −40dB/0.25s silencedetect pass found no intervals.
That does not establish absence of room noise/reverb or predict the cleaner's
adaptive edge trimming, which uses a different criterion.

The actual cleaned copy is also17.528s: this run did not trim any reference
duration. Mono input remains mono24000Hz. The meaningful preparation differences
here are the existing80Hz high-pass and peak normalization, not removed speech.

The retained baseline raw waveform has207120 samples, with one full-scale sample
at native-rate time0.310125s and initial sample351/32768. Installed Coqui's
`numpy_transforms.save_wav` scales the waveform by
`32767 / max(0.01, max(abs(wav)))` before converting to16-bit PCM. A maximum sample
reaching32767 is therefore expected from its saver, not proof of sustained
clipping or the cause of several distorted words. No automatic de-click or
sample replacement was applied.

## Evidence and limits

Receipt `validation/2026-10-04-sujata-reference.json` and execution log. The driver
validates retained-reference SHA, original-clip SHA before/after, playable raw
speech, full decode of reference/raw/normalized/final files, expected processed
duration within100ms and measured final true-peak tolerance. It records raw
full-scale sample count and first occurrence, if any; sample counts alone do not
establish or exclude perceptual distortion.

## Completed result

Completed115.953s including model load and preparation; synthesis68.391s.
The writer reports24000Hz. Cleaned reference remains17.528s, SHA differs as
expected after filtering/normalization. New raw take8.118s versus the baseline's
native8.630s; processed6.049s versus6.431s. The tempo remains1.342; shorter
generation is not an added pace increase or word cut. Content completeness and
opening naturalness require listening, not duration alone.

Final gain correction+0.24dB gives−16.56LUFS versus baseline−16.57LUFS;
true peak−2.20dBTP versus−1.55dBTP. Integrated levels nearly match, while dynamics
and peak shape differ. Candidate raw has one full-scale sample at0.33875s, which
does not diagnose clipping given the saver's peak scaling.

Output folder `validation/2026-10-04-sujata-reference-d18b58a6/` contains the cleaned
reference, full new raw, normalized raw, final candidate and preserved earlier
clip. Reference/raw/normalized/final decode checks pass, timeline and peak checks
pass, retained reference/current-clip hashes are unchanged, owned workspace removed.
No objective test here establishes that the opening distortion improved.

A new take is not accepted until the user hears it. No production/default change or speculative echo fix.
Prior490 backend tests retained, not rerun for diagnostic-only code and media.
Full-video/cue-fit/semantic/platform release gates remain open. No downloads,
commit, push or release; preserved original user files are never overwritten.

## Subsequent acceptance

The user responded “beautiful” to the6.049s candidate. The exact presented take
is accepted and retained; the receipt and accepted-example hash ledger record
the decision. This supports this preparation variant on this passage, not a
universal distortion cause or all-text quality guarantee. Varied-text testing
is documented in `HINDI_VOICE_COVERAGE_2026-10-04.md`.
