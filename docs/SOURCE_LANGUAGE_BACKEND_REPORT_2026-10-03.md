# Backend source-language handling — 2026-10-03

## Approved scope and status

The user approved the backend stage of the source-language plan: Auto by default, a manual translation-source override, exact source mappings, an automatic fixed-vocabulary confidence threshold of 0.80, safe fallback checks, provider forwarding, tests, and documentation. The interface stage requires separate approval. No frontend dependency restoration, npm installation, framework, external tool, model download, commit, push, or deployment occurred. Earlier user changes and approved repairs remain in place.

## Resulting policy

| Input condition | Prompt-based translation | M2M100 / NLLB |
| --- | --- | --- |
| Valid manual source | Source name included in prompt/request | Use exact supported source token; no confidence requirement |
| Known detected source, confidence >= 0.80 | Source name included | Use exact supported source token |
| Missing or lower confidence | Ask model to infer from text | Reject; request manual selection |
| Unknown detected label | Ask model to infer from text | Reject; never assume English |
| Invalid manual source setting | Reject | Reject |
| Source absent from fixed engine map | Prompt provider may receive the known source name | Reject; no language/script substitution |
| Subtitle input in Auto | Model may infer from subtitle text | Reject; subtitle files have no detection metadata |

The threshold is an initial safety policy, not calibrated accuracy. Exactly 0.80 is accepted; lower values and missing probabilities are rejected by fixed-vocabulary translation. Numeric strings, booleans, NaN, infinity, and out-of-range values cannot satisfy it. Manual selection is a user's assertion and does not invent a confidence score.

## Source resolution and mappings

Added core/source_language.py, using the standard library and existing language tables. Its immutable SourceLanguage context contains canonical code, origin (manual/detected/unknown), optional probability, and the original detected label. Resolved means a known manual selection or a known detection with sufficient valid confidence. Result instances remain local to a request; translators do not inherit source language from the preceding request.

The source catalog has 28 entries: the existing 24 product languages plus Simplified Chinese, Traditional Chinese, Punjabi with unspecified script, and Punjabi/Gurmukhi. Auto is a selection mode rather than a language entry. Known codes, existing display names, selected clear cloud labels such as English/Arabic/Chinese/Punjabi, and maintained exact NLLB token labels are normalized case-insensitively. Unknown detected strings remain unresolved; unknown manual choices fail. This is a reviewed subset, not the full engine vocabulary. For example, a detected language outside this catalog does not become English or acquire an unreviewed mapping.

Source maps are separate from target maps:

- Generic Chinese (zh) is usable with M2M100's language token but does not select an NLLB script. NLLB requires zh-Hans or zh-Hant, mapping to zho_Hans or zho_Hant.
- Generic Punjabi (pa) does not select a script for either fixed provider. An explicit pa-Guru maps to M2M100 pa or NLLB pan_Guru. Western Punjabi remains a distinct source choice and is unsupported by these maintained fixed maps.
- Hinglish does not become Hindi. Unsupported sources fail instead of borrowing a related language's token.
- Both Simplified and Traditional Chinese map to the same M2M100 language token because that engine's vocabulary does not distinguish them; this does not certify output script or quality.

The installed tokenizer source files were inspected through AST, without importing models or downloading weights. Final maintained maps match their declared vocabularies: M2M100 has 23 source entries and 20 target entries; NLLB has 23 source entries and 21 target entries. Runtime checks still verify the loaded tokenizer's source token, since a different checkpoint may differ.

### Correction to the previous NLLB coverage claim

The earlier capability report and tests incorrectly treated pcm_Latn (Nigerian Pidgin) and pnb_Arab (Western Punjabi) as dedicated NLLB tokens. The installed NLLB FAIRSEQ_LANGUAGE_CODES contains neither. This verification exposed the error; those two target declarations were removed, which also removes their derived source declarations. Both languages now fail before NLLB model loading rather than reaching a later unknown-token error. Telugu's tel_Telu token is present and remains supported by the maintained NLLB map. The earlier report has a correction note pointing here. Prompt-based providers still receive these product language names, with quality unverified.

