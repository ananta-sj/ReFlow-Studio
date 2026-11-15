# Dialogue reviewer evidence repair — 2026-10-16

Status: **implementation, 98 focused tests, 954 full backend tests, frontend build and preservation audit passed**. This is a development iteration using deterministic fixtures and recorded outputs. It does not repeat the removed temporary model evaluation or establish new live model quality.

## Problem addressed

The preceding Qwen3 evaluation exposed a reviewer that rejected plausible paraphrases based on changes of structure or vocabulary, misidentified supplied words, and accepted effectively unshortened wording. The selected speech take remained 6.606 seconds against a six-second window. That outcome is retained in `TEMPORARY_DIALOGUE_MODEL_EVALUATION_2026-10-16.md`; this iteration does not relabel it as a success.

The previous reviewer interface accepted a status and free-text reasons alone. It had no mechanical way to reject a reason that cited nonexistent source/candidate wording. New production dialogue reviews now require bounded paired quotations, which the application checks before saving the opinion.

## Changes and rationale

### Reviewer and writer instructions

`core/providers/dialogue_chat.py` advertises the `quoted-spans.v1` review protocol. The reviewer instruction separates the original English source from current wording and explicitly permits faithful synonyms, word order, contractions and punctuation changes. It asks about changed claims, negation, quantities, names, tense, tone and clarity rather than identical wording. It uses “did not approve” versus “rejected” as an example of a potentially substantive distinction. Timing is explicitly outside the meaning judgment.

The writer instruction now discourages returning the full source as a supposedly shorter alternative and forbids inventing an ending to an incomplete source. The application still does not treat character count as a verified duration or assume the model obeys these instructions. Both changes are instructions, not demonstrated improvements in live model quality; no new inference was performed.

Each reviewed candidate must carry one to three evidence pairs with exact `source_quote`, exact `candidate_quote`, and one of `equivalent`, `changed`, `omitted`, `added`, or `uncertain`. The prompt asks for one or two short decisive pairs and one concise reason to limit response size. Existing three-candidate, two-request, timeout and response-size limits remain.

### Quote validation

New `core/dialogue_evidence.py` checks:

- Quotes occur in the actual original source and the corresponding candidate, rather than another candidate or the current translation.
- Quotes do not exceed 240 characters; evidence lists are bounded; duplicate, blank and malformed pairs fail validation.
- A word or number fragment cannot masquerade as a supplied word. For example, “any” alone is not valid evidence from “anyone”, and “42” is not valid evidence from “420”. Unicode letters, combining marks, digits and joiners are included in boundary checks so ordinary Hindi words are covered too.
- Equivalence/change/uncertainty pairs require both quotes. Omission requires a source quote with an empty candidate counterpart; addition requires the reverse. Empty counterparts mean no counterpart was cited; they do not prove absence.
- A preserved opinion can cite only equivalent relations. Changed opinions must cite at least one changed/added/omitted relation; uncertain opinions must include uncertain evidence. These are consistency checks on the returned structure, not semantic proof.

The orchestration in `core/dialogue_supervision.py` applies this validation before an opinion can be published. Missing/invented/mismatched evidence fails the explicit operation without retrying, substituting a provider, editing wording or changing an accepted take. Invalid opinion IDs and the existing meaning-reason bounds still fail closed.

### Saved evidence and compatibility

Grounded predicted-duration reports use schema version 3; grounded measured-take reports use version 4. They require the new protocol marker and preserve `meaning_evidence` for each candidate. Removing the marker/evidence, changing a quote, or contradicting its declared relation causes saved validation to fail. Measured candidates still have null predicted duration and null fit until new speech is actually generated.

Historical version 1/2 reports remain readable as ungrounded advisory history. They cannot contain evidence presented as checked under the new protocol. Existing generic fixture/legacy reviewer adapters retain that historical route; production connection resolution uses `DialogueChatProvider`, which declares the grounded protocol. No default or connection is silently upgraded to a different service.

`core/cue_review.py` clears both old and new measured-review reports on regeneration, while existing edit/timing invalidation remains. `frontend/src/lib/api.ts` describes the optional evidence fields for compatibility. `frontend/src/components/shared/CueReviewPanel.tsx` displays the source quotation, suggested-wording quotation and declared relation as text, with an explicit reminder that meaning still needs review. Older reviews with critic results show a warning that their quotations were not checked. Selecting a suggestion remains a user edit followed by new speech generation, not audio acceptance.

## Verification

- Final focused suite: **98 tests passed in 29.205 seconds**. Log: `validation/2026-10-16-dialogue-evidence-focused-final.log`. The earlier 97-test pass is retained; the additional test covers word/number/Hindi fragment boundaries.
- Frontend type-check and production build passed. Log: `validation/2026-10-16-dialogue-evidence-frontend.log`. Existing bundle-size/plugin-time warnings remain advisory.
- New `dev/test_dialogue_evidence.py` covers valid paraphrase quotations, missing/invented quotations, wrong-candidate quotations, distinct omission/addition/uncertainty relations, contradictory statuses, tampered saved evidence/protocol, regeneration invalidation and preservation of the previous review on failure.
- Real loopback HTTP fixtures in the existing connection/review tests now return the grounded response structure. They exercise the actual transport, orchestration and saved-review path without an external provider. Their meaning verdicts are fixture values and are not semantic accuracy measurements.
- A deliberate test shows the limit: real quotations can still be paired with a false equivalence claim. Therefore quotations never imply semantic approval, and human review remains mandatory.
- Full suite: **954 tests passed**, zero errors/failures. Combined suite and final audit took **189.891 seconds**. Receipt: `validation/2026-10-16-dialogue-evidence-acceptance.json`; log: `validation/2026-10-16-dialogue-evidence-backend.log`; verifier: `dev/verify_dialogue_evidence_iteration.py`.
- Captured backend/test sources and built frontend remained unchanged during the audit. The five protected app-state files, six established runtime identities and all eight original XTTS assets matched their baselines. The previous evaluation's owned Ollama/model directory remained absent.
- All **14** reviewed opinions from the historical model run lacked checked evidence and were rejected when evaluated against the new protocol. The historical record itself was preserved and remains readable as history. This is a response-contract replay, not a new inference or a measured improvement in semantic accuracy.

Test counts overlap and must not be added together. No package, model, framework or driver was installed; no live inference, paid call or new speech generation was performed. The temporary Ollama/model removal remains in effect. The frontend production bundle was rebuilt because the displayed review evidence changed.

## Limits and next validation

These checks prove that cited spans come from the supplied texts and that returned statuses follow the declared evidence structure. They cannot prove a reason is truthful, the quotations cover every claim, the target language sounds natural, or the speech will fit. A model may still select real but unhelpful quotations or misjudge equivalence. Replaying old unquoted outputs establishes only that they fail the new interface; it does not show a model will produce better judgments with the new prompt.

The six-second diagnostic remains unresolved. Live quality validation of this new contract still requires a user-connected instruction backend or a separately approved temporary evaluation. Existing speech speed limits, review requirements and source timing are preserved. Broader video workflow, engine coverage, clean-machine and licensing release gates remain open. No release-ready claim is made.
