"""Repository transfers run in an owned process so cancellation can stop them."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.download_failures import describe_download_failure


def main():
    params = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=params['repo_id'], local_dir=params['dest_dir'],
                          cache_dir=params['cache_dir'], allow_patterns=params['allow_patterns'],
                          revision=params['revision'], max_workers=2)
    except Exception as error:
        if params.get('failure_path'):
            Path(params['failure_path']).write_text(json.dumps(describe_download_failure(error)), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
