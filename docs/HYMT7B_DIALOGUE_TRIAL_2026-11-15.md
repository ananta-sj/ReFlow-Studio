# Larger dialogue-model trial

The approved isolated HY-MT1.5-7B Q4 trial downloaded 4,624,649,312 bytes and matched SHA-256 `fc87637e4dd29547811a28170770c2ac17725fb7690b7c4aafa4f463c3e77568`. It reuses the existing portable runner. Active application models were not replaced.

The official pinned artifact is from `tencent/HY-MT1.5-7B-GGUF`, revision `126325496bc8e3575f1d8615b8ca951d8483f206`. The preparation receipt and raw outputs are retained locally under `docs/validation`; they are excluded from source publication.

## Quality findings

- Contextual English-caption translation preserved the explicit geography and family relation that the smaller model lost. Some first-person grammar and conversational register remained awkward, and several translations were long for the source windows.
- A separate conversational, duration-budget trial did not reliably shorten dialogue. It also lost the geographic direction again. The new narrow fact alarm caught that omission; absence of an alarm on other lines is not general semantic approval.
- Direct Japanese translation recovered the urgency idiom and passed basic negation/relationship controls, but changed the mother's family reference and made her address another mother in a first-person line. This route was not accepted for episode dubbing.
- A separate draft-rewrite test on the mother's Europe line still exceeded its requested word budget and retained unnatural phrasing. The MT model is not established as a reliable dialogue adapter.

The scene roles and female grammatical context were supplied as known test fixtures. These tests do not prove automatic role identification or natural acting. The experimental multi-prototype voice comparison also produced no improvement over the existing conservative held-out result; it was not adopted.

## Real speech and operational findings

One correctly matched daughter turn generated 6.114 seconds of speech in a 7.09-second source window. Its first cold call took about 260 seconds, including model startup. The mother's first take still exceeded the allowed window after the existing speed limit. Its alternate then exposed a Windows sharing/access denial while reading a worker request. No accepted scene or episode was exported.

Worker reads and response publication now use bounded sharing-lock retries. Consumed-sidecar cleanup cannot discard a successful inference result. A real Windows exclusive-lock test passed. Separation and recognition no longer import the translation library just to construct an unused stopping callback.

All four actual GPU stages were reverified after these worker changes. The dedicated speaker runtime was also reverified against the updated GPU identity. This proves runtime operation, not successful episode quality.

The saved review first pass now commits each checked line, keeps an isolated failure as a review decision while proceeding, and stops after three consecutive actual engine failures. Over-budget speech is a line-level timing decision and does not trigger that engine circuit breaker.

## Remaining acceptance work

The software still needs a reliable dialogue-adaptation route, more complete character coverage, and a continuous multi-character listening test before a complete episode can be accepted. Full-episode/movie readiness and failure-free operation have not been established. Do not enable an unaccepted candidate or publish an episode-ready release based only on unit tests or successful GPU loading.
