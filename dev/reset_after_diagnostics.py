"""Requested offline reset, preserving all previous work outside active folders."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import psutil
    from core.deletion_plan import safe_path
    from core.settings import Settings
    from core.ui_preferences import UIPreferences
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        if process.pid == os.getpid():
            continue
        if 'python' not in (process.info['name'] or '').lower():
            continue
        command = ' '.join(process.info['cmdline'] or []).lower()
        if str(ROOT).lower() in command:
            raise RuntimeError('ReFlow or a project worker is still running; reset refused.')
    archive = safe_path(ROOT/'docs/diagnostics'/('reset-recovery-'+datetime.now().strftime('%Y%m%d-%H%M%S')), ROOT)
    archive.mkdir(parents=True)
    names = ('settings.json', 'ui_preferences.json', 'queue_state.json', 'render_state.json')
    for name in names:
        path = safe_path(ROOT/name, ROOT)
        if path.is_file():
            shutil.copy2(path, archive/name)
    moved = []
    for name in ('outputs', 'temp'):
        source = safe_path(ROOT/name, ROOT)
        destination = safe_path(archive/name, ROOT)
        if destination.exists():
            raise RuntimeError('Archive destination already exists')
        if source.exists():
            source.rename(destination)
            moved.append(name)
        source.mkdir(exist_ok=True)
    Settings().reset()
    UIPreferences().store.mutate(lambda data: data.clear())
    (ROOT/'queue_state.json').write_text(json.dumps(dict(version=1, items=[], paused=True))+'\n', encoding='utf-8')
    recovery = safe_path(ROOT/'render_state.json', ROOT)
    if recovery.exists():
        recovery.rename(archive/'inactive-render-state.json')
    result = dict(status='reset-complete', archive=str(archive), preserved=moved,
                  models_retained=True, runtimes_retained=True,
                  source_videos_untouched=True)
    (archive/'reset-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
