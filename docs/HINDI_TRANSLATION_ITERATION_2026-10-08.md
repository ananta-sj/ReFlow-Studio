# Hindi translation quality and completion — 8 October 2026

## Scope and current result

The user authorized continuing after accepting absence of original English
leakage in the background-enabled Hindi video. Work started on 6 October and
resumed on 8 October. The accepted speech/reference/mixing settings are unchanged.
No new model, dependency, service or framework was installed. No user model
selection, registry entry or credential was changed.

Local NLLB decoding changes did not resolve the known film terminology and
sarcasm failures. Wider beam search or a length penalty must not be promoted as
a semantic-quality fix. Implemented repairs reject oversized or mechanically
unfinished translation output, and let a user combine adjacent review phrases
before retranslating a complete sentence. These improve integrity and editing;
they do not establish automatic Hindi meaning/tone fidelity.

## Controlled NLLB experiment

Helper: `dev/compare_hindi_translation_context.py`.
Receipt: `docs/validation/2026-10-06-hindi-translation-context-d0ec32ce.json`.
Log: `docs/validation/2026-10-06-hindi-translation-context.log`.

Existing local `facebook/nllb-200-distilled-600M` was evaluated offline on the
already approved GPU evaluation runtime. Eight source cases used three settings:
five beams/length penalty 1.0 (production baseline), five beams/1.2, and eight
beams/1.2. Five cases are complete source-video sentences and three exercise
negation, a date/time and amounts. Four original narration fragments were also
translated with the baseline. Total: 28 generations, 98.578 seconds after
helper imports; owned workspace removed. Source wording remained unchanged,
including the previously confirmed unusual report phrase in the source receipt.

Concrete observations from reviewing the retained outputs:

- “Lacklustre establishing shot” stays an unclear “अस्पष्ट स्थापित तस्वीर” or
  “अस्पष्ट स्थापना शॉट” across variants. Widening decoding changes words without
  resolving the film term.
- The long sarcastic narration is identical across all three settings, including
  the bad choices “कुतियाओं” and “गंदगी मैट्रिक्स”. Complete context alone does
  not correct this model's lexical decisions.
- Length penalty 1.2 changes “babbles on about facts” to wording using “भौंकती”
  (barks), making that candidate less faithful.
- Wider decoding improves the explicit “slows to a halt” clause in one sentence,
  but leaves other errors. This isolated improvement does not justify a global
  default change.
- “Faces subtly framed out” remains wording about faces being prepared/framed,
  missing that faces are excluded from the image. All variants retain “Vox Pops”
  without explaining that technical term.
- The short negation, date/time and amount examples retain their critical
  information in this small comparison. This is an engineering observation,
  not user acceptance or broad model certification.

Production NLLB's five-beam deterministic decoding remains unchanged. Neither
this receipt nor the editorial script should be presented as an automatic
translation quality pass.

## Completion repairs

New `core/translation_completion.py` checks actual input token count against
the model's declared `max_position_embeddings`, requires one valid generated
sequence ending with its real EOS token, and rejects generation reaching the
configured output cap even when a forced EOS is present. Trailing pad tokens
are allowed. Missing/invalid checkpoint limits or end tokens are explicit
errors. The policy is conservative: a translation naturally ending exactly at
the cap is also rejected, since that boundary cannot safely prove completion.

`core/providers/translation/nllb_local.py` explicitly disables tokenizer
truncation, performs both checks, and retains its 512-new-token cap and existing
decoding. `core/llm_translator.py` applies equivalent checks to M2M100 and sets
an explicit 512-new-token cap rather than inheriting its shorter generation
default. Error messages tell the user to split the source into complete
sentences. No partial result is substituted or silently returned as success.
These checks prove mechanical completion, not preservation of all source
clauses, emotion, negation or nuance.

Live checks used three short sources per engine and deliberately oversized
input plus a four-token generation ending. Both models correctly generated
normal nonempty translations, rejected the input beyond their 1024-token
windows and rejected forced output-cap endings.

- NLLB: `docs/validation/2026-10-08-translation-completion-live-86c17cad.json`,
  GPU. Its section passed, but the overall receipt is false: the subsequent
  M2M100 attempt in the IndicF5 evaluation runtime failed because that runtime
  lacks SentencePiece. The failed attempt and log are retained. No dependency
  was installed to repair an unrelated evaluation environment.
