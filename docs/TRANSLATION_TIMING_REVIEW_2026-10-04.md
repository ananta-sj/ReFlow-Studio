# Failing Hindi sentence: transcription, translation and timing review

Status: diagnostic and listening review completed technically; human wording/mix
acceptance pending. This is not a general automatic translation repair.

## What failed previously

The eight-second news fixture generated the fragment:

> एक लंबे समय से मानक समाचार रिपोर्ट से पहले, दृश्य भाषा खुद को स्थापित किया, एक है कि तुरंत

Its first cue had 4.880 seconds available, while the generated voice still needed
7.055 seconds after the former 1.3x fit adjustment. Production correctly rejected
audible truncation. The failed receipt and prior historical output are preserved.

The recorded short raw-audio transcript also misread “Before long” as “Before a
longer-standard” and stopped the first cue at “immediately.” The continuation
“recognisable to anyone” belonged to the same sentence but arrived in a separate
cue. The separated-audio failure did not preserve its exact source transcript,
so its precise upstream recognition cannot be reconstructed from that receipt.
Do not pretend the old raw transcript and separated transcript are identical.

## Source-context diagnostic

Existing local faster-whisper tiny transcribed the first 15 seconds, with English
explicitly selected, five beams, temperature zero and word timestamps. No new
model or package was downloaded. It produced:

> Before long, a standard news report visual language established itself, one that's immediately recognisable to anyone.

The two recognition cues occupy 0–4.920 and 4.920–6.300 seconds. The following
report introduction begins at 6.660 seconds. This supports treating the first
complete sentence as one review unit, with 6.300 seconds of sentence timing and
the existing gap available until 6.660. It does not move the following sentence.
The recognizer still produces an uncertain later “Me, has this report”; that was
not translated or claimed corrected in this experiment. Source recognition is
not yet human certified. Source/context audio and word probabilities are retained
in `validation/2026-10-04-failing-line-source-context.*`.

## Translation and actual voice comparison

NLLB translated the complete sentence as:

> जल्द ही, एक मानक समाचार रिपोर्ट दृश्य भाषा स्थापित हो गई, जो किसी को भी तुरंत पहचानने योग्य है।

It now retains the “Before long” / “जल्द ही” meaning and the omitted continuation,
but its Hindi remains awkward. Proposed concise review version:

> जल्द ही खबरों की एक तय दृश्य शैली बनी, जिसे सब तुरंत पहचान लेते थे।

The proposed wording preserves the early establishment of a recognizable visual
style and immediate recognition; its meaning/register still require user review.
It is a manual candidate, not output claimed to come from a new model or a
sentence-specific rule installed in the application.

Both texts were freshly synthesized with existing XTTS, the previously reviewed
six-second voice reference, CPU, temperature .75 and reset seed 1234. Raw speech
was retained, then replayed through production mastering and the approved Hindi
1.342x pace; neither received a guessed final-word edit.

| Candidate | Raw voice | Production-paced voice | Fit before next cue | Measured level / true peak |
| --- | --- | --- | --- | --- |
| Complete-context NLLB | 8.081 s | 6.009 s | Pass, under 6.660 s | -14.97 LUFS / -1.47 dBTP |
| Concise manual review | 6.769 s | 5.030 s | Pass, under 6.660 s | -15.19 LUFS / -1.46 dBTP |

Execution took 77.937 seconds; owned workspace removed. No speech was hard-cut
to fit. Neither output is claimed to fit the original 4.880-second fragment
window: the test intentionally uses the complete source-sentence interval. The
timing correction and wording correction are separate improvements.

Receipt: `validation/2026-10-04-failing-line-review.json`; review directory:
`validation/2026-10-04-line-review-76b5fc7e/`. It retains both raw and fitted voices.

## Background-mix review

