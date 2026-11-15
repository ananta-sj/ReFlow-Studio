"""Remove this application's temporary tree after all owned work has stopped."""
import os
from pathlib import Path
import shutil

from core.stage_checkpoints import safe_path


def clear_temporary_files(project, temporary):
    project, temporary = safe_path(project), safe_path(temporary)
    if temporary == project or not temporary.is_relative_to(project):
        raise ValueError('Temporary cleanup must stay inside this project.')
    if not temporary.exists():
        return
    # Validate the complete tree before deleting any entry.
    for directory, folders, files in os.walk(temporary, followlinks=False):
        for name in folders + files:
            safe_path(Path(directory) / name)
    for entry in temporary.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
