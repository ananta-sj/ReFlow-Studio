"""Download pinned, approved IndicTrans2 assets without executing model code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
REVISION = '89cd0007fd7b9e0693a2fd4404d187e07dac79fd'
os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '120'
os.environ['HF_HUB_DISABLE_XET'] = '1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', action='store_true')
    args = parser.parse_args()
    from huggingface_hub import HfApi, hf_hub_download
    destination = ROOT / 'models/translation/indictrans2-evaluation'
    destination.mkdir(parents=True, exist_ok=True)
    names = ['LICENSE', 'README.md', 'config.json', 'configuration_indictrans.py',
             'modeling_indictrans.py', 'tokenization_indictrans.py', 'tokenizer_config.json',
             'special_tokens_map.json', 'generation_config.json', 'dict.SRC.json',
             'dict.TGT.json', 'model.SRC', 'model.TGT']
    if args.weights:
        names.append('model.safetensors')
    report = dict(repository='ai4bharat/indictrans2-en-indic-1B', revision=REVISION,
                  weights_requested=args.weights, complete=False, model_code_executed=False,
                  transfer_backend='standard-http',
                  files=[])
    receipt = ROOT / 'docs/validation' / ('2026-10-08-indictrans2-download-' +
                                        ('weights' if args.weights else 'source') + '.json')
    started = time.monotonic()
    def save():
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        receipt.write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        info = HfApi().model_info(report['repository'], revision=REVISION, files_metadata=True)
        expected = {item.rfilename: item for item in info.siblings}
        report['expected_bytes'] = {name: expected[name].size for name in names}
        save()
        for name in names:
            report['downloading'] = name
            save()
            print(json.dumps(dict(downloading=name, bytes=expected[name].size)), flush=True)
            path = Path(hf_hub_download(report['repository'], filename=name, revision=REVISION,
                                       local_dir=str(destination)))
            checksum = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    checksum.update(chunk)
            row = dict(name=name, bytes=path.stat().st_size, sha256=checksum.hexdigest())
            assert row['bytes'] == expected[name].size, 'Downloaded size differs from pinned metadata'
            lfs = expected[name].lfs
            remote = (lfs.get('sha256') if isinstance(lfs, dict) else getattr(lfs, 'sha256', None)) if lfs else None
            if remote:
                row['remote_sha256_matches'] = row['sha256'] == remote
                assert row['remote_sha256_matches'], 'Downloaded checksum differs from pinned metadata'
            report['files'].append(row)
            save()
        report['complete'] = True
        report.pop('downloading', None)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        raise
    finally:
        save()
        print(json.dumps(dict(receipt=str(receipt), complete=report['complete'])), flush=True)


if __name__ == '__main__':
    main()
