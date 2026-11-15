# XTTS helper build and dependency-lock preparation — 13 October 2026

## Outcome and authorization

The user approved **only the helper build and dependency-lock preparation**. That work is complete. No runtime was installed, no existing package was upgraded or removed, and no AI model was loaded or downloaded. Windows portable remains the first release target; this pass does not establish release readiness.

The target is ordinary Windows x64 CPython 3.13.16 with CPU PyTorch. The reviewed closure contains **85 packages and 128 active dependency links**, all satisfied according to published metadata and target wheel tags. This is a proposed XTTS worker, not a replacement for the current shared runtime, a resolved desktop environment or a repaired RVC environment.

## Approved Docopt build

The indirect dependency chain is `coqui-tts → num2words → docopt`. Docopt is an argument parser, not a speech model. Version 0.6.2 has a source archive but no published wheel, which prevented the initial binary-only resolver from completing.

- The downloaded source was exactly **25,901 bytes**. Its SHA256 matched the previously reviewed PyPI value: `49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491`.
- Archive members were checked for traversal, absolute targets, links, devices and excessive count/size before extraction into an owned workspace temporary folder.
- The retained setup declares a single Python module and no native extension or installation dependency. The build used the existing Python 3.10.11, setuptools 80.10.2 and wheel 0.47.0. No compiler, new packaging tool or build environment was installed.
- The command was `python -B -X utf8 setup.py bdist_wheel --dist-dir <retained-evidence-directory>`. It produced `docopt-0.6.2-py2.py3-none-any.whl`, **13,857 bytes**. Its SHA256 is `f9303dca1215f1dd0f784ab91347fa6e95df44396f3f19c9079f0faa1efa20b6`.
- Wheel metadata name/version, module/source byte equality, safe wheel paths, included license and all hashed RECORD entries were checked. A real `--quiet` argument-parsing assertion passed with the wheel on the existing interpreter's import path; it was not installed.
- The first verification assumed LF metadata lines; the wheel used different line endings. That assertion failed after the build. Validation was corrected to parse email-style headers, the build reran, and all checks passed. This was a validation error, not a package-install failure.
- Both owned temporary build folders were removed. The verified source archive, wheel, setup recipe, MIT notice, successful build log and receipt are intentionally retained for review/reproducibility.

The universal wheel tag permits selection for the proposed target, but **execution on Python 3.13 is untested**. The new interpreter was not downloaded under this approval. Actual packaging-tool versions are recorded as imported from the existing runtime, whose broader package metadata remains inconsistent; that runtime is not certified by this build.

## Resolution history and network boundary

Historical failed direct-URL and missing-Docopt attempts remain in the validation folder. After adding the approved local wheel, the resolver progressed to Colorama but the PyTorch mirror offered an archive without usable separate metadata. The network guard blocked that archive GET before transfer. Its failure log/receipt remain retained.

The CPU mirror was then limited to `torch`, `torchaudio` and `torchcodec`. Other packages resolve from PyPI. The final dry run completed using package index pages and separate wheel metadata; remote archive GETs remained blocked. `--dry-run`, `--ignore-installed`, `--no-cache-dir`, `--only-binary=:all:` and explicit CPython 3.13/Windows x64 target arguments were used. The approved local wheel was bound to its recorded hash. No source build was permitted within the resolver itself.

Pip's cross-target resolution can still evaluate some environment markers against the host Python. Independent checking therefore evaluated required extras to a fixed point, target Python/OS markers, version constraints, root pins, wheel tags and artifact SHA256 availability. The initial dry run selected 86 packages; `async-timeout` is required only for older Python and was excluded from the target lock after reachability analysis. The retained raw report preserves this difference. All 128 active target dependency links are satisfied.

Each selected transitive package is listed below with its requesting parent(s), so its reason is reviewable. For example, `aiohttp` is required through the `fsspec[http]` extra. The candidate does not request Coqui's `[all]`, server or notebook extras. Trainer/tensorboard dependencies are still required by the selected base package and were retained; removing them without changing/validating the package recipe would not be a correct dependency lock.

