# IndicTrans2 evaluation preparation — 8 October 2026

## Scope and authorization

The user approved evaluating AI4Bharat IndicTrans2 and installing required packages in a separate environment. The user subsequently reported accepting the English-to-Indic model's access conditions. Acceptance was performed by the user, not by the agent. This iteration prepares compatibility checks; it does not replace production translation, voice models, or model defaults.

## Current result

Initial checks returned HTTP 403 with `X-Error-Code: GatedRepo`, including a request bypassing caches. Inspecting the open IndicTrans2 tab then showed an unaccepted access form. After the user clicked the agreement button, the browser explicitly showed access granted and the saved local login's pinned configuration request succeeded. The access blocker is resolved; no credential refresh was necessary.

Repository: `ai4bharat/indictrans2-en-indic-1B`.
Pinned revision: `89cd0007fd7b9e0693a2fd4404d187e07dac79fd`.
Credentials were read from the existing workspace authentication location. Tokens were not printed, copied to documentation, or requested in chat.

The pinned model configuration, tokenizer assets, MIT license, and Python source have now downloaded with size/hash receipts. Static inspection found local vocabulary file operations in the tokenizer and model/Transformers/Torch imports, without subprocess or network calls in the model implementation. Reviewed custom model code is loaded only from the pinned local directory in offline evaluation. The safetensors download and subsequent actual comparison have their own receipts; inspect their `complete`/`completed` fields rather than assuming success from preparation. Duplicate pickle weights are excluded.

## Windows compatibility route

Current IndicTransToolkit 1.1.1 has Linux/macOS wheels and a source distribution, but no Windows wheel in the inspected package metadata. Its current processor is compiled with Cython; no MSVC installation was found. Installing a compiler or changing the OS was not authorized or attempted.

An earlier upstream pure-Python processor was retrieved and inspected as an evaluation-only alternative:

- Source repository: `VarunGumma/IndicTransToolkit`.
- Revision: `0c607654e8b6cce897a32039df79018a1daff4e2`.
- Processor SHA256: `354c3299229f8b05602d82d0a84a8c2e98082dce38879a3459ca2fc33ec8f7b8`.
- MIT license SHA256: `3be0a01dffc3eda371f1532a50116384d3b51695dbe30068c67419aa0923a715`.
- The original processor, license, setup file, and requirements are retained under `dev/vendor/indictrans2-toolkit-review` with revision-prefixed filenames.
- The inspected processor imports text normalization/tokenization helpers and has no network, subprocess, or dynamic execution calls.
- The verification runner checks the processor hash before loading it.

This route is not a claim of upstream-supported Windows inference. Model code compatibility and actual generation remain untested. The historical requirements use a Git-based Indic NLP fork; this evaluation uses the published `indic-nlp-library-itt` wheel used by the current toolkit instead. That substitution must remain visible in any later results.

## Isolated environment and package changes

New profile: `runtime_profiles/indictrans2-evaluation`.

Python 3.10.11 interpreter files are copied from the existing evaluation interpreter. The new profile searches its own packages first, then the existing GPU profile for Torch and the CPU IndicF5 profile for shared general dependencies. It is therefore an overlay requiring both existing profiles, not an independently portable environment. No model weights or Torch libraries were duplicated.

Installed into the new profile only:

| Package | Version | Purpose |
| --- | --- | --- |
| transformers | 4.51.3 | Separate model-loading/generation API for evaluation |
| tokenizers | 0.21.4 | Version compatible with this Transformers branch |
| huggingface-hub | 0.36.0 | Compatible local model download/loading support |
| sentencepiece | 0.2.1 | Model tokenizer support |
| sacremoses | 0.1.1 | English punctuation normalization/tokenization |
| indic-nlp-library-itt | 0.1.1 | Indic normalization/transliteration/detokenization |
| morfessor | 2.0.6 | Indic NLP dependency |

The package plan was inspected before installation. All installed artifacts were wheels. Installation used a separate target with no dependency replacement, no pip download cache, and no bytecode compilation. Shared general dependencies already exist in the evaluation profiles. Documentation-only Sphinx dependencies of Indic NLP were not installed; this is a focused evaluation environment rather than a full package dependency closure. No FlashAttention, Conda, compiler, WSL, or additional speech engine was installed.

The package plan and installation receipts include distribution URLs, versions, and hashes. They are under `docs/validation/2026-10-08-indictrans2-package-{plan,install}.json`.

## Validation and discovered limits

### Model preflight and matching baseline

Offline preflight completed successfully with Transformers 4.51.3. The local custom configuration, tokenizer, and generation class load; the test sentence uses 12 input tokens. The actual model configuration declares 256 source positions and 256 target positions, so this evaluation rejects oversized source inputs and caps generated output below the decoder window. FlashAttention is not required for the selected eager implementation. This preflight does not load trained weights.

Receipt: `docs/validation/2026-10-08-indictrans2-preflight.json`.

The existing NLLB production provider completed all 19 common comparison inputs (8 video cues, 8 prior integrity/style cases, and 3 held-out conversational/phone cases) using the existing GPU profile. Its completion guards remained active and its job workspace was removed. This provides a matching baseline, not a human semantic acceptance score. The initial baseline helper run encountered Windows' default CP1252 decoding when reading the multilingual cue fixture; an explicit UTF-8 read fixed it. The failed receipt is retained separately.

