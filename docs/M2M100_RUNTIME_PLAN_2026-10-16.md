# M2M100 runtime proposal and repairs — 16 October 2026

## Decision requested

Build a **separate CPU translation candidate**, using the existing Python
3.13.16 bootstrap and 40 existing package versions, plus one new dependency:
**SentencePiece 0.2.2** for Windows x64 / CPython 3.13.

The proposed directory is `runtime_profiles/translation-candidate`. It has not
been created. This document and the metadata review do not authorize installing
packages, changing defaults or downloading models. The user's standing
instruction requires approval before adding a new tool/package; the next build
therefore needs explicit approval.

The purpose is to make M2M100 usable from the clean desktop through its own
worker, without adding dependencies to the working XTTS/NLLB environment. The
new environment may later host both translation engines, but that migration
must pass its own tests before any route is switched.

## Why SentencePiece and why a separate environment

M2M100's installed Transformers tokenizer explicitly requires SentencePiece
and reads the existing `sentencepiece.bpe.model` plus `vocab.json`. NLLB's
modern fast tokenizer can use its existing tokenizer JSON; this is why NLLB
worked without the missing dependency while M2M100 cannot use the same route
as-is.

The existing modern CPU environment has an exact 99-package lock and a runtime
identity used by both XTTS and the new NLLB trial. Adding another distribution
there would invalidate that verified closure. A native Python 3.10 package
cannot be copied into Python 3.13 as a compatible replacement.

The new candidate instead copies the required existing packages into its own
directory. This uses more disk but keeps both working environments intact and
provides a clear rollback: retain the old selections and remove only newly
owned staging/candidate files if the trial fails.

## Exact external dependency

| Item | Published metadata |
| --- | --- |
| Package | SentencePiece 0.2.2 |
| Wheel | `sentencepiece-0.2.2-cp313-cp313-win_amd64.whl` |
| Archive bytes | 1,247,987 bytes, about 1.19 MiB |
| SHA-256 | `74f0ee601047c0c12a783088b51be4e6214a62ecd9e02278c477433cd16e0ed9` |
| Declared license expression | Apache-2.0 |
| Required default dependencies | None in the published wheel metadata; NumPy, Protobuf and test dependencies are optional extras and are not enabled by this plan. |

