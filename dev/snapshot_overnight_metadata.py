"""Preserve diagnosis records, not generated media, before output cleanup."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'core')]


def main():
    import psutil
    current = psutil.Process()
    ancestors = {p.pid for p in current.parents()} | {current.pid}
    for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
        if process.pid in ancestors:
            continue
        command = ' '.join(process.info.get('cmdline') or []).lower()
        if str(ROOT).lower() in command and any(name in command for name in ('main.py', 'cuda_worker.py', 'diarization_worker.py')):
            raise RuntimeError('A ReFlow process is still active; pause it before cleanup')
    destination = ROOT/'docs/diagnostics/overnight-20261114-metadata'
    destination.mkdir(exist_ok=True)
    records = []
    for name in ('queue_state.json', 'render_state.json'):
        shutil.copy2(ROOT/name, destination/name)
    for source in (ROOT/'outputs').rglob('*'):
        if source.is_symlink() or not source.is_file() or source.suffix.lower() not in ('.json', '.jsonl', '.log'):
            continue
        target = destination/'outputs'/source.relative_to(ROOT/'outputs')
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if len(data) > 20*1024**2:
            data = data[-2*1024**2:]
        target.write_bytes(data)
        records.append(dict(path=str(source.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    (destination/'snapshot.json').write_text(json.dumps(dict(media_preserved=False, files=records), indent=2), encoding='utf-8')
    from core.queue_manager import QueueManager
    queue = QueueManager(ROOT/'queue_state.json')
    queue.set_paused(True)
    for item in queue.get_items():
        if item['status']=='completed':
            queue.update_item(item['id'], output_path=None, status_text='Output cleared for diagnosis')
    from core.render_state import clear
    clear()
    print('Saved',len(records),'diagnostic text records; queue paused; no generated media copied.',flush=True)


if __name__=='__main__':
    main()