## Backend interfaces

Every translation provider now accepts optional source_language after custom_instructions. Direct calls can supply a manual code/name or a resolved SourceLanguage object. None and auto mean unresolved automatic source unless the pipeline supplies detection metadata. Fixed providers therefore no longer interpret omitted source as English. Third-party TranslationProvider implementations must accept the new keyword to participate in the updated pipeline; old signatures produce an explicit error instead of silently dropping a requested override.

Bridge render parameters use a serializable source_language string, defaulting to auto when absent. _template_kwargs forwards it to video_dub, video_dub_lipsync, audio_dub, and subtitle_translate. list_source_languages() exposes the reviewed source catalog for the next interface stage. Existing queue/interrupted-job parameters already retain arbitrary render parameters, so a manual string selection survives those paths without persisting the internal context object.

Programmatic bridge request example:

```json
{
  "lang": "en",
  "source_language": "fr"
}
```

The rest of the selected template's existing parameters still apply. The manual override tells translation what source to use; it does not force Whisper's transcription language or correct already-misrecognized words.

## File-by-file implementation

- core/source_language.py: source catalog, reviewed aliases, immutable context, Auto/manual resolution, confidence policy, fixed-source checks, and prompt source wording.
- core/languages.py: updates the policy reference and removes the two unsupported NLLB target declarations discovered during vocabulary verification.
- core/providers/base.py: documents the new translation keyword and behavior.
- core/llm_translator.py: removes the hardcoded English source. M2M100 validates source policy before tokenization, verifies a real nonnegative integer token distinct from the unknown token, and sets src_lang for each request. Ollama prompts include a resolved source or an inference instruction. Startup and runtime fallback validate source, target, and custom instructions before warnings or M2M100 loading. Rejection retains the originating Ollama cause; compatible fallback retains visible warnings and existing loading behavior.
- core/providers/translation/ollama_m2m100_local.py: validates manual overrides before lazy discovery and forwards the full source context.
- core/providers/translation/nllb_local.py: checks source policy before loading, verifies the loaded source token, and sets src_lang before encoding each request. Existing target-token and output checks remain.
- core/providers/translation/airllm_local.py: validates source context before model loading and includes resolved source/inference wording in its existing prompt.
- core/providers/translation/cloud_rest.py: chat-shaped requests include source/inference wording. Custom requests format source_language (canonical code) and source_language_name (display name). A resolved source requires a real top-level string placeholder; escaped literals and nested objects do not transmit it. Source placeholders with formatting or conversion are rejected to prevent truncation/discard. Unresolved Auto supplies empty strings to these optional placeholders and leaves inference to the endpoint. Request configuration must be a dictionary.
- core/providers/resolve.py: forwards optional registry meta.translation_request into cloud/local-API translation adapters. This was necessary because a template configured in registry metadata would otherwise never reach the adapter. Other stage configuration is unchanged.
- core/pipeline.py: validates manual selections before processing; resolves source from the original transcription metadata for audio and video, or from manual selection for subtitles; forwards the context through all three translation loops. The existing segment/cue error context is retained. Translation bypass still skips the translator. Detection metadata remains associated with the original recording even after segment text is translated.
- bridge/api.py: forwards the new render parameter for all templates and exposes the source catalog. No frontend source or compiled asset was changed.
- dev/test_source_language.py: adds focused source policy, tokenizer, fallback, cloud, resolver, bridge, persistence, subtitle publication, and actual generator-wiring tests with AI/media boundaries mocked.
- dev/test_translation_integrity.py and dev/test_transcription_metadata.py: update old success fixtures to supply explicit fixed-provider sources and verify the newly forwarded context. Correct the prior NLLB coverage assertions.
- dev/run_cleanup_checks.py: includes the new test module.

