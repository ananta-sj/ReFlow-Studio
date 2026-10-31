"""Record official model revision and access status without exposing credentials."""
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
if (ROOT / 'models/indicf5/evaluation/auth/token').is_file():
    os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')


def main():
    from huggingface_hub import HfApi, hf_hub_download, get_token
    report = dict(repository='ai4bharat/IndicF5', access_checked=False,
                  cached_credential_present=bool(get_token()), model_code_executed=False)
    started = time.monotonic()
    try:
        info = HfApi().model_info(report['repository'], files_metadata=True)
        report.update(revision=info.sha, gated=info.gated,
                      files=[dict(name=item.rfilename, size=item.size) for item in info.siblings])
        path = hf_hub_download(report['repository'], filename='config.json', revision=info.sha,
                               cache_dir=str(ROOT / 'models/indicf5/evaluation/cache'))
        report.update(access_checked=True, access_granted=True, config_path=path)
    except Exception as exc:
        response = getattr(exc, 'response', None)
        report.update(access_checked=True, access_granted=False, error_type=type(exc).__name__,
                      http_status=getattr(response, 'status_code', None))
    report['elapsed_seconds'] = round(time.monotonic()-started, 3)
    (ROOT / 'docs/validation/2026-10-06-indicf5-access.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}))


if __name__ == '__main__':
    main()
