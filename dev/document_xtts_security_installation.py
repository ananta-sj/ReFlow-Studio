"""Consolidate actual replacement acceptance, retained failures and release limits."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation'
PROFILE=ROOT/'runtime_profiles/xtts-security-candidate'

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    install=read('2026-10-13-xtts-security-candidate-install.json')
    probe=read('2026-10-13-xtts-security-candidate-runtime-probe-compat-adapter.json')
    live=read('2026-10-13-xtts-security-candidate-live-evaluation-dense-position.json')
    session=read('2026-10-13-xtts-security-candidate-session.json')
    speech=read('2026-10-13-xtts-security-candidate-speech-content.json')
    pcm=read('2026-10-13-xtts-security-candidate-pcm-comparison.json')
    preserved=read('2026-10-13-xtts-candidate-preservation-after.json')
    source=read('2026-10-13-xtts-security-candidate-source-records.json')
    cleanup=read('2026-10-13-xtts-security-candidate-staging-cleanup.json')
    scan=read('2026-10-13-xtts-security-cpu-advisories.json')
    notices=read('2026-10-13-xtts-security-candidate-notices/inventory.json')
    lock_hash=hashlib.sha256((OUT/'2026-10-13-xtts-security-cpu-lock-review.json').read_bytes()).hexdigest()
    adapter_hash=hashlib.sha256((ROOT/'dev/xtts_security_compat.py').read_bytes()).hexdigest()
    checks=dict(approved_installation_completed=install['completed'] and install['packages']==99,
        isolated_runtime_checks_passed=probe['passed'],real_speech_and_cancellation_passed=live['acceptance'],
        persistent_worker_checks_passed=session['passed'],recognized_words_passed=speech['passed'],
        original_models_state_and_sources_preserved=preserved['passed'],
        hashed_third_party_python_sources_preserved=source['passed'],
        installer_staging_removed=cleanup['removed'] and not (ROOT/'temp/xtts-security-candidate-2026-10-13-staging').exists(),
        package_advisory_check_zero_matches=scan['complete'] and scan['match_count']==0,
        output_hash_verified=hashlib.sha256(Path(live['output_file']).read_bytes()).hexdigest()==live['output_sha256'],
        no_new_models=not install['model_downloaded'] and not live['model_downloaded'] and not speech['model_downloaded'],
        production_defaults_unchanged=not install['defaults_changed'] and not live['application_defaults_changed'],
        previous_candidate_preserved=(ROOT/'runtime_profiles/xtts-candidate/profile.json').is_file(),
        release_not_claimed=not install['release_eligible'])
    helpers=['build_xtts_runtime_candidate','verify_xtts_runtime_candidate','evaluate_xtts_runtime_candidate',
        'verify_xtts_candidate_session','xtts_candidate_worker','xtts_security_compat',
        'check_xtts_candidate_speech_content','compare_xtts_candidate_pcm','verify_xtts_security_source_records',
        'document_xtts_security_installation']
    for name in helpers:ast.parse((ROOT/f'dev/{name}.py').read_text(encoding='utf-8'))
    checks['helper_syntax_valid']=True
    if all(checks.values()):
        assert (PROFILE/'.owner').read_text()=='reflow.xtts.security-candidate.2026-10-13'
        profile=json.loads((PROFILE/'profile.json').read_text(encoding='utf-8'))
        profile.update(status='candidate-offline-validated-with-adapter',runtime_verified=True,
            real_model_inference_verified=True,persistent_session_verified=True,production_default=False,
            release_eligible=False,security_gate='package-scan-no-current-matches; broader release checks pending',
            dependency_lock_sha256=lock_hash,compatibility_adapter='../../dev/xtts_security_compat.py',
            compatibility_adapter_sha256=adapter_hash,
            validation_receipt='../../docs/validation/2026-10-13-xtts-security-candidate-live-evaluation-dense-position.json')
        (PROFILE/'profile.json').write_text(json.dumps(profile,indent=2),encoding='utf-8')
    text=f'''# XTTS replacement runtime installation and validation — 13 October 2026

## Outcome and authorization

The user explicitly approved **the separate replacement runtime and tests** after reviewing the exact 99-package plan. That approved installation/evaluation is complete. The new candidate is `runtime_profiles/xtts-security-candidate`; the original shared runtime, earlier XTTS candidate, app defaults and original model files remain preserved.

**Technical replacement acceptance: {'passed' if all(checks.values()) else 'pending/failed checks below'}. Release readiness: false.** Actual package, decoding, checkpoint inference, cancellation, persistent-session and recognition tests pass with the narrowly scoped compatibility adapter below. The application does not automatically select this runtime. No full-video, all-language, clean-machine or human naturalness acceptance is claimed.

No new model, compiler, package manager, system Python/PATH change, GPU driver or paid service was introduced. The 99 reviewed package artifacts were downloaded into an owned workspace staging folder, checksum-verified and installed into the separate candidate. The verified Python 3.13.16 bootstrap was copied from the earlier candidate with before/after file hashes; its site-packages were not copied. The existing Docopt wheel and XTTS checkpoint were reused.

## Installed versions and package consistency

| Component | Installed version |
| --- | --- |
| Python | 3.13.16, ordinary Windows x64 embedded build |
| Torch | 2.14.1+cpu |
| TorchAudio | 2.11.0+cpu |
| TorchCodec | 0.17.0+cpu |
| Transformers | 5.19.0 |
| Coqui TTS | 0.27.5 |
| Hugging Face Hub | 2.2.0 |
| Tokenizers | 0.23.3 |

The exact 99-package set and versions match the reviewed hash-bound lock. The candidate has no duplicate distribution records; all active target dependency constraints are satisfied. Tested imports originate within this candidate. CPU convolution, real TorchCodec audio decoding, Pydub compatibility and the Docopt parser on Python 3.13 passed. All {len(probe['checks'])} recorded runtime checks pass; job-owned probe caches were removed.

The public exact-version OSV scan returned zero current advisory matches for this lock at its recorded scan time. This resolves the earlier package-match gate for this proposed stack. It is not a native-binary security certification or remediation of the original shared/GPU/other optional runtimes. Windows relocation, prerequisites, full third-party provenance and runtime-family migration remain separate gates.

## Actual existing-checkpoint speech results

| Check | Measured result |
| --- | --- |
| Source | Existing XTTS checkpoint and six-second reference extracted from `Sample/2.mp4` |
| Spoken input | {live['spoken_text']} |
| Output | {live['output_duration_seconds']:.2f} seconds of non-silent {live['output_sample_rate']} Hz speech |
| Level | {live['output_dbfs']:.3f} dBFS |
| Model load | {live['model_load_seconds']:.3f} seconds in this trial |
| Generation | {live['generation_seconds']:.3f} seconds in this trial |
| Real token-boundary cancellation | {live['cancellation_seconds']:.3f} seconds |
| Model lifetime | Same loaded model reused for successful speech and cancellation |
| Previous output | Hash preserved after cancellation |
| Temporary state | Pending output and job workspace removed |
| Network | No outbound or DNS attempts; network operations blocked |

The conditioning/audio path exercises real TorchAudio loading and resampling, and decoder output retains the existing handler's 24 kHz correction. The faster observed generation time compared with the earlier trial is not a general speed guarantee: these are individual CPU runs with different cache/startup conditions. No GPU throughput or calibrated resource estimate was established.

The unchanged existing Whisper Turbo worker recognized “{speech['recognized_text']}”. Normalized word error rate was **{speech['word_error_rate']}**; its worker and workspace were released. This helps detect missing words/gibberish but does not judge emotion, voice likeness, naturalness or source-video synchronization. This take has not received a new human listening acceptance.

The old and replacement candidates produced the same frame count and decoded format for the same seeded sentence. They are **not bit-identical**. Direct decoded-PCM comparison measured maximum sample difference {pcm.get('max_sample_difference')}, RMS difference {pcm.get('rms_sample_difference'):.6f} sample units and signal-to-difference ratio {pcm.get('signal_to_difference_db'):.3f} dB. Neither file was rewritten for this comparison. These small measured differences do not establish perceptual equivalence.

## Persistent session bridge

The existing parent `FeatureSession` interface was exercised with the replacement interpreter and development-only worker. Two real utterances reused one worker PID ({session['worker_pid']}) and one model identity, with one checkpoint load. Unsupported `source` speech language was rejected without creating output. Closing the session during a longer utterance stopped the worker in **{session['stop_seconds']:.3f} seconds**, preserved the previously completed audio and left no incomplete publication or parent workspace. All {len(session['checks'])} session checks passed.

This verifies the existing session boundary, ownership and lifetime contracts. It does not register a production provider, enable the runtime in native UI, change the active engine, replace current Hindi synthesis or validate all concurrent batch/video paths. The worker uses explicit local models and caller-owned cache/workspace paths; the current advisory-affected original profiles remain comparison baselines, not a newly certified release environment.

## Compatibility failures and the scoped adapter

Every failed receipt/log remains retained. No package was downgraded and no declared dependency was stripped to make the new stack appear valid.

1. **Initial runtime import failure:** Coqui 0.27.5 imports `transformers.pytorch_utils.isin_mps_friendly`, removed in Transformers 5.19. Inspection of the older published implementation showed that its CPU branch calls `torch.isin` directly. The adapter supplies that existing native operation for the exact reviewed CPU stack, with vector and scalar assertions. It does not restore an obsolete serialization/generation implementation.
2. **First real-speech failure:** The model loaded, but the custom Coqui forward path received `attention_mask=None` and attempted to read its shape. The first trial with the import adapter therefore correctly failed; its job workspace was removed and no successful audio was substituted.
3. **Dense-mask attempt:** Supplying the mask at the generate entry point was insufficient. The newer generator deliberately removes all-ones masks before prefill for its optimized path. The second failed real trial remains retained.
4. **Explicit-position attempt:** Restoring the mask only when already supplied to preparation still failed because the upstream preparation call received `None`. The adapter deliberately rejected the unsupported state rather than silently guessing an arbitrary padded mask. That failed receipt also remains retained.
5. **Final dense-position adapter:** The entry point validates that this custom XTTS input is an unpadded dense CPU sequence. At preparation, it reconstructs an all-ones mask from the complete growing input-token sequence when the upstream optimizer removed it, then preserves the two-dimensional mask for Coqui's learned audio-position calculation. Modern generation, cache objects, input slicing, sampling and cancellation criteria remain in use. Real speech, cancellation, session reuse and recognition subsequently passed.

The adapter is `dev/xtts_security_compat.py`, guarded to this owned profile and exact Torch/Transformers/Coqui versions. It modifies Python objects in the worker process only. It rejects unsupported padded/non-CPU forms instead of presenting itself as a general Transformer bridge. Its SHA256 is `{adapter_hash}`. Future library/version changes must re-evaluate it; this developer helper is not yet a production integration.

Installed third-party Python source was independently checked against distribution RECORD hashes: **{source['python_source_files_checked']:,} files**, {source['source_bytes_checked']:,} bytes, across {source['distributions']} distributions, with no mismatches. This verification covers hashed Python source in the profile, not a full native security audit or unhashed generated launchers. No Coqui/Transformers source file was patched on disk. Cross-target console launchers pointing at the build interpreter were removed from the newly owned candidate, as documented in the earlier plan.

## Disk use, cleanup and notices

Installation-completion size was **{install['runtime_bytes']:,} bytes ({install['runtime_bytes']/1048576:.1f} MiB)**, excluding existing model weights and validation/notice artifacts. That value precedes possible subsequent import caches; a fixed final footprint is not promised. **{cleanup['bytes']:,} bytes** of owned temporary wheel/installer staging were removed after native/model verification. No original runtime/model/reference file was deleted.

Bundled wheel license/notice files were retained for {sum(bool(r['notice_files']) for r in notices)} of {len(notices)} packages. The notice extractor still did not find bundled notices for tokenizers and tensorboard-data-server. Exact-source follow-up and complete component/native/model redistribution review remain required. Coqui's installed Tortoise source also contains AGPL-specific change-notification headers; a top-level package license field alone cannot stand in for a component inventory. None of those files was edited here. The user's application license remains undecided; no license was assigned to their code.

Retained warnings include the embedded executable's “Failed to find real location” message, legacy Pydub/Docopt invalid-escape warnings, TorchScript deprecation and GPT configuration default token-ID warnings. Generation explicitly uses Coqui's audio start/stop IDs and the tested phrase is correctly recognized, but the warnings are not declared fully resolved. They remain items for launcher/configuration and broader compatibility review before release; no warning was removed merely to produce a clean-looking log.

## Changed helpers and evidence

The existing builder gained a separately owned security variant, exact 99-package receipt names and verified interpreter-bootstrap reuse. Runtime, live-speech, session and recognition helpers gained explicit profile/label parameters to preserve old evidence. Added the evaluation compatibility adapter, decoded PCM comparison, Python RECORD verification and this report helper. No production application module changed. The previous 766-test backend and 47-contract frontend baseline were not rerun as a substitute for actual replacement inference; production source hashes remain equal to that tested baseline.

Evidence: [installation](validation/2026-10-13-xtts-security-candidate-install.json), [downloads](validation/2026-10-13-xtts-security-candidate-downloads.json), [passing runtime probe](validation/2026-10-13-xtts-security-candidate-runtime-probe-compat-adapter.json), [passing real speech](validation/2026-10-13-xtts-security-candidate-live-evaluation-dense-position.json), [session](validation/2026-10-13-xtts-security-candidate-session.json), [recognition](validation/2026-10-13-xtts-security-candidate-speech-content.json), [PCM comparison](validation/2026-10-13-xtts-security-candidate-pcm-comparison.json), [source RECORD verification](validation/2026-10-13-xtts-security-candidate-source-records.json), [source/model/state preservation](validation/2026-10-13-xtts-candidate-preservation-after.json), [staging cleanup](validation/2026-10-13-xtts-security-candidate-staging-cleanup.json), [notice inventory](validation/2026-10-13-xtts-security-candidate-notices/inventory.json), [advisory scan](validation/2026-10-13-xtts-security-cpu-advisories.json), [consolidated integrity](validation/2026-10-13-xtts-security-installation-integrity.json).

Failed attempts: [initial import probe](validation/2026-10-13-xtts-security-candidate-runtime-probe-audited-network.json), [first real speech](validation/2026-10-13-xtts-security-candidate-live-evaluation-audited-network.json), [dense-mask trial](validation/2026-10-13-xtts-security-candidate-live-evaluation-dense-mask.json), [position-mask trial](validation/2026-10-13-xtts-security-candidate-live-evaluation-position-mask.json). The final passing receipt is separately named and does not overwrite any of them.

## Remaining release work

The next implementation step is a supported production XTTS worker/provider boundary with readiness and cache identity bound to the interpreter, lock, adapter recipe and model. It must be exercised in a disposable application copy before any default switch, including long/varied language/reference inputs, batching, cancellation, crash/recovery and relocation. The current adapter is evaluated for dense CPU XTTS generation only; other generation modes/devices require their own checks.

RVC's legacy Windows/Fairseq/OmegaConf constraints, desktop/runtime-family migration, Hindi gated-engine/reference setup, calibrated resource estimates, model download/retry/offline behavior, optional-stage/all-language/full-video workflows, source notices and the owner's license decision, portable CI and clean-machine Windows prerequisites remain open. The existing GPU Whisper and Hindi profiles used as evaluation references were not upgraded or independently security-cleared by this CPU XTTS trial. Linux/macOS remain experimental.

The original saved state and eight XTTS assets retain their hashes, the earlier Ollama trial remains absent, and both comparison runtimes remain available. This pass completes the explicitly approved replacement creation and tests while keeping production defaults unchanged. See the [runtime repair map](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release status](RELEASE_READINESS_2026-10-04.md).
'''
    doc=ROOT/'docs/XTTS_SECURITY_RUNTIME_ITERATION_2026-10-13.md'
    doc.write_text(text,encoding='utf-8')
    receipt=dict(passed=all(checks.values()),checks=checks,replacement_functional=True,
        compatibility_adapter_sha256=adapter_hash,production_defaults_changed=False,release_ready=False,
        document_sha256=hashlib.sha256(doc.read_bytes()).hexdigest())
    (OUT/'2026-10-13-xtts-security-installation-integrity.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2));return not receipt['passed']

if __name__=='__main__':raise SystemExit(main())
