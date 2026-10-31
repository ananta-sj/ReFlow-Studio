import os
import sys

# --- HARDWARE CONFIG ---
# Desktop startup must not require a working legacy AI runtime. Feature
# preflight checks the engine actually selected for each job.
TORCH_IMPORT_ERROR = None
try:
    import torch
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    if DEVICE == "cuda":
        torch.backends.cudnn.benchmark = True
except (ImportError, OSError, RuntimeError) as error:
    torch = None
    TORCH_IMPORT_ERROR = str(error)
    DEVICE = "cpu"

# --- PATHS ---
# Under a PyInstaller-frozen build, __file__ resolves inside the bundle's
# internal extraction path, not the folder the actual .exe (and the
# models/ffmpeg/gfpgan folders the user actually has) lives in - sys.frozen
# is PyInstaller's own documented way to detect this and use
# sys.executable's directory instead. Running from source (the normal dev
# path) is unaffected, since sys.frozen is never set there.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# torchcodec (coqui-tts/f5-tts's audio IO backend under torch>=2.9) needs
# real FFmpeg *shared* libraries (avcodec-*.dll etc.) at runtime - this
# project's own bundled ffmpeg/bin/ffmpeg.exe is a --enable-static build
# with no such DLLs, so TTS synthesis previously failed on every single
# segment with "Could not load libtorchcodec", silently (each failure was
# logged but swallowed per-segment, so a whole render could "complete"
# with zero real dubbed audio). A full-shared FFmpeg build's DLLs are
# vendored into ffmpeg/shared_libs/. Plain PATH is NOT enough to satisfy
# Windows' post-3.8 safe DLL search mode for a dependent DLL loaded via
# ctypes.CDLL(full_path) (which is how torch.ops.load_library resolves
# torchcodec's own .dll) - os.add_dll_directory() is required, and must
# run after `import torch` above so torch's own DLL directories are
# already registered first (torchcodec's DLLs depend on them too).
_SHARED_FFMPEG_LIBS = os.path.join(BASE_DIR, "ffmpeg", "shared_libs")
if os.path.isdir(_SHARED_FFMPEG_LIBS) and hasattr(os, "add_dll_directory"):
    _SHARED_FFMPEG_HANDLE = os.add_dll_directory(_SHARED_FFMPEG_LIBS)

TEMP_PATH = os.path.join(BASE_DIR, "temp")
OUTPUT_PATH = os.path.join(BASE_DIR, "outputs")

# [CRITICAL FIX] We define BOTH names to prevent errors
MODELS_PATH = os.path.join(BASE_DIR, "models")
MODELS_DIR = MODELS_PATH  # Alias for compatibility

# Ensure folders exist
os.makedirs(TEMP_PATH, exist_ok=True)
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(MODELS_PATH, exist_ok=True)

# --- TTS SETTINGS ---
TTS_default_voice = "en-US-AriaNeural"
TTS_rate = "+0%"
