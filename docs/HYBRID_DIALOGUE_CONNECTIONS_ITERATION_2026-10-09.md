# Hybrid dialogue configuration and connection adapter — 9 October 2026

## Result and authorization

The user selected an optional hybrid design and authorized continued configuration/connection work. This increment adds a Settings control, stored role selections, scoped text-sharing consent, configuration readiness and a bounded chat-compatible adapter using the existing HTTP and OS credential infrastructure. No package, model, framework or external account was added. No model was downloaded, local inference service launched or paid/live provider request made.

This is configuration and adapter implementation, not an activated automatic quality supervisor. Normal automatic runs and saved cue-review actions are not wired to invoke these connections yet. The UI explicitly says this. The existing active recognition, translation and voice selections remain untouched. A real instruction-following model still needs user selection and live evaluation before activation.

## User controls

The Settings page now presents Dialogue assistance at every experience level. Modes are Off, Local assistance on this computer and Hybrid assistance with selected APIs. Off is the default for existing settings files and new installations. These are assistance-only controls: Local assistance does not override an independently selected cloud recognizer/translator or establish global offline behavior.

Writer and meaning-reviewer dropdowns select installed chat-compatible connections from the existing Translation marketplace. They are independent of the active translator. The same connection can fill both roles, but the UI states that agreement is not independent proof. The chosen connection must specify an explicit service model in its existing request metadata. The adapter does not select a default model.

Hybrid mode includes a text-sharing consent switch describing original/translated dialogue, candidates and timing estimates, possible provider charges, and the absence of video/audio uploads for this feature. Saving a choice or reading readiness performs no HTTP/model requests. Credentials continue to belong to the existing Marketplace connection and OS credential manager. They are not placed in new settings fields or returned by readiness.

The following settings were added: `dialogue_mode` (default `off`), `dialogue_writer_id`, `dialogue_reviewer_id`, `dialogue_text_consent` (default false), and `dialogue_consent_fingerprint`. Type and mode validation use the existing Settings/JsonStore machinery. Existing files can omit all new fields; loading defaults does not rewrite their files. Reset clears the selections and consent through ordinary defaults, without deleting independently stored Marketplace connections/credentials.

## Connection validation and consent scope

`core/dialogue_connections.py` requires installed local/cloud API entries in the Translation stage with the existing `openai_chat` protocol. File models, unsupported/custom protocols, uninstalled entries, missing endpoints and missing explicit model names are rejected. This is a compatibility contract, not a claim that every provider accepts the required JSON-response settings.

URLs must use HTTP(S), contain a host, and have no embedded username/password, query or fragment. Ports are validated. Local assistance permits literal loopback IPs and localhost only; LAN and public endpoints are rejected. Remote connections require HTTPS and a stored credential reference. Actual credential availability is checked at request time, so configuration readiness does not establish that an account/key works.

The bridge computes a consent fingerprint from mode and ordered writer/reviewer connection details, including IDs, labels, normalized endpoints, model names and credential references. It ignores client-supplied fingerprints and derives the value when the user explicitly confirms sharing. Role/mode changes clear old consent. Changes to endpoint/model/connection details invalidate the stored fingerprint even if the entry ID is unchanged; readiness requests confirmation again. The UI displays an unchecked consent control in that state so reconfirmation is possible.

Readiness statuses distinguish off, needs_connection, needs_consent, offline and configured. `configured` means structurally valid and consented, not contacted, available, paid-account-ready or quality-approved. Global `REFLOW_OFFLINE=1` rejects remote assistance while allowing loopback services. No connection is silently replaced by another service or cloud fallback.

The connection resolver accepts a supplied registry/settings snapshot. A future job integration must freeze those values and bind them to review configuration/provenance; this increment does not claim that inactive writer/reviewer selections are already bound into normal pipeline jobs.

## Transport and supervisor interface

New `core/providers/dialogue_chat.py` implements the previously prepared `rewrite_dialogue` and `review_dialogue` interfaces. It reuses `cloud_rest_common.request` and `resolve_credential`, with no new SDK. Loopback services may omit credentials; remote requests require a resolvable stored credential. Endpoint paths support base URLs with or without a trailing `/v1`, avoiding duplicate path segments.

Requests use an explicit model, two chat messages, a JSON-object response contract and bounded output tokens. Source/translation/candidate data are serialized as quoted JSON data; the system instructions tell the service not to treat those contents as instructions. This prompt separation is not an independent semantic guarantee. Only dialogue text and timing payloads supplied by the supervisor are sent; there is no media/file upload code.

