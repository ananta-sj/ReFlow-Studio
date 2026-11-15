# Isolated dialogue trial result

The approved Qwen3-4B Q4_K_M trial is **rejected for production dubbing**. No active model connections, settings or graph were replaced. The original episode queue remains paused.

The 2,497,280,256-byte model matched its official SHA-256. The official llama.cpp b12375 Vulkan portable archive also matched its published checksum. The smaller Vulkan build replaced the planned CUDA bundle download; it explicitly selected the existing RTX 4060 driver, without changing other AI runtimes or installing drivers.

Large downloads initially stalled and disconnected. Bounded, resumable one-MiB ranges completed the file, and final whole-file checksums were verified. Removed 257,758,667 bytes of obsolete partial downloads and failed cache data. Only the verified trial assets and diagnostic text were retained.

The local-server test could load the model but its client could not reach the loopback endpoint. The chat CLI also failed to finish its smoke test within five minutes. Both owned processes were stopped. Direct, file-based `llama-completion` inference passed its smoke test and required no network service. It finished complete JSON responses with EOS and stayed within the explicit output budget.

## Actual quality results

- Japanese scene: 14 cue IDs retained, but statements changed and an unsupported twelve-lakh-kilometre distance appeared. All model uncertainty flags were false despite those failures.
- Japanese plus English subtitle evidence: 14 cue IDs retained, but dialogue was duplicated across cues and claims changed.
- English subtitles as the primary input: 15 cue IDs retained, but the mother's “your father” became her own father, “before he died” was lost, and geography and phrasing remained wrong or unnatural.
- Independent source lines: some simple quantities and negation survived, but refusal and relationship wording did not pass.
- CPU and GPU/backend controls both produced incorrect Hindi for the same simple English father statement. The native model chat-template control did not fix it. These are quality controls, not a controlled speed comparison; they show RTX selection is not the sole cause of the translation failure.

The text fixtures supplied known character roles and female gender explicitly. They do not demonstrate improved automatic speaker identification. JSON validity, EOS completion, low uncertainty flags and fast execution do not establish semantic fidelity. No rejected wording was sent to a new speech-generation pass, and no accepted scene or episode was exported.

Raw outputs and inputs are preserved in `docs/validation/qwen-scene-20261114`. The existing installed NLLB/M2M100 failure evidence remains separate.

## Software repairs completed alongside the trial

The failed-dialogue report now persists a bounded run identifier so a newly constructed bridge can recover it after restart. Deleted output records do not resolve to stale reports; external paths, changed run identities and links are rejected. Clearing the prior pointer is auxiliary and cannot block a new render when cleanup is denied.

Broader queue checks also exposed an optional-review-report type failure that could turn a valid completed media export into a failed job. Review publishing now accepts only path-like manifest values and treats malformed optional report data as a warning. The pipeline's required dialogue completeness checks still run before media export.

## Next candidate, not installed

Tencent's official HY-MT1.5-1.8B is a translation-specific model. Its model card explicitly lists Japanese and Hindi and documents contextual/terminology translation. Its Q8_0 GGUF is approximately 1.91 GB, with published SHA-256 `6789b06d0902f2f5312c0e1703d56ccbddfcfb6c653d22519b7c720f7db9a98e`.

Source and publisher instructions: https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF

Artifact: https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF/blob/main/HY-MT1.5-1.8B-Q8_0.gguf

This is a better task match to evaluate, not a claim it passes this episode. It can reuse the existing portable runner. User approval is required before downloading these additional weights or removing the failed Qwen trial weights. Test the same relationship, negation, quantity and scene fixtures, then actual speech timing/readback only if meaning and wording pass. Character matching remains a separate unresolved requirement.
