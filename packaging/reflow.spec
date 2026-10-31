# PyInstaller spec for Reflow Studio - builds a real native executable
# (onedir: a folder containing the .exe/binary + its Python runtime,
# not a single self-extracting file, since that's slow to start for a
# torch/transformers-sized dependency tree) on whichever OS this is run
# on. PyInstaller cannot cross-compile - a Windows build must run on
# Windows, a Linux build on Linux, a macOS build on macOS - see
# .github/workflows/build.yml for the 3-OS CI matrix that actually
# produces all three from one source tree.
#
# noarchive=True keeps every bundled .py as a real compiled file inside
# the onedir output (mirroring the source tree's own relative layout)
# instead of packing them into a compressed in-memory archive. Several
# modules in this codebase (core/lipsync_handler.py, core/enhancer.py,
# core/rvc/rvc_handler.py, etc.) locate data files relative to their own
# __file__ - inside a compressed archive that resolves to a synthetic,
# non-filesystem path and those lookups would silently break. Run from
# packaging/, e.g.: pyinstaller packaging/reflow.spec
#
# Run scripts/build_dist.py after this to copy the large runtime asset
# folders (ffmpeg/, models/, gfpgan/, core/Wav2Lip/checkpoints/) next to
# the built executable - deliberately NOT bundled as PyInstaller datas,
# since core/integrity.py already owns downloading/managing them and
# duplicating multi-GB weights into the PyInstaller analysis step would
# make every rebuild far slower for no benefit.

import os

block_cipher = None
# PyInstaller exec()'s .spec files in a namespace with no __file__ - it
# injects SPECPATH (the spec file's own directory) for exactly this
# purpose instead. Found by actually running this, not assumed.
ROOT = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT, os.path.join(ROOT, "core")],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "frontend", "dist"), "frontend/dist"),
    ],
    hiddenimports=[
        # Packages that build their public API dynamically (plugin
        # registries, lazy submodule loading) - PyInstaller's static
        # import scanner can't see these on its own, and a missing one
        # here fails at runtime, not at build time, which is worse.
        "torch", "torchaudio", "torchvision",
        "transformers", "tokenizers", "accelerate", "airllm",
        "TTS", "TTS.utils.synthesizer",
        "cv2",
        "gfpgan", "realesrgan", "basicsr",
        "librosa", "soundfile",
        "keyring.backends",
        "engineio.async_drivers.threading",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ReflowStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-compressing torch/opencv's native DLLs is a common
                # source of false-positive AV flags and load failures -
                # not worth the size savings for a bundle this size anyway.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows needs a real multi-resolution .ico (assets/icon.png alone
    # isn't accepted as an EXE icon resource); Linux/macOS builds ignore
    # this - Linux has no exe-icon concept and macOS uses Info.plist/an
    # .icns bundle instead, neither of which this onedir build produces.
    icon=os.path.join(ROOT, "assets", "icon.ico") if os.name == "nt" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ReflowStudio",
)