- M2M100: rerun on the existing core CPU runtime, which already contains the
  required tokenizer library. Successful receipt:
  `docs/validation/2026-10-08-translation-completion-live-0d79f5fd.json`;
  log `docs/validation/2026-10-08-m2m100-completion-live.log`.
- Helper: `dev/verify_translation_completion.py`, with engine-specific choice
  to respect runtime separation. M2M100 still mistranslated the film-term case.

## Review workspace changes

`core/cue_review.py` adds revision-checked `ReviewStore.combine`: combine the
selected cue with the next one, preserve the first start/second end and the
full available speech window, join both source and draft translations, and
clear only those two cues' candidate/accepted takes. Other cues and their
accepted audio remain unchanged. Source/background/reference assets are reused,
never overwritten. The combined line must span at most 30 seconds and each text
must stay within 4000 characters. Invalid last-line/index, stale revision and
size failures do not publish a changed record. Existing cancellation and
cross-process save locks remain in force.

`bridge/api.py` exposes `combine_review_cues` with the existing idle-work lock
and busy guard. `frontend/src/lib/api.ts` adds its typed method.
`frontend/src/components/shared/CueReviewPanel.tsx` adds “Combine with next
phrase”, disabled for unsaved edits, active work or the last line. The hint
explains take invalidation and the need to retranslate/review. Combining does
not itself rewrite Hindi or infer speaker changes; this workspace remains
single-voice audio review. The video dubbing pipeline does not automatically
inherit these manual review edits.

## Regression evidence and repaired test issues

- 99 completion, translation integrity and source-language checks passed in
  152.465 seconds: `docs/validation/2026-10-08-translation-completion-tests.log`.
- Final 22 cue-review/completion checks passed in 48.051 seconds:
  `docs/validation/2026-10-08-translation-review-tests-final.log`.
- Production frontend TypeScript/Vite build passed. The existing bundle-size
  advisory remains; browser visual interaction was not checked here.
- `dev/test_translation_completion.py` tests oversized source rejection, missing
  limits, padded EOS, unfinished output, forced EOS at the cap and malformed
  tokens. Existing mocked-model fixtures in `dev/test_translation_integrity.py`
  and `dev/test_source_language.py` now declare real limits/EOS and completed
  sequences instead of relying on unrestricted mocks.
- `dev/test_cue_review.py` tests timing/gap preservation, exact retention of an
  unrelated accepted take, invalidation of affected takes, stale revisions,
  text limits and bridge busy guards. Its existing process-race test now allows
  30 seconds for rendezvous and 60 seconds for process completion; the original
  20-second completion timeout expired under cold imports/concurrent evaluation.
  The assertions still require exactly one successful competing revision save.
- Initial review runs failed because new fixture setup omitted the required
  expected revision, and then compared a public take (which deliberately omits
  file/hash) to the full persisted take. Fixture setup/assertions were corrected;
  production locking and public-data filtering were preserved. Failed logs:
  `2026-10-08-translation-review-tests.log` and
  `2026-10-08-translation-review-tests-retry.log` under `docs/validation`.

## Next translation evaluation: proposal requiring approval

An isolated comparison of AI4Bharat's IndicTrans2 English-to-Indic 1.1B model
would test a different translation model against the same difficult passages,
negation/numbers and new held-out conversational material. This is a candidate,
not an established improvement. It translates text; IndicF5 remains the speech
engine. The official model card demonstrates English-to-Hindi and requires
separate gated model-access agreement/contact sharing. Its inference path uses
IndicTransToolkit plus model-specific code. [Official model card](https://huggingface.co/ai4bharat/indictrans2-en-indic-1B).

The current toolkit documents Python 3.10+, Linux/macOS and explicitly states
Windows is not built/tested/supported. Therefore feasibility on this Windows
machine must be established before installing it. Required dependency versions
would be resolved in a separate optional runtime; no upgrade of the accepted
core/IndicF5 runtime is proposed. Any different operating-system runtime would
require explicit approval. [Official toolkit prerequisites](https://github.com/VarunGumma/IndicTransToolkit).

Approval scope proposed: Windows feasibility research first, then a separate
local evaluation runtime, the named model and required processor/tokenizer
packages if a compatible route is established. Expect several GB of extra
storage/downloads; exact manifests and revisions must be pinned before
installation. No automatic replacement, fine-tuning, new cloud service or
universal any-language claim. Other non-English source languages would need a
separate validated route. Promotion requires demonstrated meaning/tone quality,
runtime/timing/cleanup checks and human review.