## Custom translation endpoint configuration

The existing flat request template can be configured programmatically in a translation model entry's meta.translation_request. The adapter forwards canonical source codes by default; an endpoint that expects names can use source_language_name. This only verifies transmission, not the endpoint's interpretation or translation quality.

Example metadata:

```json
{
  "translation_request": {
    "path": "/translate",
    "body": {
      "text": "{text}",
      "target_language": "{target_language}",
      "source_language": "{source_language}",
      "instructions": "{custom_instructions}"
    },
    "response_field": "text"
  }
}
```

A custom endpoint with a resolved source and a template that cannot send it fails before HTTP. Existing metadata-free Auto requests can retain their text/target-only template. Adding custom-template configuration controls to Marketplace is outside this stage.

## Verification and evidence limits

The initial focused source run passed 41 tests. Additional token-validation and vocabulary-correction regressions were then added; the final source module contains 44 tests. The final aggregate run passed all 221 tests in 12.305 seconds, exit code 0. All 15 changed Python files passed AST syntax validation, and targeted git diff --check passed with only LF/CRLF conversion notices. The workspace temp directory was empty; frontend/node_modules remained absent. The aggregate covers the existing queue, asset restoration, output integrity, speech, translation, metadata, and new source policies. Existing media checks use real bundled FFmpeg/FFprobe on synthetic fixtures. Simulated download fixtures do not download actual model weights.

Source-specific checks cover the inclusive threshold, absent/malformed confidence, known aliases, manual override precedence, unknown labels, script distinctions, immutable contexts, source assignment before tokenization on successive requests, loaded-token errors, source checks before model loading, startup/runtime fallback blocking and successful recovery, Ollama/AirLLM/chat/custom forwarding, registry configuration, default/explicit bridge parameters, interrupted-job preservation, subtitle output creation and rejection without publication, translation bypass, and actual video/audio generators stopped before synthesis with media/model calls mocked. A vocabulary regression reads installed tokenizer constants through AST; it skips when this checkout's bundled tokenizer files are unavailable.

No live Ollama server, Whisper checkpoint, translation model, cloud endpoint, complete AI render, GUI, GPU, fresh installation, Linux, or macOS was exercised. High-confidence detection does not establish that the entire recording is monolingual. No per-segment language detection, text-script detector, semantic translation validator, or new dependencies were added.

Commands use existing bundled Windows Python, -B, UTF-8 output, and workspace-local TEMP/TMP:

```powershell
$env:TEMP = Join-Path (Get-Location).Path 'temp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
.\build\windows-portable\python.exe -B dev/test_source_language.py
.\build\windows-portable\python.exe -B dev/run_cleanup_checks.py
```

## Interface follow-up and current usability limit

The built interface still sends no manual source parameter, so it defaults to Auto. It does not yet show detected language/confidence or offer the override selector. Automatic fixed-provider jobs with adequate known detection can run; low/absent confidence, ambiguous scripts, unsupported sources, and subtitle-only fixed-provider jobs now fail clearly rather than assume English. Manual selection is currently available through backend calls only. The next approved stage must provide the visible selector and feedback, persist/forward selections, and rebuild the existing frontend.

The existing frontend node_modules was removed during cleanup. A UI build requires temporary restoration of lockfile-listed development dependencies, previously approximately 161 MB, plus possible build/cache overhead. That restoration needs separate user approval. No such restoration happened here.

For rollback, reverse only this coordinated change against the prior working state. A whole-tree Git reset would discard earlier approved work and unrelated user edits.


## Subsequent interface stage — 2026-10-03

The approved interface stage added the visible source selector, saved choices, detection feedback, and rebuilt frontend. It supersedes the backend-only usability limitation above. See SOURCE_LANGUAGE_UI_REPORT_2026-10-03.md for changes, build/verification evidence, temporary dependency clearance, and the unavailable live-browser verification limitation.
