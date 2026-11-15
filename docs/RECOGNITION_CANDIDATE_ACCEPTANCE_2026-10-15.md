# CPU recognition candidate — partial acceptance, 15 October 2026

## Decision and authorization

**The runtime/conversion and English worker tests pass. Overall recognition quality approval remains false because the confirmed Hindi reference was automatically classified as Urdu.** An explicit Hindi hint produces Devanagari output, but its measured word error rate on that reference is 25.8%. No default was switched and no full-app release approval is granted.

The user approved the exact 24-package recognition candidate, existing-bootstrap reuse, offline conversion of the existing Whisper turbo checkpoint into a separate evaluation copy, actual recognition/worker tests, preservation of originals/defaults and installer cleanup. That work was performed. No new model, compiler, conversion package, driver or paid API was downloaded/installed. Existing application environments remain intact.

## Installed candidate and actual artifacts

`runtime_profiles/recognition-candidate` contains ordinary Windows x64 CPython 3.13.16 and the reviewed 24-package closure. The bootstrap was copied from the verified owned interpreter, without copying another environment's packages. All remote wheels matched their exact reviewed sizes and SHA-256 hashes before local binary-only, hash-bound installation. Installation used no index or dependency resolution and targeted only the owned candidate.

The environment contains faster-whisper 1.2.1, CTranslate2 4.8.3, PyAV 19.0.1, ONNX Runtime 1.31.0 and their locked support packages. It has no Torch or Transformers. Actual import origins and all 24 metadata versions were checked; there are no duplicate distribution names. All **2,316 installed hashed payload files** matched RECORD hashes and sizes, including native components.

Cross-target CLI launchers were deliberately removed because they point to the host build interpreter and are not used by Reflow. The initial file verifier missed two such declared launcher paths, `pyav.exe` and `idna.exe`; its failed receipt is retained. The corrected verifier permits only specifically listed removed launchers and still rejects arbitrary missing or changed payloads.

## Offline model conversion and first compatibility repair

The original `models/f5/reference-asr` checkpoint was checked against every pinned manifest hash, including its **1,617,824,864-byte** safetensors payload, before conversion and again after testing. Original files were not edited or moved.

The existing main runtime supplies CTranslate2 4.6.3 and Transformers 4.36.2. Its first conversion failed because CTranslate2 supplied `dtype` to a Transformers release expecting `torch_dtype`. That raw failure receipt/log is retained. A conversion-only subclass maps this one argument for those **exact two versions**. It changes no installed third-party source and no model architecture or tokenizer content. The mapping runs only in the conversion process.

With offline flags, Python socket access blocked, and `trust_remote_code=False`, that adapter converted the local checkpoint to a separate int8 CTranslate2 copy at `models/whisper/ct2-turbo-candidate-compat/model`. No replacement model was fetched. The conversion took **35.39 seconds** on this run and produced **817,887,676 bytes**, about **780.00 MiB**, including tokenizer/preprocessor assets. This is a representation/quantization change, not proof of equal recognition quality; the actual tests below decide the accepted scope. Converted file hashes are retained and verified after inference.

The original failed conversion directory contained only its owned marker. After verifying its exact location, ownership and contents, that empty failed container was removed; failure evidence remains in `docs/validation`.

## Real decoding exposed a second compatibility failure

