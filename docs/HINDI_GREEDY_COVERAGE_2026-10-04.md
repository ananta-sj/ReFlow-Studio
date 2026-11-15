# Greedy Hindi decoding: further voice/text coverage

## Purpose and preserved acceptance

The user confirmed that the exact4.545s greedy Abhishek negation take starts
directly in Hindi, preserves every word and avoids stuttering. Its acceptance
and hash remain in `validation/2026-10-04-hindi-greedy.json`. That does not
automatically approve other passages, Sujata, tempo-processed output or runtime
defaults. The sampled three-sentence montages remain rejected for distortion/
stutters; prior individually accepted voice examples remain preserved.

## Bounded follow-up

`dev/verify_hindi_greedy_coverage.py` generates the two other previously rejected
passages for both voices, four fresh full utterances:

1. क्या आप मेरी आवाज़ साफ़ सुन पा रहे हैं?
2. कल सुबह दस बजे बैठक शुरू होगी, इसलिए कृपया समय पर पहुँचें।

Existing offline CPU XTTS model loaded once, sequential generation, two OpenMP
threads. The retained Sujata reference is cleaned17.528s; Abhishek's reference is
the full unprocessed19.775s mono24000-Hz clip. Hashes must match the rejected
batch's reference receipts, preserving the intended conditioning comparison.
Same text, Hindi language marker, seed1234 bookkeeping, generation speed1.0,
checkpoint penalties and reference preparation. Changed decoding is do_sample=False,
num_beams=1. Temperature0.90 remains in the call but is inactive with greedy
selection; top-k/top-p do not perform random candidate selection in this mode.

No reference substitution, added output EQ/compression/loudness normalization,
tempo, fades, gate, text rewrite or word cut. Each raw is retained and a gain-only
listening copy targets−18LUFS subject to true-peak headroom. Levels/dynamics are
measured, not assumed perfectly matched. Raw input and listening copy must have
the exact same duration and native mono24000-Hz format. Voice review WAVs join
the question and meeting sentence with900ms digital silence; this is a listening
separator, not a real source cue gap or video output.

## Checks and limitations

Tokenizer first marker, decoded roundtrip and unknown count recorded per passage.
Valid input routing does not certify audible language, pronunciation, naturalness
or complete-word preservation. Nonzero decodable raw speech, finite measurements,
peak tolerance, exact duration through gain-only adjustment, complete raw/listening/
review decode and unchanged reference hashes checked. Mechanical pass and human
acceptance are separate fields. The full negation is not regenerated here;
Sujata's greedy negation remains untested by this follow-up.

Receipt/log `validation/2026-10-04-greedy-coverage.json` / `.log`.
Completion results appended below. User listening is required before adopting
the decoding mode for actual application workflows. This is a small fixed-seed,
fixed-reference coverage batch, not a statistical reliability benchmark.

Only diagnostic code/media/docs change. No app default, package/framework/model
installation/download, source edit or accepted-waveform replacement. Prior490
backend checks retained, not rerun for diagnostic-only changes. Full moving-video,
cue fit, semantics, optional engines and platform gates remain open. No commit,
push or release.

## Completed batch

Completed103.469s; model load20.016s once, synthesis79.922s total. Four cases
passed the mechanical checks, ten generated raw/listening/review WAVs decoded,
retained reference hashes stayed unchanged, owned workspace removed. All four
token roundtrips retain the complete intended text, first token[hi], zero unknowns.
These are input-routing checks, not an audible-language verdict.

| Voice | Passage | Greedy raw seconds | Earlier sampled raw seconds | Synthesis seconds | Listening LUFS | True peak dB |
| --- | --- | --- | --- | --- | --- | --- |
| Sujata | Question | 5.985 | 5.611 | 20.219 | −18.50 | −1.55 |
| Sujata | Meeting/time | 7.425 | 7.094 | 24.860 | −18.01 | −3.40 |
| Abhishek | Question | 4.129 | 5.195 | 14.937 | −17.99 | −3.85 |
| Abhishek | Meeting/time | 5.707 | 5.889 | 19.906 | −17.99 | −3.01 |

Review folder `validation/2026-10-04-greedy-coverage-f0745810/` contains both
references, four raw originals, four gain-only controls and two review montages.
Sujata14.309s and Abhishek10.736s include one900ms listening separator each.
Levels nearly match except Sujata's question0.50LU below the target because
peak headroom takes priority; peak/dynamics are not matched.

Greedy selection shortened the Abhishek examples but lengthened the Sujata
examples versus their sampled controls. It is not a universal timing-fit repair.
User listening remains pending for Hindi-only content, all words, clear openings,
stutter/distortion and natural delivery on these four takes. No default promotion
or full-video success is inferred from file validity or the previously accepted
Abhishek negation. Sujata greedy negation and processed tempo quality remain open.

## Subsequent raw acceptance

User “yes” confirms entirely Hindi/no distortion-stutters/natural delivery in
both raw montages. Exact four-take acceptance recorded in the receipt. Processed
copies require review; see `HINDI_GREEDY_PROCESSING_2026-10-04.md`. No silent
runtime-default promotion or full-video approval.
