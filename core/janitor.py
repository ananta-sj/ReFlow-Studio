import os
import sys
import shutil
import gc
import psutil
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Process names to hunt, without extension - psutil reports "ffmpeg.exe" on
# Windows but bare "ffmpeg"/"python3" on Mac/Linux, so compare stems.
ROGUE_PROCESS_STEMS = {'ffmpeg', 'ffprobe', 'python', 'python3'}


class Janitor:
    def __init__(self):
        self.root_dir = config.BASE_DIR
        self.temp_dir = config.TEMP_PATH
        self.output_dir = config.OUTPUT_PATH

    def kill_rogue_processes(self):
        """Kills background tasks (FFmpeg, Python Subprocesses) that cause freezes."""
        print("[JANITOR] 🔫 Hunting rogue processes...")
        current_process = psutil.Process()
        children = current_process.children(recursive=True)

        for child in children:
            try:
                stem = os.path.splitext(child.name())[0].lower()
                # Kill FFmpeg or subprocesses, but NOT the main GUI
                if stem in ROGUE_PROCESS_STEMS:
                    print(f"[JANITOR] 💥 Killing {child.name()} (PID: {child.pid})")
                    child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def sweep(self, deep=False):
        """Standard cleaning for temp files."""
        # 1. Flush RAM/VRAM
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except (ImportError, RuntimeError):
            pass
        gc.collect()

        # 2. Clear Temp
        if os.path.exists(self.temp_dir):
            try:
                root = Path(self.root_dir).resolve()
                temp = Path(self.temp_dir).absolute()
                if temp.resolve() != temp or not temp.is_relative_to(root) or temp == root:
                    raise RuntimeError('Unsafe temporary cleanup path.')
                # RenderContext owns jobs, including concurrent sessions. A
                # global sweep must never delete another owner's requests.
                for entry in temp.iterdir():
                    if entry.name == 'jobs':
                        continue
                    if entry.resolve() != entry or entry.is_symlink() or getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400:
                        raise RuntimeError('Temporary cleanup cannot follow reparse points.')
                    if entry.is_dir():
                        shutil.rmtree(entry)
                    else:
                        entry.unlink()
                print(f"[JANITOR] ✅ Legacy temp cleared; job workspaces preserved.")
            except Exception as e:
                print(f"[JANITOR] ⚠️ Temp Clean Warning: {e}")

        # 3. Deep Clean (PyCache)
        if deep:
            self.remove_pycache()

    def remove_pycache(self):
        """Recursively burns all __pycache__ folders."""
        print("[JANITOR] 🧽 Scrubbing __pycache__...")
        count = 0
        for root, dirs, files in os.walk(self.root_dir):
            if "__pycache__" in dirs:
                try:
                    shutil.rmtree(os.path.join(root, "__pycache__"))
                    count += 1
                except OSError as e:
                    print(f"[JANITOR] ⚠️ Could not remove {root}\\__pycache__: {e}")
        print(f"[JANITOR] ✅ Removed {count} cache nests.")

    def destroy_all_data(self):
        """Factory Reset: Wipes Temp, Output, and Cache."""
        print("[JANITOR] ☢️ INITIATING FACTORY RESET...")
        self.kill_rogue_processes()
        self.sweep(deep=True)
        
        # WIPE OUTPUT
        if os.path.exists(self.output_dir):
            try:
                shutil.rmtree(self.output_dir)
                os.makedirs(self.output_dir)
                print("[JANITOR] ✅ Output Directory Wiped.")
            except Exception as e:
                print(f"[JANITOR] ❌ Could not wipe output: {e}")
