"""Explicit pre-download for offline use; run --help to choose features."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.model_assets import ASSETS, ROOT, ensure_assets
from core.json_store import JsonStore
from core.model_registry import _validate


def record_restored(feature, root=ROOT):
    """Refresh matching Marketplace entries after explicit local recovery."""
    destinations = {
        'xtts': ('https://huggingface.co/coqui/XTTS-v2', 'models/xtts/default'),
        'musetalk': ('https://huggingface.co/TMElyralab/MuseTalk', 'core/MuseTalk/models'),
    }
    if feature not in destinations:
        return
    registry_path = Path(root) / 'models.json'
    if not registry_path.exists():
        return
    url, relative = destinations[feature]
    def restore(data):
        for entry in data['entries']:
            if entry.get('kind') == 'local_file' and (entry.get('source_url') or '').rstrip('/') == url:
                entry['local_path'] = str(Path(root) / relative)
                entry['status'] = 'installed'
    # Cooperate with the running app; preserve selections and concurrent edits.
    JsonStore(registry_path, {'entries': [], 'active': {}}, _validate).mutate(restore)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('features', nargs='+', choices=list(ASSETS), help='Restore only selected feature assets.')
    args = parser.parse_args()
    for feature in args.features:
        ensure_assets(feature)
        record_restored(feature)
