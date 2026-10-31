"""Read-only cleanup/state audit for the temporary evaluation receipt."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('receipt',type=Path)
    args=parser.parse_args()
    report=json.loads(args.receipt.read_text(encoding='utf-8'))
    owned=Path(report['temporary_root'])
    if owned.resolve()!=owned or not owned.is_relative_to((ROOT/'temp').resolve()) or not owned.name.startswith('ollama-eval-'):
        raise RuntimeError('Receipt has an unexpected evaluation path')
    baseline=json.loads((ROOT/'docs/validation/2026-10-10-control-paths-state-integrity.json').read_text(encoding='utf-8'))
    state={name:sha(ROOT/name)==record['current'].lower() for name,record in baseline['state'].items()}
    review=json.loads((ROOT/'docs/validation/2026-10-12-live-workflow-human-review.json').read_text(encoding='utf-8'))
    checks={
        'owned_runtime_model_and_archive_directory_absent':not owned.exists(),
        'evaluation_confirms_cleanup':report.get('temporary_runtime_models_removed') is True,
        'existing_ollama_paths_preserved':all(Path(path).exists()==existed for path,existed in report['prior_external_ollama_paths'].items()),
        'no_global_install':report['global_install'] is False,
        'saved_app_state_unchanged':all(state.values()) and report.get('saved_state_unchanged') is True,
        'human_accepted_video_unchanged':sha(review['output'])==review['output_sha256'],
        'no_paid_calls':report['paid_calls'] is False,
    }
    result=dict(passed=all(checks.values()),checks=checks,state=state,receipt=str(args.receipt.resolve()),
        receipt_sha256=sha(args.receipt),removed_bytes=report.get('removed_bytes'),
        retained_material='Evaluation JSON and bounded diagnostic log only; no Ollama binaries, models, keys or archive')
    destination=args.receipt.with_name(args.receipt.stem+'-cleanup.json')
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