Receipt: `docs/validation/2026-10-08-nllb-comparison-baseline.json`.

### Interrupted weight transfer

The initial Xet transfer did not finish. Its temporary file stayed at 3,221,225,472 bytes and sampled regions were zero-filled; no complete weight file or checksum result existed. The transfer was interrupted before attempting standard HTTP with Xet disabled. The initial receipt and partial file were preserved. A whole-file zero check found nonzero data, so the cleanup helper correctly retained the partial file rather than deleting it. The sampled zero regions did not prove the entire file was empty. The partial file cannot be treated as a valid model or as a contiguous HTTP-resumable prefix.

Receipts: `2026-10-08-indictrans2-download-xet-interrupted.json` and `2026-10-08-indictrans2-aborted-transfer-cleanup.json`. Final usable weights require the standard download receipt's `complete: true`, exact 4,462,265,272-byte size, and matching remote SHA256. Actual generation remains dependent on that completion.

The standard Hub HTTP attempt also left a zero-byte transfer file without completing. A fresh authenticated redirect and a 1 KB range probe immediately returned HTTP 206 with valid nonzero safetensors header bytes. The downloader therefore uses fresh redirects and explicitly validated byte ranges. Each checkpoint records only contiguous, completely received ranges; interrupted tail bytes are truncated back to that checkpoint on resume. Final acceptance still requires the whole-file remote SHA256. Four download connections are used, with at most four 64 MiB range bodies buffered per batch; this uses the existing Requests package and Python standard-library threads, not a new framework.

`dev/run_indictrans2_evaluation.py` runs the resumable transfer, then the isolated offline comparison only after a successful checksum receipt. It writes separate logs and a stage/status receipt, and produces `docs/HINDI_TRANSLATION_COMPARISON_2026-10-08.md` only after both models' 19 outputs are complete and their source strings match. Model/API failures stop the runner and remain in receipts rather than being treated as successful translations. The runner is an ordinary local process, not a recurring automation or a production model selection.

Live progress/status: `docs/validation/2026-10-08-indictrans2-evaluation-run.json` and `docs/validation/2026-10-08-indictrans2-http-progress.json`.

`dev/verify_indictrans2_preprocessing.py` checks package origins, the pinned processor hash, English-to-Hindi language tags, synthetic placeholder restoration, queue clearing, and an actual CUDA calculation. Synthetic postprocessing is explicitly not a model translation or a Hindi quality result.

An initial test fixture incorrectly inserted every alias from the placeholder mapping into simulated output. This caused repeated replacements and was corrected to carry only the actual prepared text. The initial failure receipt is preserved as `2026-10-08-indictrans2-preprocessing-initial-fixture-failure.json`.

A subsequent check found that `+91-9876543210` becomes `+ 91-9876543210` during Hindi detokenization. The digits remain, but the exact phone number formatting is not preserved. The final verifier records this as a failed entity-preservation case, continues other checks, and returns failure if any entity check fails. The upstream processor is not silently patched or promoted into production. This needs an explicit restoration strategy or an approved alternative processor before production use.

Use the final machine receipt `docs/validation/2026-10-08-indictrans2-preprocessing.json` for exact pass/fail results and CUDA status. Do not interpret a successful package installation as successful model inference.

## Browser clarification

The user requested inspection of the open tab. The inspected page was `https://huggingface.co/ai4bharat/IndicF5`, and visibly said access was granted. This confirms access to the speech model only, not IndicTrans2.

That model card also recommends `bodhan-ai/indic-speak` and states that it supports 22 Indian languages with improved speech capabilities. Those are the authors' claims, not ReFlow measurements. Indic-Speak has not been installed, benchmarked, or selected. A speech engine comparison would require a separate proposal and user approval under the user's tool-installation preference.

## Required next steps

1. Access is confirmed in both the browser and the saved login. Keep credentials out of chat and reports.
2. Source assets have been inspected. Complete the offline preflight and record model API compatibility.
3. Download only necessary pinned assets with integrity receipts.
4. Resolve processor phone/entity formatting and model API compatibility in the evaluation profile.
5. Compare real IndicTrans2 output with the existing NLLB baseline on the same video cues plus held-out cases for negation, quantities, dates, conversational phrasing, film terminology, and profanity.
6. Record GPU memory, runtime, completion/truncation behavior, and translation outputs. Obtain human Hindi meaning/style review before changing defaults or generating a new accepted full-video dub.

## Primary references

- [IndicTrans2 English-to-Indic model](https://huggingface.co/ai4bharat/indictrans2-en-indic-1B)
- [IndicTransToolkit](https://github.com/VarunGumma/IndicTransToolkit)
- [Pinned historical processor](https://github.com/VarunGumma/IndicTransToolkit/blob/0c607654e8b6cce897a32039df79018a1daff4e2/IndicTransToolkit/processor.py)
- [IndicF5 model card inspected in the browser](https://huggingface.co/ai4bharat/IndicF5)
