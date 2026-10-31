"""Read-only workspace storage snapshot; no file contents or deletion."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CACHE_NAMES = {'__pycache__', '.cache', '.hf-cache', '.pytest_cache', '.architecture-npm-cache', '.vite'}


def main():
    groups, caches, skipped, count = {}, {}, [], 0
    for directory, children, files in os.walk(ROOT, followlinks=False):
        parent = Path(directory)
        for name in list(children):
            path = parent / name
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                skipped.append(path.relative_to(ROOT).as_posix())
                children.remove(name)
        for name in files:
            path = parent / name
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue  # Active QA files can disappear during this snapshot.
            relative = path.relative_to(ROOT)
            if path.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
                skipped.append(relative.as_posix())
                continue
            group = relative.parts[0] if len(relative.parts) > 1 else '(root files)'
            groups[group] = groups.get(group, 0) + stat.st_size
            count += 1
            for component in relative.parts[:-1]:
                if component in CACHE_NAMES:
                    caches[component] = caches.get(component, 0) + stat.st_size
                    break
    report = dict(recorded_at=datetime.now(timezone.utc).isoformat(), files=count,
                  total_bytes=sum(groups.values()), bytes_by_top_folder=groups,
                  cache_bytes_by_name=caches, skipped_reparse_points=skipped,
                  note='Read-only snapshot includes originals, models, optional runtimes and QA copies. Active QA files can change; cache classification is not deletion authorization.')
    (ROOT / 'docs/validation/2026-10-04-storage-inventory.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
