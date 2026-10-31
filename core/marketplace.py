"""Stage-aware install helpers for core/model_registry.py's local_file
entries. Kept separate from model_registry.py itself so the registry
stays generic (any stage type, any kind) while "what does an installed
local file actually mean for THIS stage type" lives here.

Deliberately does NOT auto-populate the registry with anything (no
built-in CLONED_USER entry, no scanning old RVC folders for pre-existing
.pth files) - the marketplace is meant to reflect only what the user has
explicitly connected. An earlier version of this module seeded a default
voice entry on first run; that was removed because it silently
reappeared any time the voice registry was emptied out, fighting a user
who deliberately wanted a clean slate.
"""

import os
import shutil
from pathlib import Path

import config
from core.downloader import extract_archive


def install_downloaded_voice_model(downloaded_path):
    """Keep checkpoints in their download's owned tree; never replace user weights."""
    from core.model_contract import local_contract
    path = Path(downloaded_path)
    if path.suffix.lower() == ".zip":
        directory = Path(str(path) + "_extracted")
        extract_archive(str(path), str(directory))
        candidates = [item for item in directory.rglob("*.pth")
                      if not item.name.startswith(("G_", "D_"))]
        if len(candidates) != 1:
            raise ValueError("Voice archive must contain exactly one inference checkpoint")
        path = candidates[0]
    if path.suffix.lower() != ".pth":
        raise ValueError("RVC requires a .pth file or an unambiguous ZIP archive")
    local_contract("voice", str(path))
    return path.stem, str(path)