Package metadata resolution alone did not prove execution compatibility. The first native transcription imported every required native module successfully, then failed because faster-whisper passes `metadata_errors` to `av.open`, a parameter removed by PyAV 19. [Pinned PyAV 19 implementation](https://raw.githubusercontent.com/PyAV-Org/PyAV/v19.0.1/av/container/core.py).

`core/recognition_compat.py` now adapts only faster-whisper's private audio-module reference for **faster-whisper 1.2.1 / PyAV 19.0.1**. It removes the obsolete `metadata_errors='ignore'` argument for that pair, forwards all other operations/options to PyAV, and rejects unexpected policies or mismatched module versions. Other package versions are unchanged. Global `av.open` and installed wheel contents are untouched. Metadata decoding follows PyAV 19's native behavior rather than asserting identical handling for every historical container format.

`STTHandler` calls that guarded adapter before inference. Five unit cases verify locality/idempotence, version gating, retained native options, unsupported-policy rejection and metadata/import mismatch handling. Seven focused cases, including the two prior import-boundary tests, pass. The complete working-runtime backend suite passes **807 tests in 111.443 seconds** after this production change. Existing warnings/deprecations remain visible; installed packages were not patched to suppress them.

## Actual recognition and worker results

| Scope | Result | Limit |
| --- | --- | --- |
| Native environment/media assertions | 38 checks passed | Includes exact package closure/origins and native library imports |
| Known English speech | Exact normalized words; English probability about 0.9875 | One existing short generated sentence, not a broad accuracy benchmark |
| Silent WAV with VAD | No invented cues | Three-second digital silence fixture |
| Malformed metadata WAV | Decoded samples equal the original WAV | Specific invalid metadata fixture; not all corrupt containers |
| Corrupt media | Rejected | One invalid-media fixture |
| Desktop-to-recognition worker | 9 checks passed | Existing process-local worker override, not final feature selection wiring |
| Confirmed Hindi reference, automatic language | **Failed**: Urdu label, probability about 0.9223, Urdu script | Retained quality failure; no approval for automatic Hindi use |
| Same Hindi reference with explicit `language='hi'` | Hindi script; measured WER **8/31 ≈ 25.8%** | Diagnostic only; wording accuracy remains unapproved |

English recognition used the existing retained speech WAV whose expected text is “Good morning. This is the portable speech test.” Case/punctuation normalization yielded exact words. Returned segment bounds were valid. This provides an execution/data-contract check, not new human assessment of audio quality.

The existing desktop candidate launched the actual public `WhisperLocalProvider` and `run_stt.py` using the recognition interpreter. The same English wording and language metadata survived the JSON worker boundary. A missing media file surfaced a worker diagnostic, success unregistered the child, and cancellation terminated the observed owned worker and cleaned the workspace. Cancellation acknowledgement was **0.126 seconds** on this run. The test observes an active owned worker; it does not claim an exact mid-decoder/token cancellation boundary or a general speed benchmark.

Worker selection used `REFLOW_WORKER_PYTHON` only inside the disposable test process. No system environment or saved selection changed. The generic override affects all workers in that process, so it is not the final per-feature architecture and must not be enabled globally for the app.

## Hindi failure and its significance

The Abhishek reference audio matched its existing confirmed SHA-256 before use. In automatic mode, the candidate emitted Urdu script for spoken content whose confirmed transcript is Hindi. A high automatic confidence score therefore did not guarantee the intended language/script.

The explicit Hindi diagnostic changed only the generation language hint, using the same converted weights/audio and existing libraries. Its returned language probability is a consequence of forcing the label, **not independent confidence in automatic Hindi detection or wording quality**. Its NFC/punctuation-normalized word error rate is about 25.8%; spelling variants and actual word substitutions both count. That metric is retained without weakening the threshold or relabeling the automatic failure as a pass.

The same reference was then tested through the existing GPU `WhisperTurboLocalProvider`, original checkpoint and unchanged worker profile. That baseline also returned **Urdu**, with probability about **0.8949**, and released its worker/temporary workspace correctly. The CPU candidate's corresponding probability was about 0.9223. The shared automatic-language failure is therefore not newly introduced by this conversion. This one comparison does not establish that quantization preserves all other recognition behavior or multilingual accuracy. Baseline evidence is retained separately as `2026-10-15-recognition-existing-gpu-baseline.json` and its log.

The product currently resolves a manually selected source language after recognition rather than passing it through this provider/worker to guide recognition. That needs a real interface and cache-identity change: explicit source hints must reach each appropriate recognizer, while automatic language/script ambiguity must remain visible. Hardcoding Hindi would damage the any-language objective and is not an acceptable fix. Broader quality comparison remains needed despite the matching automatic-language failure in this baseline check.

The final acceptance receipt deliberately records `passed=false`, `technical_checks_passed=true`, `hindi_auto_detection_passed=false` and `release_ready=false`. The candidate profile is marked partial acceptance with the Hindi failure, not a ready/default engine. Neither the hinted diagnostic nor English success overrides that decision.

## Preservation, notices and cleanup

Final candidate logical size: **269,874,840 bytes**, about **257.37 MiB**, excluding the converted model, app source, frontend, FFmpeg, originals and all other profiles. The separate converted copy is **817,887,676 bytes**; these sizes are file totals, not disk allocation or a complete release footprint.

Owned wheel/install staging was removed after verification: **85,330,584 bytes**. Thirty-one generated `__pycache__` directories inside the owned candidate were removed, reclaiming **2,600,524 bytes**. Existing runtimes, original model folders and user media were not included in that cleanup. Raw failure receipts/logs and the final converted model remain intentionally retained for debugging/reproducibility.

Notice collection initially missed ONNX Runtime's package-root license/ThirdPartyNotices. Collection was extended using verified RECORD paths. Artifact notices are retained for **21/24 packages**. The selected CTranslate2, FlatBuffers and tokenizers wheels lack notice files detected by this inventory; exact upstream notice/source follow-up remains a distribution gate. The earlier exact-version package advisory scan had zero matches, but that does not certify bundled native media/inference libraries, licensing or model quality.

The final payload/preservation check confirms five original saved-state hashes, eight original XTTS asset hashes, previous boundary source hashes and the isolated XTTS identity remain preserved. The Whisper original/converted manifests are also verified after testing. Production changes in this iteration are the new exact-version recognition adapter and its handler call. New/updated build/conversion/evaluation/verifier scripts and focused tests support that scope; application defaults, model registry and cloud connections are unchanged. Ollama remains absent.

## Retained evidence and next work

Primary evidence under `docs/validation`:

- `2026-10-15-recognition-candidate-downloads.json`, install/build receipts/logs and notice inventory.
- `2026-10-15-recognition-model-conversion.json` and `.log`: first conversion failure; `...-conversion-compat.json` and log: verified successful conversion and hashes.
- `2026-10-15-recognition-candidate-native.json`: initial PyAV failure; `...-native-compat.json`, `...-native-media.json`, `...-provider.json`: corrected actual tests.
- `2026-10-15-recognition-candidate-native-hindi.json`: failed automatic Hindi detection; `...-native-hindi-hinted.json`: explicit-hint diagnostic and WER.
- `2026-10-15-recognition-compat-focused.log` and `...-full-backend.log`: focused and 807-test regressions.
- `2026-10-15-recognition-candidate-file-integrity-initial.json` and `...-final.json`: retained launcher-verifier failure and corrected full payload checks.
- `2026-10-15-recognition-candidate-cache-notice-cleanup.json`, `...-staging-cleanup.json` and `...-acceptance.json`: bounded cleanup and partial decision.

Next: propagate explicit source-language hints through provider/worker interfaces and checkpoint/cache identities; expose ambiguity rather than silently accepting the wrong script; then test multilingual recognition and quality before changing selections. The initial GPU comparison above is complete. Finish feature-specific runtime/preflight/readiness routing rather than a global interpreter override. Translation/separation/RVC/vision migrations, real full workflows, clean Windows native onboarding, resource/parallel calibration and owner/third-party/model licensing remain release gates.
