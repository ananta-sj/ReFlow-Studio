"""Repository transfers run in an owned process so cancellation can stop them."""
import json
from pathlib import Path
import sys
from huggingface_hub import snapshot_download

params = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
snapshot_download(repo_id=params['repo_id'], local_dir=params['dest_dir'],
                  cache_dir=params['cache_dir'], allow_patterns=params['allow_patterns'],
                  revision=params['revision'], max_workers=2)
