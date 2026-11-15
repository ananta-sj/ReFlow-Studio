# User-supplied Hindi reference comparison — 4 October 2026

## Inputs and purpose

User supplied `C:/Users/19shr/Downloads/Hindi_F_Sujata.mp3` and
`C:/Users/19shr/Downloads/HIN_M_AbhishekS.mp3` after the requested Hindi-reference
control. Both decode and contain signal. Durations17.528s and19.775s; original
formats stereo44.1kHz and mono44.1kHz respectively. Filenames label the samples;
speaker identities and perceptual reference cleanliness are not independently
certified by decoding or level measurements.

The prior longer B take was good initially but slowed from the middle according
to the user. Sentence-boundary normalization subsequently worsened timing and
was not adopted. This experiment changes the reference to the supplied Hindi
recordings rather than applying another speed increase or cutting words.

## Method and preserved behavior

`dev/compare_native_hindi_references.py` copies the supplied sources into an owned
diagnostic workspace and converts each complete recording to mono24kHz WAV.
No guessed mid-sentence cuts, silence trimming, reference EQ or normalization.
Both full references are below the installed model's30-second conditioning cap.
The complete files differ in content, speaker, duration and delivery: a preference
does not isolate language alone as the cause.

Generate the same passage:
“आज हम इस वीडियो की आवाज़ और अनुवाद की गुणवत्ता जाँच रहे हैं। हर शब्द साफ़ सुनाई देना चाहिए।”
Offline CPU XTTS, seed1234, temperature0.90, synthesis speed1.0, original sentence
punctuation and existing sentence splitting. Model loaded once for both cases;
Python/NumPy/Torch seeds reset before each. Existing mastering and approved
1.342× pitch-preserving Hindi pace applied identically. No production profile,
reference policy, checkpoint, provider cache or accepted media changed.

Keep source MP3 copies, prepared WAV references, raw/mastered and listening takes.
Hash inputs before preparation and again before publication to confirm original
files unchanged. Durable diagnostics are separate from user production reviews;
do not package reference recordings as default voices based on this experiment.
No new engine, library, framework or model download.

## Evidence and listening gate

Receipt: `validation/2026-10-04-native-hindi.json`; execution log:
`validation/2026-10-04-native-hindi.log`. Publication/decoding/timing establish
execution only. Check words, naturalness throughout, mid-passage pace, endings,
speaker consistency and artifacts through listening. Do not equate shorter
duration with natural speech or successful translation. The input passage is a
diagnostic quality sentence, not the suspect recognized news transcript.

If either reference is preferred, validate varied text before changing production
defaults. Reference selection should remain an explicit user choice; this run
does not authorize bundling the supplied voices into releases. Previous English
and selected Hindi approvals remain specific to their recorded cases.

## Completed execution

Completed in **186.453 seconds**, with one model load of **38.125 seconds**.

| Reference | Raw output | Listening output at approved pace | Synthesis time |
| --- | --- | --- | --- |
| Sujata | 9.393 s | 6.987 s | 74.532 s |
| Abhishek | 7.327 s | 5.445 s | 63.454 s |

Files: `validation/2026-10-04-native-hindi-1033704b/`. Source files hash-match
before and after execution; originals unchanged. Both prepared references retain
complete source duration. All generated WAVs decode and contain signal, temporary
workspace removed, whitespace diff check passes. Existing original punctuation
still produces one engine split entry; the negative boundary normalization route
was deliberately not used in this reference control.

Listening acceptance is pending. Shorter Abhishek output is not evidence of
better quality or more accurate words by itself. Ask the user to compare the
middle and final sentence as well as the overall naturalness of both takes.
Voice/source content differ, so this cannot isolate reference language alone.
No new fully corrected media render, resource-estimate calibration, production
profile or video integration resulted. Backend/frontend unchanged; prior tests
are retained rather than rerun or portrayed as listening acceptance.

Subsequent user feedback: “both... but there seems to be little presence of noise
or distorsion”. Both positively received relative to prior alternatives, with
residual noise/distortion; neither is final defect-free acceptance. Recorded in
the receipt. Next comparison reuses exact raw synthesis without added EQ and
compression, preserving pace and reference. See HINDI_NOISE_REVIEW_2026-10-04.md.