The concise version was placed at the original sentence start in a 6.660-second
track, retaining the gap before the next report introduction. The existing
production dynamic mixer combined it with the retained Demucs background from
the historical eight-second fixture; separation was not rerun. A standalone
source sentence and `concise-review-mix.wav` are available in the review folder.
Mix receipt: `validation/2026-10-04-failing-line-mix.json`.

Playback, timeline, voice-content and measured level checks passed. Human review
must check wording, pronunciation, comfortable volume and residual original
speech, especially after the Hindi line ends. Automated peak/timeline checks
cannot prove that imperfect separation removed all English narration.

## Production implications and remaining work

The approved Hindi pace is already applied in production. This review introduced
no new production translation rule or cue-merging policy, changed no original
sample or model, and installed no tools/frameworks/packages. It demonstrates
that source context, complete-sentence grouping and concise wording can repair
this review unit without losing words. It does not close the unchanged automatic
news-fixture failure or certify every full render.

The next general fix should preserve source and generated text separately,
translate complete thought units within bounded media/speaker windows, and
allow reviewed text/timing corrections before regenerating speech. A generic
merge rule must respect pauses, speaker changes, maximum lengths and following
cue starts; blindly enlarging every cue or replacing one known string would
hide the underlying problem. Broader translation acceptance and an implemented
cue-review workflow remain open.

## Subsequent listening feedback: final-word delivery

The user confirmed that no original English is audible in the mixed preview.
That specific background-leakage check passes. They rejected the robotic,
abrupt transitions in its last three/four words; complete mix/voice acceptance
therefore remains false. The mix receipt preserves both verdicts separately.

The original generated waveform already contains quiet intervals. This does
not establish word alignment or prove each gap is a defect; consonants and
breaths must not be deleted blindly. A comparison of the raw generation without
EQ/compression/tempo, a fresh sampling of the same text, and a simpler proposed
ending is underway with the existing engine. No generic production pause or
translation rule has been introduced. The approved Hindi pace remains intact.

### Ending comparison results

The rerun completed successfully in 122.875 s. Same wording with a fresh reading
fits in 4.839 s; the simpler ending `जिसे हर कोई तुरंत पहचान सकता था` fits in
5.030 s. Both pass the existing word-preserving timing boundary and retain the
approved pace. Review files are in `validation/2026-10-04-ending-review-1c0cd47b/`;
receipt: `2026-10-04-robotic-ending-review.json`. No seed/translation default was
changed and no automatic gap deletion was introduced. User listening review is
still required; neither candidate is declared natural merely because it fits.

One actual candidate exposed a mastering peak excess. Production now corrects
finite excess with gain reduction and remeasurement before publication, preserving
pitch/timing/pauses and retaining the rejection threshold. The actual rerun needed
0.44 dB correction. A meaningful converter-overshoot regression uses real audio
measurements, and the full backend suite passes 464 checks. The correction solves
a level-handling failure, not an established cause of robotic delivery.

### Selected sentence reading

The user accepted the 4.839 s fresh reading as good. It is now selected for this
sentence and the receipt records that specific voice-delivery approval. No
production sampling seed or translation policy changed. The exact fitted audio
has been reused in `fresh-reading-selected-mix.wav`, with the preserved background
and original 6.660 s sentence timeline. Measured mix: -12.11 LUFS / -1.49 dBTP;
no words cut, workspace removed. Receipt: `2026-10-04-selected-sentence-mix.json`.
Full listening review of this selected mix remains pending; broad automatic
translation/timing correctness is not established by the selected manual unit.

### Correction to background interpretation

The user confirmed the source excerpt contains no music or ambience. Describing
the separator's residual stem as music/ambient sound was incorrect. Earlier
mixing diagnostics are retained, but that stem's name is not semantic evidence
of source background content. The selected sentence output is now
`fresh-reading-selected-voice-only.wav`: accepted voice PCM preserved exactly,
remaining time to 6.660 s filled with exact digital silence, no residual track.
Receipt: `2026-10-04-selected-voice-only.json`. The preceding selected mix is
marked superseded for this review. General production background settings and
original media remain untouched.
