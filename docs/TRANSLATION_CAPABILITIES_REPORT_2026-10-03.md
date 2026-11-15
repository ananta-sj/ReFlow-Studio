# Translation capability checks — 2026-10-03

## Authorization and scope

The user approved step 1 of the language-capabilities proposal: reject unsupported translation targets and instructions that an engine cannot accept, including Ollama-to-M2M100 fallback; use the existing stack, focused tests, and thorough documentation. This is a backend translation change. No dependency, model, framework, tool, frontend build, commit, push, or deployment was added. Prior uncommitted work remains in place.

## Problem and resulting behavior

The menu contains 24 language names, but those names do not establish every engine's capabilities. Previously, M2M100 silently substituted other targets and NLLB substituted Hindi for Hinglish. Both fixed-vocabulary engines accepted custom instructions without using them. An Ollama outage could therefore change both the requested language and the instruction behavior while producing an apparently successful translation.

Fixed-vocabulary engines now use exact entries in the maintained maps and reject absent entries. Prompt-based engines can still receive the product language names, but their language quality and instruction compliance remain model-dependent and unverified. A nonempty translated string alone does not prove its language or quality.

| Requested target | Previous M2M100 target | M2M100 now | NLLB now |
| --- | --- | --- | --- |
| Hinglish | Hindi | Reject | Reject; previous Hindi substitution removed |
| Nigerian Pidgin | English | Reject | Dedicated pcm_Latn token |
| Western Punjabi | Standard Punjabi | Reject | Dedicated pnb_Arab token |
| Telugu | Kannada | Reject | Dedicated tel_Telu token |

M2M100 has 20 retained target entries and NLLB has 23. These counts describe this application's maps, not the total vocabulary or a guarantee of model quality. The global menu retains all 24 choices for providers that can receive them. No unrelated target or source-language aliases were introduced.

## File-by-file changes

### core/languages.py

Removed the four approximate M2M100 entries and the Hinglish-to-Hindi NLLB entry. Replaced misleading claims that all listed targets work unconditionally with LLMs. Map assertions now permit provider-specific subsets. Added require_known_target() for the shared name list and require_fixed_translation() to reject absent exact targets and nonblank custom instructions, returning the exact target code only after validation. Errors name the engine and target, and tell the user to select another provider or clear incompatible instructions.

### core/llm_translator.py

Ollama discovery still checks the selected model and retains the existing connection/timeout retry policy. If discovery exhausts those retries, it now records fallback_pending and the cause instead of immediately loading M2M100. The first nonblank translate() call provides the target and instructions, allowing validation before a fallback warning, model loading, or potential weights download.

A runtime Ollama request failure also validates M2M100 compatibility before switching engines. Rejection includes both the original Ollama failure and the compatibility reason. A rejected startup fallback remains pending; a rejected runtime fallback leaves the mode as Ollama. A compatible request retains visible fallback warnings and the existing loading/error behavior. Already-loaded M2M100 revalidates each request before tokenization, preventing a later request from bypassing the checks. Blank input does not activate a pending fallback.

### core/providers/translation/nllb_local.py

Checks exact target availability and custom instructions before loading the model. Retains the existing check that the loaded tokenizer recognizes the requested target token; None and unknown-token results remain errors. Uses the canonical core.languages import for the shared policy.

### core/providers/translation/ollama_m2m100_local.py

Rejects unknown product language names before constructing the lazy translator, avoiding needless discovery requests for invalid targets. Existing warning delivery through the bridge remains in place.

### core/providers/translation/airllm_local.py

Rejects unknown product target names before loading an AirLLM model. Existing prompt-based instructions remain supported; this does not certify the chosen model's proficiency.

### core/providers/translation/cloud_rest.py

Both request builders reject unknown product language names before HTTP requests. Chat requests retain instruction forwarding in their system prompt. A custom REST body with nonblank instructions must include a real {custom_instructions} placeholder in a top-level string value that this adapter actually formats. Escaped literal placeholders and nested values do not qualify. After formatting, at least one instruction-bearing value must contain the full instruction text; templates that discard or truncate it fail before HTTP. Matching text elsewhere in the body does not bypass this check. Existing flat template behavior is retained, rather than introducing nested template processing.

Transmitting instructions proves request construction, not that an arbitrary remote endpoint accepts or follows them. Such endpoint capability remains configuration-dependent. Empty or whitespace-only instructions continue to allow existing templates.

### core/providers/base.py

Corrected the translation contract documentation: prompt-based providers send instructions, fixed-vocabulary providers reject them, and custom templates must explicitly transmit them. Removed the claim that every provider honors instructions.

### dev/test_translation_integrity.py

Added 14 capability tests alongside the previous 31 translation integrity tests. Updated discovery-fallback tests to exercise deferred initialization. The new tests cover exact maps, startup and runtime fallback rejection before loading, per-request checks on a loaded engine, valid startup fallback, Ollama target/instruction forwarding, blank-input handling, NLLB rejection before loading and dedicated tokens, custom template forwarding/rejection/truncation, chat forwarding, and unknown targets before provider side effects. HTTP and AI model boundaries are mocked; no real model download is required.

## Verification

Focused translation run: 45 tests passed. Aggregate backend run: 148 tests passed in 14.850 seconds, exit code 0. Changed Python files also passed AST syntax validation; targeted git diff --check passed (only line-ending conversion notices). The aggregate includes existing queue, model asset, speech, and output integrity checks; output checks use bundled FFmpeg/FFprobe on synthetic fixtures. Simulated model-download tests do not download actual weights.

Validation commands used the bundled Windows Python with -B and workspace-local TEMP/TMP:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/test_translation_integrity.py
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

## Limits and next steps requiring separate approval

Source-language handling remains unchanged: M2M100 still sets English as its source and NLLB does not explicitly set a source here. Whisper metadata preservation and manual source overrides are step 2. Speech-engine target validation and frontend capability display are subsequent steps. The menu can therefore still show a target that the selected fixed-vocabulary engine rejects when translation begins. This change checks before that engine's loading/generation, not before every earlier stage of a render.

No live Ollama server, cloud endpoint, real translation checkpoint, full AI render, GUI, GPU, fresh installation, Linux, or macOS was exercised. No new automatic language detector or semantic output validator was added. Existing request connect/read timeouts are not total job deadlines. Error paths propagate through the existing pipeline's segment/cue context and job failure handling.

For rollback, reverse only the changes described here against the preceding working state. A blanket git checkout would also discard unrelated prior work. No snapshot commit was created.


## Subsequent correction — source-language backend verification, 2026-10-03

The original report's NLLB coverage claim for Nigerian Pidgin (pcm_Latn) and Western Punjabi (pnb_Arab) was incorrect. Neither token occurs in the installed tokenizer vocabulary. The backend source-language repair removed those declarations and added vocabulary regressions; NLLB now has 21 maintained target entries. Telugu remains mapped to the present tel_Telu token. This note supersedes the corresponding table entries and dedicated-token assertions above; the earlier test counts describe the earlier working state. See SOURCE_LANGUAGE_BACKEND_REPORT_2026-10-03.md for the correction, current behavior, and validation.
