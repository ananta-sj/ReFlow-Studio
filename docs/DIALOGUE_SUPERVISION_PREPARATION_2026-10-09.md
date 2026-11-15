# Dialogue supervision preparation and model options — 9 October 2026

## Current decision

The user requested continued pipeline development, then chose “Discuss the options first” when asked which model connection should supply dialogue rewriting. No model installation, API connection, service launch or model download is authorized by that preference. Implementation dependent on a selected service remains pending discussion. No new package or framework was installed, and the active model registry/settings were not changed.

The existing selected translator supplies deterministic IndicTrans2 translation and alternative beams, but its exposed route has no instruction-following dialogue-rewrite interface. The previous real evaluation found no fitting alternatives for the first three conflicts. Repeating those beam requests would not establish automatic shortening or meaning preservation.

The existing local Ollama endpoint was checked read-only at `http://localhost:11434/api/tags`. The first sandbox probe was denied socket access; the approved read-only probe outside that restriction received Windows connection-refused error 10061. This is evidence that this local endpoint was unavailable at check time, not evidence that all local inference is impossible. No API entry was connected in the saved registry. The service/model must be explicitly chosen before real-model evaluation.

## Code prepared within the existing architecture

New `core/dialogue_supervision.py` provides a service-neutral orchestration contract. It takes the current native speech estimator plus explicitly supplied writer/reviewer objects. It is not connected to the normal pipeline or UI yet. It performs no provider discovery, installation, request transport or fallback. A future adapter must implement its service deadlines, response limits, credentials and network policy. Request-count bounds here do not constitute wall-clock deadlines.

The supported initial contract is English source to Hindi target. It retains source and current translation in a versioned report and calculates the original timing prediction. A fitting original spends no model queries. An overflowing original permits one writer call with source, translation, available time, predicted current duration and a maximum of three variants. Invalid/empty/oversized text, excess variants and malformed output are rejected. Exact duplicates and unchanged wording are removed.

Each remaining variant receives a native timing prediction. Variants with no Devanagari characters or changed numeric sequences carry objective risk warnings. These are limited heuristics: Devanagari presence does not prove Hindi correctness; unchanged numbers do not prove preserved meaning; spelled-out quantities and script variants may need manual review. No claim of complete language/semantic detection is made.

Only predicted-fitting variants without those warnings are sent to one batch reviewer call. That call receives the original English source, existing Hindi translation and immutable candidate identifiers/text. Exactly one opinion must return for each candidate. Unknown, missing or duplicate identities, invalid status, empty/unbounded explanation lists and malformed responses fail closed. Supported model opinions are `preserved`, `changed` and `uncertain`.

A preserved opinion still leaves the report `needs_review`, with `auto_rewrite: false`, `human_review_required: true` and every candidate `approved: false`. The model's opinion is evidence to inspect, not authoritative proof. The original wording is never replaced, and no speech is synthesized. Changed/uncertain opinions cannot become preferred approved takes. No retry loop is implemented.

When supplied, a real `RunManifest` saves writer/reviewer operations and publishes the quality report through the existing atomic publisher. Failed service calls propagate and remain failed operations. Provider identities are recorded at the abstraction level available from the supplied objects; actual pinned service/model/configuration bindings remain the responsibility of a future connected adapter.

## Validation

`dev/test_dialogue_supervision.py` adds 14 tests. Together with the existing nine dialogue-assessment tests, **23 focused tests passed** in 0.313 seconds with zero failures/errors. The tests cover advisory-only preserved opinions, no calls for fitting originals, duplicate handling, overflow/script/number warning exclusion, changed/uncertain opinions, invalid/mismatched/duplicate critic identities, writer budget violations, unsupported routes, missing services, no retry/fallback, cancellation, operation/report calls and publication through a real durable manifest.

Receipt: `validation/2026-10-09-dialogue-supervision-focused.json`; detailed log: corresponding `.log`. Tested-source and saved registry/settings hashes were unchanged during this run. These are fixture and durable-publication tests. No live rewriting/reviewer model was invoked. The previous 641-test full backend result still belongs to the prior increment; it is not relabeled as validation of this new module. Existing frontend behavior did not change. The cleanup-check runner now includes the new supervision tests.

## Options for the discussion

1. Local Ollama model: optional separate local service and an explicitly chosen model. Keeps dialogue on the machine after downloads, but adds disk/runtime requirements and competes for GPU memory with recognition, translation and speech. The intended scheduler would release one stage before loading the next; simultaneous residency is not promised.
2. Existing API: supply the user's selected endpoint, model and credential reference. Adds provider usage charges and sends the dialogue text to that provider. Video/audio upload is unnecessary for this text-only rewrite/review step. An API may offer a larger model, but task quality still needs direct evaluation.
3. Optional hybrid: keep recognition, translation and speech local; allow cloud rewriting/review only when explicitly enabled. If it is unavailable or declined, retain a needs-review state. No silent cloud fallback.

Current primary-source candidates checked for discussion on 9 October 2026:

- [Qwen3 4B through Ollama](https://ollama.com/library/qwen3:4b): text model, listed Q4_K_M download 2.5 GB. This is a practical small initial evaluation candidate, not a proven Hindi shortening/critic engine for ReFlow.
- [Qwen3.5 4B through Ollama](https://ollama.com/library/qwen3.5:4b): newer multimodal candidate, current tag lists 4.0 GB. Its text behavior can be evaluated, but vision capability is unnecessary for this dialogue-only stage.
- [Official Qwen3.5 4B card](https://huggingface.co/Qwen/Qwen3.5-4B): documents instruct/non-thinking configuration. Advertised model-family benchmarks do not establish these small variants' performance on ReFlow's Hindi cues.

Download sizes are tag-specific observations and exclude Ollama, runtime buffers and context memory. Local fit, speed and Hindi quality require a measured test on the actual machine. The proposed first local comparison would use a pinned tag/digest, limited context and isolated evaluation without switching the active translator/voice. Specific installation awaits user agreement.

## Next acceptance evidence

After choosing a service, connect a bounded adapter and validate real original-source/translation pairs, including negation, named entities, numbers, tense, technical claims and natural spoken phrasing. Record completion and response limits, service/model identity and unchanged originals. Measure native estimates against actual generated speech. Include independent videos and negative/adversarial examples rather than treating the accepted editorial sample as automatic validation.

The reviewer may share a model with the writer initially in separate calls, but their errors can be correlated. Neither separate calls nor a model agreeing with itself establishes independent correctness. Human review remains required until an evaluation supports any narrowly defined automatic policy. Acoustic naturalness/emotion needs a separate audio evaluation; this text supervisor does not listen to generated audio. Training a proprietary SLM remains deferred.