The writer requests at most three shorter spoken Hindi variants while preserving negation, facts, names, quantities, tense and tone. It may return an empty list when faithful shortening is impossible. The reviewer receives the original English source, current Hindi translation and candidate IDs/text, and must give one preserved/changed/uncertain opinion with reasons per supplied ID. The existing supervisor validates identities, number/script warnings, predicted fit and the one-writer/one-batch-reviewer budget. Opinions remain advisory, with no automatic acceptance or speech synthesis.

Responses must have one completed chat choice with `finish_reason: stop`, a JSON-object content and the expected candidate/opinion shape. Truncated output, malformed JSON, excess candidates, oversized response bodies and missing credentials fail closed. The decoded HTTP response limit is 65,536 bytes. Responses are closed after parsing or failure; failed requests are not retried or substituted.

The adapter uses a 60-second HTTP read timeout and elapsed-time checks while consuming bytes, with cancellation checks between bytes. One-byte iteration avoids waiting for a large buffered chunk under a slow-drip response. This is not a hard interrupt of an in-progress socket read: an idle read/connection can extend the elapsed deadline until its transport timeout returns, and cancellation is not instantaneous during such a read. Tight hard-deadline cancellation remains a transport hardening item before unattended production activation.

`RunManifest.provider_identity` now records explicit `service_model` and `service_endpoint` fields for this adapter. A recorded model name is the requested alias, not proof of an immutable remote weight revision. Live evaluation must record whatever provider/version evidence is available. Secrets are not part of these fields.

## Validation

Focused configuration/supervision/persistence tests initially passed 59 tests in 31.093 seconds. Additional elapsed-time and missing-credential tests were added before the final complete suite. The initial focused log remains `validation/2026-10-09-hybrid-focused.log`; the final suite provides the final source binding.

`dev/test_dialogue_connections.py` covers defaults/off behavior, independent role selection, explicit models/protocols, local-only endpoint enforcement, HTTPS/credential requirements, consent invalidation after endpoint/model changes, offline behavior, settings consent reset, bridge-computed fingerprints and ignored forged hashes, explicit text-only request shape, reviewer source/IDs, response completion/JSON/size checks, no retry/fallback, credential lookup at request time, `/v1` path handling, elapsed response limits and missing-key rejection.

A test also starts a disposable loopback HTTP server and runs the actual adapter through the supervisor: one writer request and one reviewer request traverse real HTTP, return fixture JSON, preserve the original input and retain `needs_review` plus unapproved candidates. This verifies transport/orchestration only; its fixed responses are not a real Hindi model or a meaningful preservation judgment. The server is stopped and closed in cleanup. No external model API is contacted.

The frontend production build and application-source lint passed. Logs: `validation/2026-10-09-hybrid-frontend-build.log` and `validation/2026-10-09-hybrid-frontend-lint.log`. Existing chunk-size/React warnings remain. Browser interaction was not newly exercised; a successful build is not a visual interaction test.

Final backend results are in `validation/2026-10-09-hybrid-backend-complete.json` and its corresponding full log. The runner discovers all test modules, uses workspace temporary files and records production-source hashes and saved registry/settings integrity. It now accepts a label so this increment does not overwrite the earlier dialogue receipt. Final result: **673 tests across 38 modules passed in 168.922 seconds**, with zero failures/errors and unchanged saved registry/settings and tested production files. The accepted editorial video hash was separately verified unchanged. Expected simulated failure messages in the backend log are fixture paths, not live engine failures.

## Changes and remaining work

Production: new `core/dialogue_connections.py` and `core/providers/dialogue_chat.py`; Settings defaults/validation/consent reset; bridge consent/readiness methods; service identity fields in `core/run_manifest.py`; frontend settings types/readiness wrapper and Dialogue assistance card. Validation: new connection tests, cleanup-suite registration and receipt-label/source-inventory extension in the backend runner. No new production cue-review action or normal pipeline model request was added.

Next: choose and approve a real writer/reviewer service and models; evaluate them on preserved raw source/translation plus independent examples; test negation, technical claims, names/numbers, omitted information, natural Hindi and fit against actual generated speech. Then connect a user-invoked review action with frozen connection identity, bounded correction budget, durable reports and safe failure behavior. Automatic shortening and unattended acceptance remain pending evidence. Acoustic emotion/naturalness is a separate audio evaluation, not something this text reviewer measures.

The accepted editorial Hindi video remains a historical comparison baseline. The new module does not establish arbitrary-video success, provider-wide quality or release readiness. Release remains pending.