## Download and disk budget

The 85 selected package artifacts total **279,567,278 bytes (266.6 MiB)**, including the already-built local Docopt wheel. If that wheel is reused, remote package archives would total **279,553,421 bytes**. These are planned download sizes, not downloads performed in this pass. PyPI JSON verified exact filenames/hashes/sizes; official PyTorch HEAD responses provided the CPU wheel sizes. The mirror denied the first HEAD requests with HTTP 403; primary-host HEAD requests succeeded. No response body containing a package archive was fetched.

This total excludes the Python interpreter archive, extracted package size, installed runtimes, temporary installation overlap and existing model weights. Exact installed disk usage requires an approved staged installation and measurement. CPU packages were chosen for this first dependency evaluation; GPU testing would require separately reviewed matching artifacts. Existing weights and FFmpeg libraries would be reused only after their paths and compatibility are verified.

## Exact candidate package inventory

The JSON lock retains each artifact URL, filename, SHA256, declared license fields, requested extras and every active dependency link. The text lock binds exact artifact URLs and hashes. Its Docopt `file:` URL is specific to this workspace; a portable installer must deliberately rewrite that reference to the retained owned wheel, preserving the hash. This review lock is not an approved installation command.

| Package | Version | Archive bytes | Reason / requesting packages |
| --- | --- | ---: | --- |
| `absl-py` | 2.5.1 | 137,673 | tensorboard |
| `aiohappyeyeballs` | 2.7.1 | 15,038 | aiohttp |
| `aiohttp` | 3.14.3 | 476,518 | HTTP helper for fsspec[http]; final dependency closure must confirm this edge |
| `aiosignal` | 1.4.0 | 7,490 | aiohttp |
| `anyascii` | 0.3.3 | 345,090 | Maintained Coqui text transliteration requirement |
| `attrs` | 26.1.0 | 67,548 | aiohttp |
| `audioop-lts` | 0.2.2 | 30,503 | Provides audioop removed from Python 3.13, needed by pydub |
| `certifi` | 2026.7.22 | 136,983 | requests |
| `cffi` | 2.1.1 | 185,688 | soundfile |
| `charset-normalizer` | 3.5.2 | 206,489 | requests |
| `cloudpickle` | 3.1.2 | 22,228 | joblib |
| `colorama` | 0.4.6 | 25,335 | tqdm |
| `contourpy` | 1.4.0 | 234,084 | matplotlib |
| `coqpit-config` | 0.2.5 | 15,018 | coqui-tts, coqui-tts-trainer |
| `coqui-tts` | 0.27.5 | 862,766 | Maintained library for the existing XTTS model, in its own candidate worker |
| `coqui-tts-trainer` | 0.3.3 | 56,187 | coqui-tts |
| `cycler` | 0.12.1 | 8,321 | matplotlib |
| `decorator` | 5.3.1 | 10,365 | librosa |
| `docopt` | 0.6.2 | 13,857 | num2words |
| `einops` | 0.8.2 | 65,638 | coqui-tts |
| `filelock` | 4.1.1 | 132,460 | huggingface-hub, torch, transformers |
| `fonttools` | 4.66.1 | 2,485,146 | matplotlib |
| `frozenlist` | 1.8.0 | 43,882 | aiohttp, aiosignal |
| `fsspec` | 2026.9.0 | 221,738 | coqui-tts, coqui-tts-trainer, huggingface-hub, torch |
| `grpcio` | 1.84.0 | 5,255,326 | tensorboard |
| `huggingface-hub` | 0.36.2 | 566,395 | tokenizers, transformers |
| `idna` | 3.20 | 69,583 | requests, yarl |
| `inflect` | 7.5.0 | 35,197 | coqui-tts |
| `jinja2` | 3.1.6 | 134,899 | torch |
| `joblib` | 1.6.0 | 306,115 | librosa, scikit-learn |
| `kiwisolver` | 1.5.1 | 70,758 | matplotlib |
| `ko-speech-tools` | 0.1.0 | 997,279 | coqui-tts |
| `lazy-loader` | 0.6 | 8,791 | librosa |
| `librosa` | 1.0.0 | 294,628 | coqui-tts |
| `llvmlite` | 0.46.0 | 38,138,941 | Compiler library required by this Numba version, supplied as a wheel |
| `markdown` | 3.11 | 111,296 | tensorboard |
| `markupsafe` | 3.0.4 | 14,313 | jinja2, werkzeug |
| `matplotlib` | 3.11.2 | 9,349,539 | coqui-tts |
| `monotonic-alignment-search` | 0.2.1 | 229,778 | coqui-tts |
| `more-itertools` | 11.1.0 | 72,226 | inflect |
| `mpmath` | 1.3.0 | 536,198 | sympy |
| `msgpack` | 1.2.3 | 76,569 | librosa |
| `multidict` | 6.9.1 | 59,449 | aiohttp, yarl |
| `narwhals` | 2.27.1 | 483,211 | scikit-learn |
| `networkx` | 3.7 | 2,142,205 | torch |
| `num2words` | 0.5.14 | 163,525 | coqui-tts |
| `numba` | 0.63.1 | 2,750,228 | Compiled numeric operations used by the audio dependency chain |
| `numpy` | 2.3.5 | 12,779,090 | CPython 3.13 numerical wheel; old RVC cap cannot share this environment |
| `packaging` | 26.3 | 129,956 | coqui-tts, coqui-tts-trainer, huggingface-hub, lazy-loader, matplotlib, pooch, tensorboard, transformers |
| `pillow` | 12.3.0 | 7,239,691 | matplotlib, tensorboard |
| `platformdirs` | 4.13.0 | 32,724 | pooch |
| `pooch` | 1.9.0 | 67,175 | librosa |
| `propcache` | 0.5.4 | 45,342 | aiohttp, yarl |
| `protobuf` | 7.36.2 | 456,514 | tensorboard |
| `psutil` | 7.2.2 | 137,737 | coqui-tts-trainer |
| `pycparser` | 3.11 | 51,178 | cffi |
| `pydub` | 0.25.1 | 32,327 | Existing Reflow audio preparation and validation |
| `pyparsing` | 3.3.3 | 126,420 | matplotlib |
| `pysbd` | 0.3.4 | 71,082 | coqui-tts |
| `python-dateutil` | 2.9.0.post0 | 229,892 | matplotlib |
| `pyyaml` | 6.0.3 | 154,090 | coqui-tts, huggingface-hub, transformers |
| `regex` | 2026.9.29 | 280,307 | transformers |
| `requests` | 2.34.2 | 73,075 | huggingface-hub, pooch, transformers |
| `safetensors` | 0.8.0 | 355,540 | transformers |
| `scikit-learn` | 1.9.1 | 8,237,244 | librosa |
| `scipy` | 1.16.3 | 38,529,877 | Speech signal processing; satisfies maintained Coqui requirement |
| `setuptools` | 84.0.0 | 818,216 | tensorboard, torch |
| `six` | 1.17.0 | 11,050 | python-dateutil |
| `soundfile` | 0.13.1 | 1,019,162 | Audio loading and writing using the existing interface |
| `soxr` | 1.1.0 | 174,357 | librosa |
| `sympy` | 1.14.0 | 6,299,353 | torch |
| `tensorboard` | 2.21.0 | 5,516,204 | coqui-tts-trainer |
| `tensorboard-data-server` | 0.7.2 | 2,356 | tensorboard |
| `threadpoolctl` | 3.7.0 | 26,362 | scikit-learn |
| `tokenizers` | 0.22.2 | 2,747,786 | transformers |
| `torch` | 2.9.1+cpu | 110,859,971 | CPU inference proof before a separate approved GPU evaluation |
| `torchaudio` | 2.9.1+cpu | 663,050 | Matching Torch audio implementation |
| `torchcodec` | 0.8.1 | 2,107,715 | Audio decoding paired with Torch 2.9 and existing shared FFmpeg |
| `tqdm` | 4.70.1 | 80,199 | coqui-tts, huggingface-hub, transformers |
| `transformers` | 4.57.1 | 11,990,925 | Coqui minimum 4.57; preserves below-5 candidate boundary |
| `typeguard` | 4.6.0 | 36,884 | inflect |
| `typing-extensions` | 4.16.0 | 45,571 | coqpit-config, coqui-tts, grpcio, huggingface-hub, torch, typeguard |
| `urllib3` | 2.8.0 | 135,717 | requests |
| `werkzeug` | 3.1.9 | 228,700 | tensorboard |
| `yarl` | 1.25.1 | 101,945 | aiohttp |

