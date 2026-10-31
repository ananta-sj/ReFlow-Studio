"""Finish the approved download then run comparison and write its review artifact."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    started = time.monotonic()
    status = dict(completed=False, stage='download', production_changed=False)
    receipt = ROOT / 'docs/validation/2026-10-08-indictrans2-evaluation-run.json'
    env = {**os.environ, 'PYTHONIOENCODING':'utf-8', 'PYTHONHASHSEED':'0'}
    def save():
        status['elapsed_seconds'] = round(time.monotonic()-started, 3)
        receipt.write_text(json.dumps(status, indent=2), encoding='utf-8')
    try:
        save()
        for stage, interpreter, script in (
            ('download', 'build/windows-portable/python.exe', 'dev/download_indictrans2_http_ranges.py'),
            ('comparison', 'runtime_profiles/indictrans2-evaluation/python.exe', 'dev/compare_indictrans2_evaluation.py')):
            status['stage'] = stage
            save()
            log = ROOT / 'docs/validation' / ('2026-10-08-indictrans2-'+stage+'-run.log')
            with log.open('w', encoding='utf-8') as output:
                result = subprocess.run([str(ROOT / interpreter), str(ROOT / script)], cwd=str(ROOT),
                    env=env, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            status[stage+'_exit_code'] = result.returncode
            if result.returncode:
                raise RuntimeError(stage+' failed; inspect its receipt/log')
        comparison = json.loads((ROOT / 'docs/validation/2026-10-08-indictrans2-comparison.json').read_text(encoding='utf-8'))
        baseline = json.loads((ROOT / 'docs/validation/2026-10-08-nllb-comparison-baseline.json').read_text(encoding='utf-8'))
        assert comparison['completed'] and baseline['completed']
        nllb = {row['id']:row for row in baseline['cases']}
        def cell(text):
            return str(text).replace('|', '\\|').replace('\n', ' ')
        lines = ['# Hindi translation comparison — 8 October 2026', '',
                 'Both engines ran offline on the same 19 inputs. Production defaults are unchanged. '
                 'These are generated candidates for human review; no automatic semantic winner or release approval is claimed.', '',
                 f"IndicTrans2 revision: `{comparison['model_revision']}`. Transformers {comparison['transformers_version']}; "
                 'FP16 CUDA, eager attention, five beams, deterministic decoding.', '',
                 f"IndicTrans2 peak allocated GPU memory: {comparison['peak_cuda_allocated_bytes']/1024**3:.3f} GiB. "
                 f"Model load: {comparison['load_seconds']} seconds. Full evaluation: {comparison['elapsed_seconds']} seconds.", '',
                 'The historical pure-Python toolkit and its Indic NLP wheel substitution remain evaluation-only. '
                 'Synthetic preprocessing revealed phone-number spacing changes. Check every quantity, negation, '
                 'name, idiom and film term below before using these translations in a dub.', '',
                 '| Case | Source | NLLB | IndicTrans2 |', '| --- | --- | --- | --- |']
        for row in comparison['cases']:
            previous = nllb[row['id']]
            assert previous['source'] == row['source'], 'Comparison sources differ'
            lines.append('| '+' | '.join(cell(x) for x in (row['id'], row['source'], previous['translation'], row['translation']))+' |')
        lines += ['', '## Evidence', '',
                  '- `docs/validation/2026-10-08-indictrans2-download-weights.json`: pinned size and remote SHA256 verification.',
                  '- `docs/validation/2026-10-08-indictrans2-comparison.json`: tokens, completion guards, timing and GPU memory.',
                  '- `docs/validation/2026-10-08-nllb-comparison-baseline.json`: existing provider outputs and workspace cleanup.',
                  '- `docs/INDICTRANS2_EVALUATION_2026-10-08.md`: preparation, packages, failures, limitations and provenance.', '',
                  'Next: human Hindi meaning/style review, then a controlled dubbed-video comparison if accepted.']
        artifact = ROOT / 'docs/HINDI_TRANSLATION_COMPARISON_2026-10-08.md'
        artifact.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        status.update(completed=True, stage='ready-for-human-review', artifact=str(artifact))
    except Exception as exc:
        status.update(error_type=type(exc).__name__, error=str(exc))
    finally:
        save()
        print(json.dumps(status), flush=True)
    if not status['completed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
