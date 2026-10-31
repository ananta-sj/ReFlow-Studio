import concurrent.futures
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from core.model_assets import ASSETS

def check(asset):
    relative, url, expected = asset
    try:
        r = requests.head(url, allow_redirects=True, timeout=(10, 20))
        return {'path': relative, 'url': url, 'status': r.status_code, 'remote_bytes': r.headers.get('Content-Length'), 'expected_bytes': expected}
    except Exception as e:
        return {'path': relative, 'url': url, 'error': str(e)}

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, [a for group in ASSETS.values() for a in group]))
    print(json.dumps(results, indent=2))
