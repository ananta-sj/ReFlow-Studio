# Proposed isolated dialogue-adaptation trial

Status: proposal only. No model or runner has been downloaded or installed.

## Why another translation trial is justified

The installed NLLB and M2M100 routes have actual scene failures, not just timing problems. M2M100 translated a third-person reply as “I said” and an idiom meaning “as soon as possible” as “one day before.” NLLB using the embedded English subtitles repaired that idiom but produced verbose, formal Hindi and incorrect speaker gender in another line. Neither route follows instructions about character identity, conversational wording or a speech-window budget.

## Candidate and isolation

- Official Qwen3-4B Q4_K_M GGUF: approximately 2.5 GB of model weights. Source: https://huggingface.co/Qwen/Qwen3-4B-GGUF . Apache-2.0 model card; multilingual instruction-following is a vendor claim, not proof it passes this scene.
- Official llama.cpp Windows portable CUDA 12 build and its required portable DLLs: https://github.com/ggml-org/llama.cpp/releases . Pin a specific release, published digest and model revision before any approved download.
- Use a dedicated evaluation folder, without changing existing PyTorch environments, system PATH or security settings. No installer, cloud API, account or paid service is proposed. Inference must run offline; any local service must bind only to loopback and terminate with its owned job.
- Approval is required before adding either the runner or model. Exact download sizes and disk budget must be recorded from the selected release's metadata before downloading; the 2.5 GB estimate excludes runner files.

## Acceptance experiment

Use the existing 14-line mother/daughter scene and additional held-out source dialogue. Supply source text, adjacent dialogue context, speaker identity where established, available seconds and optional embedded English subtitle evidence. Request conversational Hindi using the user's restrained Hinglish preference, without new facts, changed relationships, shifted numbers or added dialogue.

Require schema-valid output with the same cue identities and coverage, no hidden reasoning or commentary in spoken text, and no omitted/reordered dialogue. Reject unfinished, repeated or out-of-bounds output. Check meaning on known idioms and pronouns, then synthesize through the existing bounded XTTS route and verify timing/readback. A shorter sentence alone is not an acceptable result. Keep baseline and candidate results separate and do not switch production routing unless the trial passes.

This is a text-adaptation experiment. It will not repair unassigned character voices or establish emotional acting quality; those remain independent acceptance requirements.
