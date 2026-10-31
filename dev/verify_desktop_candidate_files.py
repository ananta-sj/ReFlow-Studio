"""Verify installed RECORD payloads and preservation against retained evidence."""
import base64
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PROFILE = ROOT / 'runtime_profiles/desktop-candidate'
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    global PROFILE
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='final')
    parser.add_argument('--recognition', action='store_true')
    args = parser.parse_args()
    prefix = '2026-10-15-recognition-candidate' if args.recognition else '2026-10-14-desktop-candidate'
    if args.recognition:
        PROFILE = ROOT / 'runtime_profiles/recognition-candidate'
    assert args.label.replace('-', '').isalnum()
    site = PROFILE / 'Lib/site-packages'
    checked = 0
    skipped_launchers = []
    failures = []
    for record in site.glob('*.dist-info/RECORD'):
        for name, digest, size in csv.reader(record.open(encoding='utf-8', newline='')):
            path = (site / name).resolve()
            if not digest:
                continue
            removed_launchers = {'../../bin/bottle.exe', '../../bin/bottle.py', '../../bin/normalizer.exe',
                                 '../../bin/idna.exe', '../../bin/keyring.exe', '../../bin/f2py.exe',
                                 '../../bin/numpy-config.exe', '../../bin/tqdm.exe'}
            if args.recognition:
                removed_launchers = {'../../bin/ct2-fairseq-converter.exe', '../../bin/ct2-marian-converter.exe',
                    '../../bin/ct2-openai-gpt2-converter.exe', '../../bin/ct2-opennmt-py-converter.exe',
                    '../../bin/ct2-opennmt-tf-converter.exe', '../../bin/ct2-opus-mt-converter.exe',
                    '../../bin/ct2-transformers-converter.exe', '../../bin/f2py.exe', '../../bin/numpy-config.exe',
                    '../../bin/tqdm.exe', '../../bin/isympy.exe', '../../bin/hf.exe', '../../bin/tiny-agents.exe',
                    '../../bin/onnxruntime_test.exe', '../../bin/httpx2.exe', '../../bin/pyav.exe', '../../bin/idna.exe'}
            if not path.is_file() and name in removed_launchers:
                skipped_launchers.append(name)
                continue
            if not path.is_relative_to(PROFILE.resolve()) or not path.is_file():
                failures.append(name + ': missing or unsafe')
                continue
            algorithm, expected = digest.split('=', 1)
            if algorithm != 'sha256':
                failures.append(name + ': unsupported digest')
                continue
            actual = base64.urlsafe_b64encode(bytes.fromhex(sha(path))).decode().rstrip('=')
            if actual != expected or path.stat().st_size != int(size):
                failures.append(name + ': hash/size mismatch')
            checked += 1
    baseline = json.loads((OUT / '2026-10-13-desktop-runtime-boundary-integrity.json').read_text())
    states = json.loads((OUT / '2026-10-10-control-paths-state-integrity.json').read_text())['state']
    assets = json.loads((OUT / '2026-10-13-xtts-candidate-preservation-before.json').read_text())['assets']
    from core.xtts_runtime import validate
    checks = dict(installed_record_payloads_verified=not failures,
                  original_sources_preserved=all(sha(ROOT / name) == value for name, value in baseline['source_sha256'].items()),
                  original_state_preserved=all(sha(ROOT / name) == row['current'].lower() for name, row in states.items()),
                  original_models_preserved=all(sha(ROOT / name) == value for name, value in assets.items()),
                  original_xtts_identity_preserved=validate()['identity'] == baseline['xtts_runtime_identity'],
                  ollama_absent=not (ROOT / 'temp/ollama-eval-c_lslq8w').exists())
    inventory = json.loads((OUT / (prefix + '-notices/inventory.json')).read_text())
    result = dict(passed=all(checks.values()), checks=checks, payload_files_checked=checked,
                  failures=failures, intentionally_removed_cli_launchers=skipped_launchers,
                  notice_packages_with_files=sum(bool(row['notice_files']) for row in inventory),
                  notice_packages_without_files=[row['name'] for row in inventory if not row['notice_files']],
                  candidate_bytes=sum(path.stat().st_size for path in PROFILE.rglob('*') if path.is_file()),
                  packages=24 if args.recognition else 31, release_ready=False)
    (OUT / (prefix + '-file-integrity-' + args.label + '.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
