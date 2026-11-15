# Separate GPU evaluation proposal — October 6, 2026

## Why this is proposed

The machine's existing NVIDIA diagnostic utility reports an RTX 4060 Laptop GPU
with 8,188 MiB of memory and driver version 617.14. The current IndicF5
evaluation uses Torch 2.9.1+cpu. The generated Sujata control took 557.563 seconds
of inference for 1.952 seconds of audio. CPU speed makes repeated listening
experiments expensive in time.

The user's latest correction rejects that Sujata take's delivery as unnatural.
GPU evaluation is a proposal to improve iteration performance, not a claim that
GPU use itself repairs prosody. Official-reference sentence acceptance remains
separate from user-voice and full-video acceptance.

## Concrete package and runtime plan

Prepare a new sibling profile, `runtime_profiles/indicf5-gpu-evaluation`, keeping
the current CPU evaluation and core portable app available. Reuse the same
IndicF5 source/package, pinned model checkpoint, exact confirmed reference
excerpts and existing compatible non-Torch dependencies. Do not duplicate model
weights or source recordings.

The proposed Windows CUDA 12.8 package set is:

- `torch==2.9.1` from the official CUDA 12.8 wheel index.
- `torchvision==0.24.1` from that same index.
- `torchaudio==2.9.1` from that same index.

This matched set is listed in the official
[PyTorch previous-version installation instructions](https://pytorch.org/get-started/previous-versions/#v291).
Use `https://download.pytorch.org/whl/cu128` as the official package index.
This changes the execution build of the existing framework; it does not
introduce a new speech engine. Actual wheel availability, dependency requirements
and CUDA device compatibility must still be checked during preparation.

Before activation, inspect downloaded package metadata, verify compatible
versions and avoid mixing CPU and CUDA builds. Preserve dependency-resolution
receipts and isolated import/device checks. Do not change system Python, install
a system driver, or alter the existing app's production engine selection as part
of this proposal. A driver/toolkit need discovered later would require separate
discussion rather than an automatic system change.

## Storage and acceptance boundaries

GPU packages require a substantial download and additional local storage. The
exact wheel and dependency sizes have not yet been resolved; no size estimate is
presented as measured fact. Use the existing pinned model files in place, and
retain CPU results for comparison.

The initial GPU checks should load all weights strictly, report actual device
and peak memory, run the same controls, decode outputs fully and measure elapsed
time. Begin with the model's current precision/settings; treat precision or
diffusion-step changes as separately recorded experiments. Listening must assess
meaning, voice and naturalness even if generation is faster. Do not claim
byte-identical CPU/GPU audio or an unmeasured speedup.

The user requested approval before additions. This package/runtime installation
has not been performed. Await explicit permission for this concrete proposal;
finish the already authorized CPU voice baseline independently.

## Approval and preparation update

The user selected "Allow separate GPU evaluation runtime". Preparation started
in `runtime_profiles/indicf5-gpu-evaluation`; its status is prepared-not-ready.
This evaluation profile places its own GPU packages ahead of the existing
IndicF5 profile's reusable non-Torch dependencies in the Python search path.
It avoids copying large model weights or all dependency files. Therefore the
CPU dependency profile must remain present; this is not an independent release
package. CPU package files and Python search configuration are unchanged.

The official CUDA 12.8 download resolved Windows CPython 3.10 wheels for all
three pinned versions. Torch's download is approximately 2,862.1 MB, before
installation/unpacked size and the other two packages. The download and device
validation remain in progress at this update; no measured GPU speedup exists.
