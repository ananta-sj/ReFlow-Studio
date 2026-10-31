"""Builds the native Reflow Studio executable for whichever OS this runs
on (Windows/Linux/macOS - PyInstaller can't cross-compile, see
reflow.spec's docstring) and assembles a ready-to-run distribution folder:
runs PyInstaller against reflow.spec, then copies the large runtime asset
folders (ffmpeg/, models/, gfpgan/, core/Wav2Lip/checkpoints/) alongside
the built executable, since those are deliberately NOT PyInstaller datas
(core/integrity.py already owns downloading/managing them, and bundling
multi-GB weights into every PyInstaller analysis pass would make rebuilds
far slower for no benefit).

Usage: python packaging/build_dist.py
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "packaging", "reflow.spec")
DIST_DIR = os.path.join(ROOT, "dist", "ReflowStudio")

# Copied as full folders alongside the built exe, matching how
# Launch_Reflow.bat/main.py already expect them to sit next to whatever's
# running the app - not bundled through PyInstaller's own `datas` (see
# reflow.spec).
ASSET_FOLDERS = ["ffmpeg", "models", "gfpgan", os.path.join("core", "Wav2Lip", "checkpoints")]


def run_pyinstaller():
    print(f"[build] Running PyInstaller for {sys.platform}...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", SPEC_PATH],
        cwd=ROOT, check=True,
    )


def copy_asset_folders():
    for rel in ASSET_FOLDERS:
        src = os.path.join(ROOT, rel)
        if not os.path.isdir(src):
            print(f"[build] Skipping missing asset folder: {rel}")
            continue
        dest = os.path.join(DIST_DIR, rel)
        print(f"[build] Copying {rel}/ -> {os.path.relpath(dest, ROOT)}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)


def main():
    if not os.path.exists(os.path.join(ROOT, "frontend", "dist", "index.html")):
        raise SystemExit(
            "frontend/dist/index.html not found. Build the frontend first:\n"
            "    cd frontend && npm install && npm run build"
        )

    run_pyinstaller()
    copy_asset_folders()

    exe_name = "ReflowStudio.exe" if sys.platform == "win32" else "ReflowStudio"
    print(f"\n[build] Done. Launch: {os.path.join(DIST_DIR, exe_name)}")


if __name__ == "__main__":
    main()
