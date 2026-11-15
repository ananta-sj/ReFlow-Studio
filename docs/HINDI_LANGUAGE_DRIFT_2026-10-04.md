# Abhishek Hindi raw-take language failure and greedy control

## Observed failure

The user reports: “Abhishek has a different lang followed by hindi” when hearing
the exact raw negation control. That control derives from the rejected batch's
8.214s synthesis of “यह रिपोर्ट अभी पूरी नहीं हुई है।” It has only comparison
gain attenuation, no tempo/loudness normalization/EQ/compression. Thus this
reported incorrect-language opening already exists at the synthesis stage;
post-processing is not required for this failure. The other language has not
been identified independently, and an accent/phonetic failure is not ruled out.
Either way, the intended Hindi-only utterance failed human review.

The original generation call explicitly used language='hi' with Hindi text.
No translated source text, source-language auto-detection or frontend language
switch participated in this diagnostic. Raw-control receipt records rejection
of this Abhishek take. The user gave no new Sujata raw verdict in this message;
do not infer acceptance or rejection of that control. Previous montage rejection
and previously accepted exact examples remain distinct.

## Bounded synthesis control

`dev/diagnose_hindi_language_drift.py` generates one Abhishek control using the
exact retained reference and input text. The only intended decoding change is
do_sample=False, num_beams=1: greedy selection rather than random sampling.
Native sample rate remains24000Hz, generation speed1.0, reference preparation
unchanged, seed1234 reset for comparable bookkeeping. The explicit temperature
argument remains0.90 but is inactive in greedy decoding; top-k/top-p also do
not select candidates in this mode. Repetition penalty and model config are
unchanged. This is not a new production setting or a claimed naturalness fix.

The driver records the tokenizer's first token, full decoded token roundtrip,
unknown count and loaded writer rate. Valid Hindi input tokens establish correct
model input routing, not a guarantee of Hindi speech. Greedy output may still
mispronounce, repeat, hallucinate or sound less natural. No leading words are
trimmed to hide a failure, and no unrelated segment is spliced in.

Raw candidate and a gain-only listening copy are retained. No output loudness
normalization, tempo, EQ/compression, fade, gate or word cutting. Peak-constrained
gain aims−18LUFS; actual level is recorded, not assumed matched. Original reference
and rejected raw hashes must match before/after generation; output must contain
signal, decode fully at native mono format, preserve exact duration through
listening gain and remain within true-peak tolerance. Owned workspace removed.

Receipt/log `validation/2026-10-04-hindi-greedy.json` / `.log`. Completed measurements
are appended below. Mechanical checks cannot certify spoken language or preserved
negation. Listening is required before treating this as a successful candidate.

Only diagnostic code, receipts, media and docs changed. No production defaults,
new package/framework/model/download. Previous490 backend checks retained,
not rerun for this bounded diagnostic. Hindi reliability, full-video, cue fit and
source semantics remain release blockers. No commit, push or release.

## Completed result

The tokenizer starts with `[hi]`, its20 tokens include zero unknowns, and its
decoded roundtrip preserves `[hi]यह रिपोर्ट अभी पूरी नहीं हुई है।`. The loaded
writer reports24000Hz. These confirm Hindi input routing, not generated speech
correctness. Total81.703s, synthesis42.344s, owned workspace removed.

Greedy synthesis produces4.545s raw versus the rejected sampled8.214s. No word
or leading audio is cut; listening copy preserves the full4.545s waveform.
Gain−2.81dB yields−18.01LUFS and−2.81dBTP, close to the rejected raw control's
−17.99LUFS while peak/dynamics differ. Decode/signal/exact duration/native format/
peak/unchanged-original-hash checks pass.

Output `validation/2026-10-04-hindi-greedy-e59ab24c/` holds reference, untouched
greedy raw and gain-only listening copy. Shorter duration is not a language
success criterion. Human Hindi-only/negation/intelligibility/naturalness review
remains pending. No production profile or earlier accepted take is changed.

## Subsequent listening acceptance

The user answered “yes” when asked whether this exact take starts directly in
Hindi, preserves every word and avoids stuttering. The receipt records this
specific language/content/fluency acceptance and the presented WAV's hash.
This does not certify varied-text reliability, complete naturalness, processed
tempo quality or a final video. Greedy selection remains a diagnostic candidate;
production defaults are unchanged. Validate other previously rejected passages
before promoting a decoding setting, including Sujata separately.