Sources: [PyPI release metadata](https://pypi.org/pypi/sentencepiece/0.2.2/json)
and the published wheel's `.whl.metadata` sidecar, retained locally at
`validation/2026-10-16-m2m100-runtime-sentencepiece-wheel.metadata`.
The wheel archive has **not** been downloaded, extracted, installed or
hash-verified. Its filename/tag, published size/hash, non-yanked status and
metadata were checked; archive bytes must match the stated hash after approval.
No source compilation or new compiler is proposed.

## Storage and transfers

- Existing package payload estimate: **643,380,692 bytes**, from their installed
  RECORD size fields, excluding outside-profile entry points and bytecode.
- Existing bootstrap: **22,062,412 bytes**, across 33 embedded Python files.
- Combined existing-file estimate: **665,443,104 bytes**, about **634.62 MiB**.
- New network transfer: only the **1,247,987-byte** SentencePiece wheel, plus
  small metadata/advisory responses already read.
- Final disk use adds unpacked SentencePiece and candidate receipts. Actual
  copied/installed bytes must be measured during the build; these are estimates.

The existing roughly 1.94 GB M2M100 weights are reused in place. No model copy,
new model download, Ollama installation, cloud call or paid API call is proposed.
The old CPU runtime, XTTS/NLLB environment, recognition environment, desktop
candidate, user settings and current defaults are preserved.

## Reviewed package closure

The roots are Torch, Transformers, psutil, Requests and SentencePiece. Torch
and Transformers execute translation; psutil supports existing worker/process
ownership; Requests is imported by the existing translation module even when
the isolated fixed-model path makes no network call. Their declared transitive
helpers remain part of the verified dependency closure.

The metadata review finds **41 packages and 48 active dependency links** for
Windows x64 / Python 3.13.16. Forty distributions match existing installed
versions and their existing lock. Only SentencePiece is new.

```text
annotated-doc==0.0.5
anyio==4.15.1
certifi==2026.7.22
charset-normalizer==3.5.2
click==8.5.0
colorama==0.4.6
filelock==4.1.1
fsspec==2026.9.0
h11==0.16.0
hf-xet==1.7.0
httpcore2==2.13.1
httpx2==2.13.1
huggingface-hub==2.2.0
idna==3.20
jinja2==3.1.6
markdown-it-py==4.2.0
markupsafe==3.0.4
mdurl==0.1.2
mpmath==1.3.0
networkx==3.7
numpy==2.3.5
packaging==26.3
psutil==7.2.2
pygments==2.21.0
pyyaml==6.0.3
regex==2026.9.29
requests==2.34.2
rich==15.0.0
safetensors==0.8.0
sentencepiece==0.2.2
setuptools==84.0.0
shellingham==1.5.4
sympy==1.14.0
tokenizers==0.23.3
torch==2.14.1+cpu
tqdm==4.70.1
transformers==5.19.0
truststore==0.10.5
typer==0.27.3
typing-extensions==4.16.0
urllib3==2.8.0
```

The plan records original wheel identities, current installed METADATA/RECORD
hashes, the bootstrap hashes, dependency constraints and enabled extras.
An independent pass verifies the target wheel tag, source metadata hashes,
existing versions and all active dependency constraints. This is a proposal
with a satisfied metadata closure, not an already built/validated runtime.

The current public [OSV advisory lookup](https://google.github.io/osv.dev/api/)
returned **zero matches for the 41 selected package versions**. Local Torch's
`+cpu` build suffix is normalized for the upstream PyPI-version query. The
response was checked for missing/paginated results. This is not a security
certification, an audit of native code or a guarantee against future advisories.
Redistribution rights and the application's unresolved owner licensing are
separate release gates.

## Code repairs completed without new packages

1. **Target token validation:** M2M100 previously validated the source token
   but passed the target tokenizer result straight to generation. It now rejects
   missing, unknown, negative, boolean and non-integer target IDs before encoding
   or generation. The validated ID is passed to `forced_bos_token_id`.
2. **Stage-owned cleanup:** The default Ollama/M2M100 provider now exposes
   `release()` and identifies its engine. The existing translation-stage context
   releases it on success, failure and generator close. This drops only its local
   model/tokenizer references and does not stop an external Ollama service.
3. **Partial-load cleanup:** Failed M2M100 initialization clears partially loaded
   model/tokenizer references before reporting the broken state.

These changes do not install SentencePiece or alter which runtime/model is
selected. Legacy M2M100 remains available in the existing runtime. The clean
desktop still needs the proposed isolated route before its fallback can work.

Tests use model/service fixtures, including bad target IDs, valid forced target
generation, idempotent release, lazy-provider release without initialization,
success/error/generator-close cleanup and partial tokenizer-load failure.
The focused run passes **17 tests**, including completion and no-Torch import
boundary regressions. The full backend suite passes **853 tests** in
**150.081 seconds**. Counts overlap. Full acceptance is recorded in
`validation/2026-10-16-m2m100-lifecycle-full-backend.log` and the iteration
closeout receipt; no live service was contacted for these tests.

## Proposed approved build and acceptance sequence

1. Recheck the existing runtime identity and package metadata against this
   proposal. Refuse changed sources or an existing unrelated candidate path.
2. Copy the existing embedded Python bootstrap and only the 40 required package
   distributions into the new candidate. Verify package payload hashes against
   their RECORDs, contain all destination paths and preserve native package data.
3. Download the one pinned wheel from its recorded official artifact URL,
   verify SHA-256 and target metadata, then install/extract it only in the new
   candidate. Resolve no unreviewed dependencies and execute no source build.
4. Check the final 41-package closure, import origins, CPU arithmetic and real
   SentencePiece encoding/decoding with the existing tokenizer asset.
5. Load the existing M2M100 checkpoint offline and check English↔Hindi plus
   another supported pair, invalid tokens, oversized input and output completion.
   Separate mechanical checks from human semantic-quality acceptance.
6. Implement and test the job-owned persistent worker route, startup failures,
   repeated cues, decoder cancellation, stage cleanup, settings/readiness and
   evidence. Keep legacy/default execution unchanged until explicit trial selection.
7. Verify original runtime/model/state preservation; remove only owned download
   staging and candidate-generated caches. Record all bytes, failures and limitations.

No public release, licensing decision, default migration or model replacement is
included in the requested approval. If the wheel or runtime fails validation,
preserve the evidence and stop that candidate rather than modifying the working
environment or silently substituting another model.

## Evidence files

- `validation/2026-10-16-m2m100-runtime-proposal.json`: exact dependency graph,
  package versions, source/metadata hashes, artifact URL/hash/size and byte estimates.
- `validation/2026-10-16-m2m100-runtime-independent-review.json`: independent
  metadata/closure and preservation checks, with no runtime created.
- `validation/2026-10-16-m2m100-runtime-advisories.json`: current advisory response.
- `validation/2026-10-16-m2m100-lifecycle-focused.log`: focused code checks.
- `validation/2026-10-16-m2m100-lifecycle-full-backend.log`: full regression result.
- `validation/2026-10-16-m2m100-plan-and-repairs-acceptance.json`: current source
  hashes and preserved state/runtime/model identities; installation still pending approval.

The proposal remains `ready_to_install=false` and `approval_required=true` until
the user authorizes the separate candidate and its one new package.

## Subsequent approval and execution — 16 October 2026

The user subsequently approved the separate runtime and tests. The approved candidate is now built and technically validated for explicit trial selection; the proposal flags above describe the historical approval stage. Existing defaults remain unchanged. See [the implementation, complete test evidence, cleanup and remaining release gates](TRANSLATION_CANDIDATE_ACCEPTANCE_2026-10-16.md). This is not a production or full-release approval.
