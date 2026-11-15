# Parallel speech safety — 2026-10-03

## Approved change and outcome

After reviewing audit finding A02, the user approved protecting speech-engine
initialization and inference on CPU and GPU while retaining independent audio
processing in parallel. This iteration implements that narrowly scoped repair.
No dependency, framework, tool, worker process or model was added. No dependency
restoration, frontend rebuild, runtime upgrade or model download was needed.

Parallel segment workers now share an inference lock on every device. Previously
`_dub_all_segments()` supplied a lock only when the effective device was not CPU.
CPU workers could therefore enter the same lazy XTTS handler simultaneously, or
overlap RVC/F5 calls that use mutable model state. The existing actor-resolution
lock protected the provider dictionary, but not lazy engine construction or
inference inside those providers.

The shared lock surrounds the existing provider calls, so both lazy construction
and inference are covered. It is shared across actors within the segment batch:
this matters because RVC writes shared configuration files even when two actors
use different provider instances. Requested GPU inference that falls back to CPU
continues to use the same protected path.

## What remains parallel

Segment workers still exist and retain their unique working directories.
Audio validation, normalization, mastering and timing adjustment remain outside
the inference lock. Completed clips are still mixed by source segment index,
regardless of worker completion order. Worker counts and defaults are unchanged.
The sequential path remains unchanged.

One speech call at a time is a deliberate safety tradeoff. CPU inference may be
slower than overlapping calls in a case where an engine happens to tolerate them.
There is no measured speedup or slowdown claim in this iteration. Raising worker
counts does not imply multiple simultaneous speech-model calls. Separate engine
instances/processes and their memory/throughput tradeoffs would require a further
approved design and real-model benchmark.

## Files changed

| File | Change |
| --- | --- |
| `core/pipeline.py` | Create the inference lock for CPU as well as GPU; explain device-independent ownership in the batch documentation. |
| `dev/test_parallel_speech.py` | Add six overlap, initialization, actor-state, output-order and cancellation regressions. |
| `dev/run_cleanup_checks.py` | Include the new regression module in the existing aggregate. |
| `docs/validation/2026-10-03-parallel-speech-checks.log` | Retain complete aggregate validation output. |
| This report and its evidence directory | Record scope, test results and acceptance limits separately from the historical audit. |

Provider files and their public methods did not change. The protection applies
to the managed pipeline's parallel segment batch; direct external callers sharing
a provider are not made thread-safe by this pipeline lock. Separate pipeline
instances invoked outside the single-active-job bridge also have separate locks.
Such concurrent standalone usage remains outside this iteration's guarantee.

## Regression design

The new checks use existing speech fixtures and playable synthetic audio, with
simulated model boundaries. No actual model is loaded. Events establish worker
arrival before releasing the first engine call; tests do not rely on an arbitrary
sleep to create overlap. Barrier waits have bounded failure timeouts.

1. **CPU XTTS:** the first lazy constructor waits until a second worker attempts
   synthesis. The real provider wrapper is exercised with a fake handler. Exactly
   one constructor is called, two lines are generated and peak handler concurrency
   is one.
2. **GPU XTTS:** the same test verifies existing serialization is retained.
3. **CPU RVC:** two actors use real RVC provider wrappers with fake handlers.
   The first conversion waits for another conversion attempt. A simulated shared
   model selection must remain the same throughout each call; both actor names
   are honored and peak conversion concurrency is one.
4. **CPU F5 path:** a simulated F5 provider waits for another conversion attempt.
   F5 generation is serialized and base TTS is never called for those segments.
   This verifies pipeline dispatch, not real F5 loading or inference.
5. **Parallel mastering and order:** the first segment's mastering waits for the
   second segment to finish mastering. This proves that postprocessing can still
   overlap. Different synthetic tones then verify exact output bytes at their
   original timeline positions, with silence preserved in the gap.
6. **Cancellation while waiting:** a CPU model call remains blocked while a
   second worker waits for inference. Stop signals the job, but completion waits
   for the first call's release. The waiting worker never calls the model,
   temporary segment directories disappear after workers exit, and scoped
   workspace cleanup succeeds.

Existing sequential/parallel failure propagation, playable-output checks,
cancellation, queue, output-integrity, language and model-asset regressions are
included in the aggregate. The exact aggregate result is recorded in the evidence
JSON and retained log. Scoped whitespace and Python syntax checks also run.

Final validation: **268 tests passed in 23.465 seconds**, including all six new
checks. All three changed Python files parsed successfully and the scoped diff
whitespace check passed. No test job directories remained in `temp/jobs`, and
frontend dependencies remained cleared. File/log hashes and the A02 follow-up
status are saved in
`cleanup/2026-10-03-parallel-speech/VERIFICATION_AND_FOLLOWUP.json`.

## Acceptance limits and audit status

A02 is addressed for overlapping engine calls within the managed render pipeline
and verified with synthetic concurrency regressions. Real CPU/GPU XTTS, RVC and
F5 inference, actual model configuration behavior, memory consumption, device
recovery under load and throughput remain unverified. Tests ran on Windows with
the existing portable Python 3.10.11; macOS/Linux were not exercised.

The existing cancellation contract remains: native model calls cannot be killed
safely as Python threads. Stop waits for an active call to return, and the waiting
worker checks cancellation before entering inference. This repair does not add
instant native-call termination.

No other full-audit finding is closed by this iteration. In particular it does
not resolve model-install integrity, moderation failure policy, output stems,
registry updates, navigation state, environment conflicts or portable packaging.
The historical full audit and its issue register remain unchanged; the follow-up
evidence identifies this narrower A02 status and its outstanding acceptance work.

## Reproduction

From the project root, run the existing portable Python with
`-B dev/run_cleanup_checks.py`, with TEMP and TMP pointed at the project's temp
directory. For only the new module, use a runner that adds the project root and
core directory to sys.path before loading `dev.test_parallel_speech`; the embedded
portable interpreter does not automatically expose the root to `-m unittest`.
Tests use disposable directories and need no internet, actual models or added
packages. No temporary dependency directory requires clearance afterward.
