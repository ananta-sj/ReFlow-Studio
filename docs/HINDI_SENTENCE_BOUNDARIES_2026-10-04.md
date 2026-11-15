# Hindi sentence boundary listening control — 4 October 2026

User feedback on the longer temperature-0.90 take:
“B... was good untill mid.. then it was slowed”. Opening is preferred, but the
whole passage is not accepted. Feedback is recorded in the long-passage receipt.
No universal pace increase, time cut or default sampling change follows.

## Concrete observation

The installed TTS synthesizer initializes an English sentence segmenter.
Despite `split_sentences=True`, the previous Hindi input with danda punctuation
(`।`) was logged as one entry, containing both sentences. The setting therefore
did not create the intended two sentence-level generation calls for this text.
This is a boundary-handling limitation; it does not prove the cause of the
reported mid-passage slowdown or establish a word-level slowdown timestamp.

## Controlled diagnostic

`dev/compare_long_hindi_delivery.py --sentence-boundaries` maps danda to periods
only in the engine input, preserving the displayed/source text and every word.
Assert that the installed segmenter produces exactly two entries, then use the
existing engine's sentence synthesis/concatenation route. Compare against the
previous longer B take. Temperature0.90, seed1234, reference, synthesis speed,
mastering and approved1.342 pace remain the same. The seed is reset once before
the generation call, not separately for each sentence.

Punctuation normalization and resulting sentence generation boundaries are the
joint intervention. They can also affect pronunciation and sampling sequence;
the experiment cannot attribute any preference to one internal mechanism alone.
The engine supplies its existing inter-sentence silence; no new custom pause,
word trimming, timing-window change or end-of-phrase acceleration is added.
No installed package, model, production wrapper or global text policy is changed.

Receipts/log use `2026-10-04-hindi-boundaries` names; prior takes and receipts
remain preserved. Raw/mastered/listening candidate and previous B are kept in a
new owned directory. Required listening checks: naturalness through both halves,
sentence pause, complete words and ending. Successful splitting or shorter output
alone cannot establish those. Production rollout requires listening acceptance
and more varied text. The current release remains unready.

## Negative timing result

Execution completed in **145.547 seconds**, model load37.250s,
synthesis100.750s. Exactly two sentences were confirmed before inference.
Raw duration13.933s; final10.368s versus the previous B6.565s. The boundary route
therefore worsens total timing in this case and is not promoted. No human
naturalness/intelligibility acceptance exists for this candidate.

At a -45dBFS activity threshold with minimum100ms quiet windows, baseline activity
is5.960s and candidate activity9.290s. Candidate spans are0–4.310s,
4.760–5.930s and6.120–9.930s. This suggests the increase is not solely the
inter-sentence silence. Threshold activity is not a word alignment, semantic
transcript or proof of perceived speech rate. The receipt retains the audit.

Artifacts: `validation/2026-10-04-hindi-boundaries-2d1097a6/`. Decoding/signal,
explicit two-sentence assertion, cleanup and whitespace checks passed. No
production code changed; prior regression receipts remain scoped to their
existing behavior. No successful fix or measured naturalness improvement claimed.

Next useful reference control: a short human-spoken Hindi clip with clear,
natural delivery. Current comparisons all condition on English source audio;
that may contribute to cross-language prosody but has not been proven causal.
No independently reviewed human Hindi reference was located in the known
validation/assets inventory. Do not use rejected AI speech as a ground-truth
reference or keep increasing tempo to conceal delivery problems. Request a
6–12-second suitable reference before that dependent test; current short B
preference remains limited to that short reading.