## Files changed and retained evidence

- `dev/build_approved_docopt_helper.py`: the bounded source download, safe extraction, isolated existing-tool build, wheel/parser checks and owned temporary cleanup.
- `dev/resolve_runtime_plan_metadata_only.py`: hash-bound local helper input, separate labelled evidence, restricted CPU mirror and archive-transfer guard.
- `dev/check_xtts_candidate_closure.py`: independent target marker/extras/version/tag checks, host-only package exclusion and review locks.
- `dev/measure_xtts_lock_metadata.py`: package size/hash metadata and CPU archive HEAD measurement only.
- `dev/prepare_runtime_repair_plan.py`: records the scoped helper approval, completed metadata closure and download budget while retaining `install_authorized=false` and `release_ready=false`.
- `dev/document_xtts_lock_preparation.py`: this completion inventory and state/source/cleanup integrity receipt.
- The repair plan and release-readiness document now reflect completion of this bounded step.

Evidence: [Docopt receipt](validation/2026-10-13-docopt-helper/receipt.json), [successful build log](validation/2026-10-13-docopt-helper/build.log), [MIT notice](validation/2026-10-13-docopt-helper/LICENSE-MIT), [guarded failed mirror receipt](validation/2026-10-13-metadata-only-with-docopt-receipt.json), [successful metadata-only receipt](validation/2026-10-13-metadata-only-scoped-mirror-receipt.json), [raw resolution report](validation/2026-10-13-xtts-scoped-mirror-resolution-report.json), [target review lock](validation/2026-10-13-xtts-candidate-lock-review.json), [hash-bound text lock](validation/2026-10-13-xtts-candidate-review.lock.txt), [download budget](validation/2026-10-13-xtts-download-budget.json), [completion integrity](validation/2026-10-13-xtts-lock-preparation-integrity.json).

## Remaining gates and next bounded step

No production runtime/defaults, settings, graph, hardware profile, model registry, preferences, voices or accepted output media were intentionally changed. Previous production-source hashes and all five protected state hashes are checked again below. The earlier temporary Ollama trial remains absent. Full backend tests were not repeated because this pass changes planning/build helpers and documentation, not production code.

Before installation: review this exact candidate, complete package notice/vulnerability review, define owned interpreter/staging locations and obtain a separate approval for interpreter/package downloads and isolated candidate creation. Package metadata license fields are inventory clues, not completed redistribution/legal clearance. The application license remains the owner's unresolved decision.

After an approved staged installation: verify installed metadata consistency and import origins; measure installed disk size; run CPU/audio decoding and existing XTTS weights offline; check cancellation/output preservation/cleanup; compare voice quality and timing; then validate the app-worker bridge in a disposable copy before considering a default switch. RVC's Windows/Fairseq/OmegaConf conflicts, desktop and other profile closures, fresh-user setup, clean-machine validation and remaining full-workflow release gates are unchanged. See the [repair plan](RUNTIME_REPAIR_PLAN_2026-10-13.md) and [release status](RELEASE_READINESS_2026-10-04.md).
